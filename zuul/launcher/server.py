# Copyright 2024 BMW Group
# Copyright 2024-2025 Acme Gating, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import collections
from contextlib import nullcontext
import errno
import fcntl
import hashlib
import logging
import os
import random
import select
import socket
import subprocess
import threading
import time
import uuid
from urllib.parse import urlparse

import cachetools
import mmh3
import paramiko
import requests
from opentelemetry import trace

from zuul import exceptions, model
import zuul.lib.repl
from zuul.lib import commandsocket, tracing
from zuul.lib.collections import DefaultKeyDict
from zuul.lib.config import get_default
from zuul.lib.monitoring import MonitoringServer
from zuul.zk.image_registry import (
    ImageBuildRegistry,
    ImageUploadRegistry,
)
from zuul.lib.logutil import get_annotated_logger
from zuul.lib.statsd import get_statsd, normalize_statsd_name
from zuul.version import get_version_string
from zuul.zk import ZooKeeperClient
from zuul.zk.components import COMPONENT_REGISTRY, LauncherComponent
from zuul.zk.election import SessionAwareElection
from zuul.zk.exceptions import LockException
from zuul.zk.event_queues import (
    PipelineResultEventQueue,
    TenantTriggerEventQueue,
)
from zuul.zk.launcher import LauncherApi
from zuul.zk.layout import (
    LayoutProvidersStore,
    LayoutStateStore,
)
from zuul.zk.locks import tenant_read_lock
from zuul.zk.system import ZuulSystem
from zuul.zk.zkobject import ZKContext

COMMANDS = (
    commandsocket.StopCommand,
    commandsocket.ReplCommand,
    commandsocket.NoReplCommand,
)

# What gets written to disk in a single write() call; should be a
# multiple of 4k block size.
DOWNLOAD_BLOCK_SIZE = 1024 * 64
# The byte range size for an individual GET operation.  Should be a
# multiple of the above.  Current value is approx 100MiB.
DOWNLOAD_CHUNK_SIZE = DOWNLOAD_BLOCK_SIZE * 1525


def scores_for_label(label_cname, candidate_names):
    return {
        mmh3.hash(f"{n}-{label_cname}", signed=False): n
        for n in candidate_names
    }


def endpoint_score(endpoint):
    return mmh3.hash(f"{endpoint.canonical_name}", signed=False)


class NodesetRequestError(Exception):
    """Errors that should lead to the request being declined."""
    pass


class ProviderNodeError(Exception):
    """Errors that should lead to the provider node being failed."""
    pass


class LaunchTimeoutError(ProviderNodeError):
    """The node exceeded the provider's launch-timeout"""
    pass


class LauncherStatsElection(SessionAwareElection):
    """Election for emitting launcher stats."""

    def __init__(self, client):
        self.election_root = "/zuul/launcher/stats-election"
        super().__init__(client.client, self.election_root)


class DeleteJob:
    log = logging.getLogger("zuul.Launcher")

    def __init__(self, launcher, image_build_artifact, upload):
        self.launcher = launcher
        self.image_build_artifact = image_build_artifact
        self.upload = upload

    def run(self):
        try:
            self._run()
        except Exception:
            self.log.exception("Error in delete job")

    def _run(self):
        try:
            with self.launcher.createZKContext(None, self.log) as ctx:
                try:
                    with self.upload.locked(ctx, blocking=False):
                        self.upload.refresh(ctx)
                        self.log.info("Deleting image upload %s", self.upload)
                        with self.upload.activeContext(ctx):
                            self.upload.state = self.upload.State.DELETING
                        provider_cname = self.upload.providers[0]
                        provider = self.launcher.\
                            _getProviderByCanonicalName(provider_cname)
                        if self.upload.external_id:
                            provider.deleteImage(self.upload.external_id)
                        self.upload.delete(ctx)
                        self.launcher.upload_deleted_event.set()
                        self.launcher.wake_event.set()
                except LockException:
                    return
        except Exception:
            self.log.exception("Unable to delete upload %s", self.upload)


class UploadJob:
    log = logging.getLogger("zuul.Launcher")

    def __init__(self, launcher, image_build_artifact, uploads):
        self.launcher = launcher
        self.image_build_artifact = image_build_artifact
        self.uploads = uploads

    def run(self):
        try:
            self._run()
        except Exception:
            self.log.exception("Error in upload job")
        try:
            for upload in self.uploads:
                self.launcher.upload_uuids_in_queue.discard(upload.uuid)
        except Exception:
            self.log.exception("Error in upload job")

    def _acquireUploadLocks(self, ctx, uploads):
        try:
            with self.image_build_artifact.locked(ctx, blocking=False):
                for upload in self.uploads:
                    if upload.acquireLock(ctx, blocking=False):
                        upload.refresh(ctx)
                        if upload.external_id:
                            # Someone else finished it
                            upload.releaseLock(ctx)
                        elif upload.state != upload.State.PENDING:
                            # Someone else failed it (or otherwise)
                            upload.releaseLock(ctx)
                        else:
                            uploads.append(upload)
                            self.log.debug(
                                "Acquired upload lock for %s",
                                upload)
                            with upload.activeContext(ctx):
                                upload.state = upload.State.UPLOADING
        except LockException:
            # We may have raced another launcher; set the
            # event to try again.
            self.launcher.image_updated_event.set()

    def _getUploadArguments(self, uploads, upload_args):
        for upload in uploads:
            # The upload has a list of providers with identical
            # configurations.  Pick one of them as a representative.
            provider_cname = upload.providers[0]
            provider = self.launcher._getProviderByCanonicalName(
                provider_cname)
            provider_image = None
            for image in provider.images.values():
                if image.canonical_name == upload.canonical_name:
                    provider_image = image
            if provider_image is None:
                raise Exception(
                    f"Unable to find image {upload.canonical_name}")
            metadata = {
                'zuul_system_id': self.launcher.system.system_id,
                'zuul_upload_uuid': upload.uuid,
            }
            artifact = self.image_build_artifact
            image_name = f'{provider_image.name}-{upload.uuid}'

            upload_args[upload.uuid] = dict(
                provider=provider,
                provider_image=provider_image,
                image_name=image_name,
                url=artifact.url,
                image_format=artifact.format,
                metadata=metadata,
                md5=artifact.md5sum,
                sha256=artifact.sha256,
            )

    def _handleImports(self, uploads, upload_args, futures):
        for upload in uploads[:]:
            args = upload_args[upload.uuid]
            job = args['provider'].getImageImportJob(
                args['provider_image'],
                args['image_name'],
                args['url'],
                args['image_format'],
                args['metadata'],
                args['md5'],
                args['sha256'],
            )
            if job:
                uploads.remove(upload)
                self.log.debug("Scheduling import for %s", upload)
                future = self.launcher.endpoint_upload_executor.submit(
                    EndpointUploadJob(self.launcher, upload, job).run
                )
                futures.append((upload, future))

    def _handleUploads(self, uploads, upload_args, futures, path):
        for upload in uploads[:]:
            args = upload_args[upload.uuid]
            job = args['provider'].getImageUploadJob(
                args['provider_image'],
                args['image_name'],
                path,
                args['image_format'],
                args['metadata'],
                args['md5'],
                args['sha256'],
            )
            if job:
                uploads.remove(upload)
                self.log.debug("Scheduling upload for %s", upload)
                future = self.launcher.endpoint_upload_executor.submit(
                    EndpointUploadJob(self.launcher, upload, job).run
                )
                futures.append((upload, future))

    def _handleDownload(self):
        url = self.image_build_artifact.url
        url_components = urlparse(url)
        ext = url_components.path.split('.')[-1]
        path = os.path.join(self.launcher.temp_dir,
                            self.image_build_artifact.uuid)
        path = f'{path}.{ext}'
        self.log.info("Downloading artifact %s from %s into %s",
                      self.image_build_artifact, url, path)
        try:
            if ret := self.launcher.downloadArtifact(url, path):
                return ret
        except Exception as e:
            self.log.info("Unable to download %s: %s", url, e)

        # We can't download the file using requests, see if any of the
        # tenant's connections can download it using internal methods.
        providers = self.launcher.tenant_providers[
            self.image_build_artifact.build_tenant_name]
        for provider in providers:
            try:
                if ret := provider.downloadUrl(url, path):
                    return ret
            except Exception as e:
                self.log.info("Unable to download %s via %s: %s",
                              url, provider, e)

    def _handleCompression(self, path):
        if path.endswith('.zst'):
            orig_path = path
            try:
                subprocess.run(["zstd", "-dq", path],
                               cwd=self.launcher.temp_dir, check=True,
                               capture_output=True)
                path = path[:-len('.zst')]
                self.log.debug("Decompressed image to %s", path)
            finally:
                # Regardless of whether the decompression succeeded,
                # delete the original.  If it did succeed, the
                # original may already be gone.
                if os.path.exists(orig_path):
                    os.unlink(orig_path)
                    self.log.info("Deleted %s", orig_path)
        return path

    def _validateChecksum(self, path):
        artifact = self.image_build_artifact
        if not artifact.sha256:
            self.log.debug("Image build artifact %s has no sha256 checksum, "
                           "skipping validation", artifact)
            return
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while data := f.read(4096):
                h.update(data)
        digest = h.hexdigest()
        if digest != artifact.sha256:
            raise Exception(
                f"Downloaded file {path} sha256 "
                f"digest {digest} does not match "
                f"artifact {artifact} digest {artifact.sha256}")

    def _run(self):
        path = None
        uploads = []
        with self.launcher.createZKContext(None, self.log) as ctx:
            try:
                self.log.debug("Starting upload job for %s",
                               self.image_build_artifact)
                # Get a list of uploads we hold locks for
                self._acquireUploadLocks(ctx, uploads)
                if not uploads:
                    return

                # Prepare the arguments for all the import/upload jobs
                upload_args = {}
                self._getUploadArguments(uploads, upload_args)

                futures = []
                remaining_uploads = uploads[:]

                # Try a direct import if the provider supports it for
                # this url.
                self._handleImports(remaining_uploads, upload_args, futures)

                # Any uploads remaining need to be handled by
                # downloading the artifact and uploading.
                if remaining_uploads:
                    path = self._handleDownload()
                    if not path:
                        raise Exception("Unable to download artifact %s" % (
                            self.image_build_artifact,))
                    path = self._handleCompression(path)
                    self._validateChecksum(path)
                    self._handleUploads(
                        remaining_uploads, upload_args, futures, path)

                for upload, future in futures:
                    try:
                        self.log.debug("Waiting for upload %s", upload)
                        future.result()
                    except Exception:
                        self.log.exception("Unable to upload image %s", upload)
            finally:
                self.log.debug("Finalizing upload job for %s",
                               self.image_build_artifact)
                for upload in uploads:
                    try:
                        with upload.activeContext(ctx):
                            if upload.external_id:
                                self.log.debug(
                                    "Marking upload %s ready", upload)
                                upload.state = upload.State.READY
                            else:
                                new_upload = upload.copy(ctx)
                                self.log.debug(
                                    "Replacing upload %s with %s",
                                    upload, new_upload)
                                self.log.debug(
                                    "Marking upload %s deleting", upload)
                                upload.state = upload.State.DELETING
                                self.launcher.upload_deleted_event.set()
                    except Exception:
                        self.log.exception("Unable to update state for %s",
                                           upload)
                    try:
                        upload.releaseLock(ctx)
                        self.log.debug("Released upload lock for %s", upload)
                    except Exception:
                        self.log.exception("Unable to release lock for %s",
                                           upload)
                if path:
                    try:
                        os.unlink(path)
                        self.log.info("Deleted %s", path)
                    except Exception:
                        self.log.exception("Unable to delete %s", path)
                self.log.debug("Finished upload job for %s",
                               self.image_build_artifact)


class EndpointUploadJob:
    log = logging.getLogger("zuul.Launcher")

    def __init__(self, launcher, upload, job):
        self.launcher = launcher
        self.upload = upload
        self.job = job

    def run(self):
        try:
            self._run()
        except Exception:
            self.log.exception("Error in endpoint upload job")

    def _run(self):
        # The upload has a list of providers with identical
        # configurations.  Pick one of them as a representative.
        self.log.info("Starting upload %s", self.upload)
        external_id = self.job.run()
        self.log.info("Finished upload %s", self.upload)
        with self.launcher.createZKContext(self.upload._lock, self.log) as ctx:
            self.upload.updateAttributes(
                ctx,
                external_id=external_id)
        if not self.upload.validated:
            self.launcher.addImageValidateEvent(self.upload)


class NodescanRequest:
    """A state machine for a nodescan request.

    When complete, use the result() method to obtain the keys or raise
    an exception if an errer was encountered during processing.

    """

    START = 'start'
    CONNECTING_INIT = 'connecting'
    NEGOTIATING_INIT = 'negotiating'
    CONNECTING_KEY = 'connecting key'
    NEGOTIATING_KEY = 'negotiating key'
    COMPLETE = 'complete'

    def __init__(self, node, log):
        self.state = self.START
        self.node = node
        self.host_key_checking = node.host_key_checking
        self.timeout = node.boot_timeout
        self.log = log
        self.complete = False
        self.keys = []
        if (node.connection_type == 'ssh' or
            node.connection_type == 'network_cli'):
            self.gather_hostkeys = True
        else:
            self.gather_hostkeys = False
        self.ip = node.interface_ip
        self.port = node.connection_port
        addrinfo = socket.getaddrinfo(self.ip, self.port)[0]
        self.family = addrinfo[0]
        self.sockaddr = addrinfo[4]
        self.sock = None
        self.transport = None
        self.event = None
        self.key_types = None
        self.key_index = None
        self.key_type = None
        self.start_time = time.monotonic()
        self.worker = None
        self.exception = None
        self.connect_start_time = None
        # Stats
        self.init_connection_attempts = 0
        self.key_connection_failures = 0
        self.key_negotiation_failures = 0

    def setWorker(self, worker):
        """Store a reference to the worker thread so we register and unregister
        the socket file descriptor from the polling object"""
        self.worker = worker

    def fail(self, exception):
        """Declare this request a failure and store the related exception"""
        self.exception = exception
        self.cleanup()
        self.complete = True
        self.state = self.COMPLETE

    def cleanup(self):
        """Try to close everything and unregister from the worker"""
        self._close()
        if self.exception:
            status = 'failed'
        else:
            status = 'complete'
        dt = int(time.monotonic() - self.start_time)
        self.log.debug("Nodescan request %s with %s keys, "
                       "%s initial connection attempts, "
                       "%s key connection failures, "
                       "%s key negotiation failures in %s seconds",
                       status, len(self.keys),
                       self.init_connection_attempts,
                       self.key_connection_failures,
                       self.key_negotiation_failures,
                       dt)
        self.worker = None

    def result(self):
        """Return the resulting keys, or raise an exception"""
        if self.exception:
            raise self.exception
        return self.keys

    def _close(self):
        if self.transport:
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None
            self.event = None
        if self.sock:
            self.worker.unRegisterDescriptor(self.sock)
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _checkTimeout(self):
        now = time.monotonic()
        if now - self.start_time > self.timeout:
            raise exceptions.ConnectionTimeoutException(
                f"Timeout connecting to {self.ip} on port {self.port}")

    def _checkTransport(self):
        # This stanza is from
        # https://github.com/paramiko/paramiko/blob/main/paramiko/transport.py
        if not self.transport.active:
            e = self.transport.get_exception()
            if e is not None:
                raise e
            raise paramiko.exceptions.SSHException("Negotiation failed.")

    def _connect(self):
        if self.sock:
            self.worker.unRegisterDescriptor(self.sock)
        self.sock = socket.socket(self.family, socket.SOCK_STREAM)
        # Set nonblocking so we can poll for connection completion
        self.sock.setblocking(False)
        try:
            self.sock.connect(self.sockaddr)
        except BlockingIOError:
            pass
        self.connect_start_time = time.monotonic()
        self.worker.registerDescriptor(self.sock)

    def _start(self):
        # Use our Event subclass that will wake the worker when the
        # event is set.
        self.event = NodescanEvent(self.worker)
        # Return the socket to blocking mode as we hand it off to paramiko.
        self.sock.setblocking(True)
        self.transport = paramiko.transport.Transport(self.sock)
        if self.key_type is not None:
            opts = self.transport.get_security_options()
            opts.key_types = [self.key_type]
        # This starts a thread.
        self.transport.start_client(
            event=self.event, timeout=self.timeout)

    def _nextKey(self):
        self._close()
        self.key_index += 1
        if self.key_index >= len(self.key_types):
            self.state = self.COMPLETE
            return True
        self.key_type = self.key_types[self.key_index]
        self._connect()
        self.state = self.CONNECTING_KEY

    def advance(self, socket_ready):
        if self.state == self.START:
            if self.worker is None:
                raise Exception("Request not registered with worker")
            if not self.host_key_checking:
                self.state = self.COMPLETE
            else:
                self.init_connection_attempts += 1
                self._connect()
                self.state = self.CONNECTING_INIT

        if self.state == self.CONNECTING_INIT:
            if not socket_ready:
                # Check the overall timeout
                self._checkTimeout()
                # If we're still here, then don't let any individual
                # connection attempt last more than 10 seconds:
                if time.monotonic() - self.connect_start_time >= 10:
                    self._close()
                    self.state = self.START
                return
            eno = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if eno:
                if eno not in [errno.ECONNREFUSED, errno.EHOSTUNREACH]:
                    self.log.exception(
                        f"Error {eno} connecting to {self.ip} "
                        f"on port {self.port}")
                # Try again.  Don't immediately start to reconnect
                # since econnrefused can happen very quickly, so we
                # could end up busy-waiting.
                self._close()
                self.state = self.START
                self._checkTimeout()
                return
            if self.gather_hostkeys:
                self._start()
                self.state = self.NEGOTIATING_INIT
            else:
                self.state = self.COMPLETE

        if self.state == self.NEGOTIATING_INIT:
            if not self.event.is_set():
                self._checkTimeout()
                return
            # This will raise an exception on ssh errors
            try:
                self._checkTransport()
            except Exception:
                self.log.exception(
                    f"SSH error connecting to {self.ip} on port {self.port}")
                # Try again; go to start to avoid busy-waiting.
                self._close()
                self.key_negotiation_failures += 1
                self.state = self.START
                self._checkTimeout()
                return
            # This is our first successful connection.  Now that
            # we've done it, start again specifying the first key
            # type.
            opts = self.transport.get_security_options()
            self.key_types = opts.key_types
            self.key_index = -1
            self._nextKey()

        if self.state == self.CONNECTING_KEY:
            if not socket_ready:
                self._checkTimeout()
                # If we're still here, then don't let any individual
                # connection attempt last more than 10 seconds:
                if time.monotonic() - self.connect_start_time >= 10:
                    # Restart the connection attempt for this key (not
                    # the whole series).
                    self.key_connection_failures += 1
                    self._close()
                    self._connect()
                    self.state = self.CONNECTING_KEY
                return
            eno = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if eno:
                self.log.error(
                    f"Error {eno} connecting to {self.ip} on port {self.port}")
                self.key_connection_failures += 1
                self._close()
                self._connect()
                self.state = self.CONNECTING_KEY
                return
            self._start()
            self.state = self.NEGOTIATING_KEY

        if self.state == self.NEGOTIATING_KEY:
            if not self.event.is_set():
                self._checkTimeout()
                return
            # This will raise an exception on ssh errors
            try:
                self._checkTransport()
            except Exception as e:
                msg = str(e)
                if 'no acceptable host key' not in msg:
                    # We expect some host keys to not be valid
                    # when scanning only log if the error isn't
                    # due to mismatched host key types.
                    self.log.exception(
                        f"SSH error connecting to {self.ip} "
                        f"on port {self.port}")
                    self.key_negotiation_failures += 1
                self._nextKey()

        # Check if we're still in the same state
        if self.state == self.NEGOTIATING_KEY:
            key = self.transport.get_remote_server_key()
            if key:
                self.keys.append("%s %s" % (key.get_name(), key.get_base64()))
                self.log.debug('Added ssh host key: %s', key.get_name())
            self._nextKey()

        if self.state == self.COMPLETE:
            self._close()
            self.complete = True


class NodescanEvent(threading.Event):
    """A subclass of event that will wake the NodescanWorker poll"""
    def __init__(self, worker, *args, **kw):
        super().__init__(*args, **kw)
        self._zuul_worker = worker

    def set(self):
        super().set()
        try:
            os.write(self._zuul_worker.wake_write, b'\n')
        except Exception:
            pass


class NodescanWorker:
    """Handles requests for nodescans.

    This class has a single thread that drives nodescan requests
    submitted by the launcher.

    """
    # This process is highly scalable, except for paramiko which
    # spawns a thread for each ssh connection.  To avoid thread
    # overload, we set a max value for concurrent requests.
    # Simultaneous requests higher than this value will be queued.
    MAX_REQUESTS = 100
    TIMEOUT = 1

    def __init__(self):
        # Remember to close all pipes to prevent leaks in tests.
        self.wake_read, self.wake_write = os.pipe()
        fcntl.fcntl(self.wake_read, fcntl.F_SETFL, os.O_NONBLOCK)
        self._running = False
        self._active_requests = []
        self._pending_requests = []
        self.poll = select.epoll()
        self.poll.register(self.wake_read, select.EPOLLIN)

    def start(self):
        self._running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self._running = False
        os.write(self.wake_write, b'\n')

    def join(self):
        self.thread.join()

        for fd in (self.wake_read, self.wake_write):
            try:
                os.close(fd)
            except OSError as e:
                # If the nodescan worker is joined multiple times the
                # file descriptors have already been closed.
                if e.errno != errno.EBADF:
                    raise

    def addRequest(self, request):
        """Submit a nodescan request"""
        request.setWorker(self)
        if len(self._active_requests) >= self.MAX_REQUESTS:
            self._pending_requests.append(request)
        else:
            self._active_requests.append(request)
            # If the poll is sleeping, wake it up for immediate action
            os.write(self.wake_write, b'\n')

    def removeRequest(self, request):
        """Remove the request and cleanup"""
        if request is None:
            return
        request.cleanup()
        try:
            self._active_requests.remove(request)
        except ValueError:
            pass
        try:
            self._pending_requests.remove(request)
        except ValueError:
            pass

    def length(self):
        return len(self._active_requests) + len(self._pending_requests)

    def registerDescriptor(self, fd):
        """Register the fd with the poll object"""
        # Oneshot means that once it triggers, it will automatically
        # be removed.  That's great for us since we only use this for
        # detecting when the initial connection is complete and have
        # no further use.
        self.poll.register(
            fd, select.EPOLLOUT | select.EPOLLERR |
            select.EPOLLHUP | select.EPOLLONESHOT)

    def unRegisterDescriptor(self, fd):
        """Unregister the fd with the poll object"""
        try:
            self.poll.unregister(fd)
        except Exception:
            pass

    def run(self):
        # To avoid busy waiting, we will process any request with a
        # ready socket, but only process the remaining requests
        # periodically.  This value is the last time we processed
        # those unready requests.
        last_unready_check = 0
        while self._running:
            # Set the poll timeout to 1 second so that we check all
            # requests for timeouts every second.  This could be
            # increased to a few seconds without significant impact.
            timeout = self.TIMEOUT
            while (self._pending_requests and
                   len(self._active_requests) < self.MAX_REQUESTS):
                # If we have room for more requests, add them and set
                # the timeout to 0 so that we immediately start
                # advancing them.
                request = self._pending_requests.pop(0)
                self._active_requests.append(request)
                timeout = 0
                last_unready_check = 0
            ready = self.poll.poll(timeout=timeout)
            ready = [x[0] for x in ready]
            if self.wake_read in ready:
                # Empty the wake pipe
                while True:
                    try:
                        os.read(self.wake_read, 1024)
                    except BlockingIOError:
                        break
            process_unready = (time.monotonic() - last_unready_check >
                               self.TIMEOUT)
            for request in self._active_requests:
                try:
                    socket_ready = (request.sock and
                                    request.sock.fileno() in ready)
                    event_ready = request.event and request.event.is_set()
                    if process_unready or socket_ready or event_ready:
                        request.advance(socket_ready)
                except Exception as e:
                    request.fail(e)
                if request.complete:
                    self.removeRequest(request)
            if process_unready:
                last_unready_check = time.monotonic()


class CleanupWorker:
    # Delay 60 seconds between iterations
    INTERVAL = 60
    log = logging.getLogger("zuul.Launcher")

    def __init__(self, launcher):
        self.launcher = launcher
        self.wake_event = threading.Event()
        # These are indexed by endpoint cname
        self.possibly_leaked_nodes = {}
        self.possibly_leaked_uploads = {}
        self._running = False
        self.thread = None

    def start(self):
        self.log.debug("Starting cleanup worker thread")
        self._running = True
        self.thread = threading.Thread(target=self.run,
                                       name="CleanupWorker")
        self.thread.start()

    def stop(self):
        self.log.debug("Stopping cleanup worker")
        self._running = False
        self.wake_event.set()

    def join(self):
        self.log.debug("Joining cleanup thread")
        if self.thread:
            self.thread.join()
        self.log.debug("Joined cleanup thread")

    def run(self):
        while self._running:
            # Wait before performing the first cleanup
            self.wake_event.wait(self.INTERVAL)
            self.wake_event.clear()
            try:
                self._run()
            except Exception:
                self.log.exception("Error in cleanup worker:")

    def getMatchingEndpoints(self):
        all_launchers = {
            c.hostname: c for c in COMPONENT_REGISTRY.registry.all("launcher")}

        for endpoint in self.launcher.endpoints.values():
            candidate_launchers = {
                n: c for n, c in all_launchers.items()
                if not c.connection_filter
                or endpoint.connection.connection_name in c.connection_filter}
            candidate_names = set(candidate_launchers)
            launcher_scores = {endpoint_score(endpoint): n
                               for n in candidate_names}
            sorted_scores = sorted(launcher_scores.items())
            for score, launcher_name in sorted_scores:
                launcher = candidate_launchers.get(launcher_name)
                if not launcher:
                    # Launcher is no longer online
                    continue
                if launcher.state != launcher.RUNNING:
                    continue
                if launcher.hostname == self.launcher.component_info.hostname:
                    yield endpoint
                break

    def _run(self):
        for endpoint in self.getMatchingEndpoints():
            try:
                self.cleanupLeakedResources(endpoint)
            except Exception:
                self.log.exception("Error in cleanup worker:")

    def cleanupLeakedResources(self, endpoint):
        newly_leaked_nodes = {}
        newly_leaked_uploads = {}
        possibly_leaked_nodes = self.possibly_leaked_nodes.get(
            endpoint.canonical_name, {})
        possibly_leaked_uploads = self.possibly_leaked_uploads.get(
            endpoint.canonical_name, {})

        # Get a list of all providers that share this endpoint.  This
        # is because some providers may store resources like image
        # uploads in multiple per-provider locations.
        providers = [
            p for p in self.launcher._getProviders()
            if p.getEndpoint().canonical_name == endpoint.canonical_name
        ]

        for resource in endpoint.listResources(providers):
            if (resource.metadata.get('zuul_system_id') !=
                self.launcher.system.system_id):
                continue
            node_id = resource.metadata.get('zuul_node_uuid')
            upload_id = resource.metadata.get('zuul_upload_uuid')
            if node_id and self.launcher.api.getProviderNode(node_id) is None:
                newly_leaked_nodes[node_id] = resource
                if node_id in possibly_leaked_nodes:
                    # We've seen this twice now, so it's not a race
                    # condition.
                    try:
                        endpoint.deleteResource(resource)
                        # if self._statsd:
                        #     key = ('nodepool.provider.%s.leaked.%s'
                        #            % (self.provider.name,
                        #               resource.plural_metric_name))
                        #     self._statsd.incr(key, 1)
                    except Exception:
                        self.log.exception("Unable to delete leaked "
                                           f"resource for node {node_id}")
            if (upload_id and
                self.launcher.image_upload_registry.getItem(
                    upload_id) is None):
                newly_leaked_uploads[upload_id] = resource
                if upload_id in possibly_leaked_uploads:
                    # We've seen this twice now, so it's not a race
                    # condition.
                    try:
                        endpoint.deleteResource(resource)
                        # if self._statsd:
                        #     key = ('nodepool.provider.%s.leaked.%s'
                        #            % (self.provider.name,
                        #               resource.plural_metric_name))
                        #     self._statsd.incr(key, 1)
                    except Exception:
                        self.log.exception(
                            "Unable to delete leaked "
                            f"resource for upload {upload_id}")
        self.possibly_leaked_nodes[endpoint.canonical_name] =\
            newly_leaked_nodes
        self.possibly_leaked_uploads[endpoint.canonical_name] =\
            newly_leaked_uploads


class Launcher:
    log = logging.getLogger("zuul.Launcher")
    tracer = trace.get_tracer("zuul")
    # Max. time to wait for a cache to sync
    CACHE_SYNC_TIMEOUT = 10
    # Max. time the main event loop is allowed to sleep
    MAX_SLEEP = 1
    DELETE_TIMEOUT = 600
    MAX_QUOTA_AGE = 5 * 60  # How long to keep the quota information cached
    _stats_interval = 30

    def __init__(self, config, connections):
        self._running = True
        # The cleanup method requires some extra AWS mocks that are
        # not enabled in most tests, so we allow the test suite to
        # disable it.
        # TODO: switch basic launcher tests to openstack and remove.
        self._start_cleanup = True
        self.config = config
        self.connections = connections
        self.repl = None
        # All tenants and all providers
        self.tenant_providers = {}
        # Only endpoints corresponding to connections handled by this
        # launcher
        self.endpoints = {}

        self.statsd = get_statsd(config)
        if self.statsd:
            self.statsd_timer = self.statsd.timer
        else:
            self.statsd_timer = nullcontext

        # Raw provider quota
        self._provider_quota_cache = cachetools.TTLCache(
            maxsize=8192, ttl=self.MAX_QUOTA_AGE)
        # Provider quota - unmanaged usage
        self._provider_available_cache = cachetools.TTLCache(
            maxsize=8192, ttl=self.MAX_QUOTA_AGE)

        self.tracing = tracing.Tracing(self.config)
        self.zk_client = ZooKeeperClient.fromConfig(self.config)
        self.zk_client.connect()

        self.system = ZuulSystem(self.zk_client)
        self.trigger_events = TenantTriggerEventQueue.createRegistry(
            self.zk_client, self.connections
        )
        self.result_events = PipelineResultEventQueue.createRegistry(
            self.zk_client
        )

        COMPONENT_REGISTRY.create(self.zk_client)
        self.hostname = get_default(self.config, "launcher", "hostname",
                                    socket.getfqdn())
        self.component_info = LauncherComponent(
            self.zk_client, self.hostname, version=get_version_string())
        self.component_info.register()
        self.wake_event = threading.Event()
        self.stop_event = threading.Event()
        self.join_event = threading.Event()

        COMPONENT_REGISTRY.registry.registerCallback(self.wake_event.set)

        self.monitoring_server = MonitoringServer(config, 'launcher',
                                                  self.component_info)
        self.monitoring_server.start()

        self.connection_filter = get_default(
            self.config, "launcher", "connection_filter")
        self.api = LauncherApi(
            self.zk_client, COMPONENT_REGISTRY.registry, self.component_info,
            self.wake_event.set, self.connection_filter)

        self.temp_dir = get_default(self.config, 'launcher', 'temp_dir',
                                    '/tmp', expand_user=True)

        self.command_map = {
            commandsocket.StopCommand.name: self.stop,
            commandsocket.ReplCommand.name: self.startRepl,
            commandsocket.NoReplCommand.name: self.stopRepl,
        }
        command_socket = get_default(
            self.config, "launcher", "command_socket",
            "/var/lib/zuul/launcher.socket")
        self.command_socket = commandsocket.CommandSocket(command_socket)
        self._command_running = False

        self.layout_updated_event = threading.Event()
        self.layout_updated_event.set()

        self.image_updated_event = threading.Event()
        self.upload_deleted_event = threading.Event()

        self.tenant_layout_state = LayoutStateStore(
            self.zk_client, self._layoutUpdatedCallback)
        self.layout_providers_store = LayoutProvidersStore(
            self.zk_client, self.connections, self.system.system_id)
        self.local_layout_state = {}

        self.image_build_registry = ImageBuildRegistry(
            self.zk_client,
            self._imageUpdatedCallback
        )
        self.image_upload_registry = ImageUploadRegistry(
            self.zk_client,
            self._imageUpdatedCallback
        )

        self.nodescan_worker = NodescanWorker()
        self._run_lock = threading.Lock()
        self.launcher_thread = threading.Thread(
            target=self.run,
            name="Launcher",
        )
        # Avoid submitting duplicate upload jobs
        self.upload_uuids_in_queue = set()
        # Simultaneous image artifact processes (download+upload)
        self.upload_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="UploadWorker",
        )
        # Simultaneous uploads
        self.endpoint_upload_executor = ThreadPoolExecutor(
            # TODO: make configurable
            max_workers=10,
            thread_name_prefix="UploadWorker",
        )
        self.cleanup_worker = CleanupWorker(self)
        self.stats_election = LauncherStatsElection(self.zk_client)
        self.stats_thread = threading.Thread(target=self.runStatsElection)
        self.stats_thread.daemon = True

    def _layoutUpdatedCallback(self):
        self.layout_updated_event.set()
        self.wake_event.set()

    def _imageUpdatedCallback(self):
        self.image_updated_event.set()
        self.wake_event.set()

    def run(self):
        self.component_info.state = self.component_info.RUNNING
        self.log.debug("Launcher running")
        while self._running:
            loop_start = time.monotonic()
            try:
                with self._run_lock:
                    self._run()
            except Exception:
                self.log.exception("Error in main thread:")
            loop_duration = time.monotonic() - loop_start
            time.sleep(max(0, self.MAX_SLEEP - loop_duration))
            self.wake_event.wait()
            self.wake_event.clear()

    def _run(self):
        if self.layout_updated_event.is_set():
            self.layout_updated_event.clear()
            if self.updateTenantProviders():
                self.checkOldImages()
                self.checkMissingImages()
                self.checkMissingUploads()
        if self.image_updated_event.is_set():
            self.checkOldImages()
            self.checkMissingUploads()
        if self.upload_deleted_event.is_set():
            self.checkOldImages()
        self._processRequests()
        self._processNodes()
        self._processMinReady()

    def _processRequests(self):
        ready_nodes = self._getUnassignedReadyNodes()
        for request in self.api.getMatchingRequests():
            log = get_annotated_logger(self.log, request, request=request.uuid)
            if not request.hasLock():
                if request.state in request.FINAL_STATES:
                    # Nothing to do here
                    continue
                log.debug("Got request %s", request)
                with self.createZKContext(None, log) as ctx:
                    if not request.acquireLock(ctx, blocking=False):
                        log.debug("Failed to lock matching request %s",
                                  request)
                        continue
                    request.refresh(ctx)

                request_span = tracing.restoreSpan(request.span_info)
                with trace.use_span(request_span):
                    request._set(_span=self.tracer.start_span(
                        "NodesetRequestProcessing"))

            if not self._cachesReadyForRequest(request):
                self.log.debug("Caches are not up-to-date for %s", request)
                continue

            try:
                if request.state == model.NodesetRequest.State.REQUESTED:
                    self._acceptRequest(request, log, ready_nodes)
                elif request.state == model.NodesetRequest.State.ACCEPTED:
                    self._checkRequest(request, log)
            except NodesetRequestError as err:
                state = model.NodesetRequest.State.FAILED
                log.error("Marking request %s as %s: %s",
                          request, state, str(err))
                event = model.NodesProvisionedEvent(
                    request.uuid, request.buildset_uuid)
                self.result_events[request.tenant_name][
                    request.pipeline_name].put(event)
                with self.createZKContext(request._lock, log) as ctx:
                    request.updateAttributes(ctx, state=state)
            except Exception:
                log.exception("Error processing request %s", request)
            if request.state in request.FINAL_STATES:
                request._span.set_attributes(request.getSpanAttributes())
                request._span.end()
                with self.createZKContext(None, log) as ctx:
                    request.releaseLock(ctx)

    def _cachesReadyForRequest(self, request):
        # Make sure we have all associated provider nodes in the cache
        return all(
            self.api.getProviderNode(n)
            for n in request.nodes
        )

    def _filterReadyNodes(self, ready_nodes, request):
        # This returns a nested defaultdict like:
        # {label_name: {node: [node_providers]}}
        request_ready_nodes = collections.defaultdict(
            lambda: collections.defaultdict(list))
        if request.image_upload_uuid:
            # This is a request for an image validation job.
            # Don't use any ready nodes for that.
            return request_ready_nodes
        providers = self.tenant_providers.get(request.tenant_name)
        if not providers:
            return request_ready_nodes
        label_names = set(request.labels)
        for label_name in label_names:
            ready_for_label = list(ready_nodes.get(label_name, []))
            if not ready_for_label:
                continue
            # TODO: sort by age? use old nodes first? random to reduce
            # chance of thundering herd?
            for node in ready_for_label:
                if node.is_locked:
                    continue
                if node.hasExpired():
                    continue
                # Check to see if this node is valid in this tenant
                for provider in providers:
                    if node.isPermittedForProvider(provider):
                        # This node is usable with this provider
                        request_ready_nodes[label_name][node].append(provider)
        return request_ready_nodes

    def _acceptRequest(self, request, log, ready_nodes):
        log.debug("Considering request %s", request)
        request_ready_nodes = self._filterReadyNodes(ready_nodes, request)
        # Create provider nodes for the requested labels
        label_providers = self._selectProviders(
            request, request_ready_nodes, log)
        with (self.createZKContext(request._lock, log) as ctx,
              request.activeContext(ctx)):
            for i, (label, provider) in enumerate(label_providers):
                ready_for_label = request_ready_nodes[label.name]
                # TODO: sort by age? use old nodes first? random to reduce
                # chance of thundering herd?
                for node, providers in ready_for_label.items():
                    if not node.acquireLock(ctx, blocking=False):
                        log.debug("Failed to lock matching ready node %s",
                                  node)
                        continue
                    try:
                        node.refresh(ctx)
                        # Double check if it's still available
                        if (node.request_id or
                            node.state != node.State.READY):
                            request_ready_nodes[label.name].pop(node)
                            ready_nodes[label.name].remove(node)
                            continue
                        tags = provider.getNodeTags(
                            self.system.system_id, label, node.uuid,
                            provider, request)
                        with self.createZKContext(node._lock, self.log) as ctx:
                            node.updateAttributes(
                                ctx,
                                provider=provider.canonical_name,
                                request_id=request.uuid,
                                tenant_name=request.tenant_name,
                                tags=tags,
                            )
                        request_ready_nodes[label.name].pop(node)
                        ready_nodes[label.name].remove(node)
                        log.debug("Assigned ready node %s", node.uuid)
                        break
                    except Exception:
                        log.exception("Faild to assign ready node %s", node)
                        continue
                    finally:
                        node.releaseLock(ctx)
                else:
                    # If we have not assigned any nodes to this
                    # request we don't have to proceed if there is no
                    # quota.
                    if not bool(request.provider_node_data):
                        try:
                            has_quota = self.doesProviderHaveQuotaForLabel(
                                provider, label, log)
                        except Exception:
                            self.log.exception(
                                "Error checking quota for label %s "
                                "in provider %s", label, provider)
                            raise NodesetRequestError(
                                "Unable to determine quota")
                        if not has_quota:
                            log.debug("Deferring request %s "
                                      "due to insufficient quota", request)
                            # TODO: We may want to consider all the
                            # labels at once so that if we can
                            # fulfilly any label immediately, we
                            # accept the request; currently this will
                            # happen only if we can fulfill the first
                            # label immediately.
                            return
                    node = self._requestNode(
                        label, request, provider, log, ctx)
                    log.debug("Requested node %s", node.uuid)
                request.addProviderNode(node)
            if request.provider_node_data:
                log.debug("Accepting request %s", request)
                request.state = model.NodesetRequest.State.ACCEPTED

    def _shuffleProviders(self, providers):
        # This is to allow unit test control of this process.
        providers = providers[:]
        random.shuffle(providers)
        return providers

    def _selectProviders(self, request, request_ready_nodes, log):
        providers = self.tenant_providers.get(request.tenant_name)
        if not providers:
            raise NodesetRequestError(
                f"No provider for tenant {request.tenant_name}")

        # Start with a randomized list of providers so that different
        # requests may have different behavior.
        providers = self._shuffleProviders(providers)

        # Sort that list by quota
        providers.sort(key=lambda p: self.getQuotaPercentage(p))

        # Then if there are ready nodes, sort so that we can use the
        # most ready nodes.
        if request_ready_nodes:
            # provider -> total ready nodes
            usable_provider_ready_nodes = collections.Counter()
            for label_name in set(request.labels):
                for node, node_providers in request_ready_nodes[
                        label_name].items():
                    for node_provider in node_providers:
                        usable_provider_ready_nodes[
                            node_provider.canonical_name] += 1
            providers.sort(
                key=lambda p: usable_provider_ready_nodes[p.canonical_name],
                reverse=True
            )

        # A list of providers that could work for all labels in the request
        ideal_providers_for_all_labels = set(providers)
        # The same, but omit providers with failures
        providers_for_all_labels = set(providers)
        # A list of providers for each label in the request, indexed
        # by label index number
        ideal_providers_for_label = {}
        # The same, but omit providers with failures
        providers_for_label = {}
        # Which providers are used by existing nodes in this request
        existing_provider_names = collections.Counter()

        for i, label_name in enumerate(request.labels):
            provider_failure_names = collections.Counter()
            pnd = request.getProviderNodeData(i)
            if pnd:
                provider_failure_names.update(pnd['failed_providers'])
                if pnd['uuid']:
                    existing_node = self.api.getProviderNode(pnd['uuid'])
                    # Special case for the current node just failed
                    if existing_node.state == existing_node.State.FAILED:
                        provider_failure_names[existing_node.provider] += 1
                    if existing_node.state not in existing_node.FAILED_STATES:
                        existing_provider_names[existing_node.provider] += 1
            candidate_providers = [
                p for p in providers
                if p.hasLabel(label_name)
                and (provider_failure_names[p.canonical_name] <
                     p.launch_attempts)
            ]
            ideal_providers_for_label[i] = []
            providers_for_label[i] = []
            for provider in providers:
                if not (label := provider.labels.get(label_name)):
                    continue
                image = provider.images[label.image]
                if (request.image_upload_uuid
                        and image.name in request.image_names):
                    image_cname = image.canonical_name
                    uploads = self.image_upload_registry.getUploadsForImage(
                        image_cname)
                    # Check that the given provider can actually supply
                    # the requested image.
                    valid_uploads = (
                        u for u in uploads
                        if u.uuid == request.image_upload_uuid
                    )
                    if not any(valid_uploads):
                        continue
                # Check if the provider could possibly handle the
                # request based on quota but not current zuul usage.
                # TODO: consider the impact of a multi-node request
                # for the same label where that single request is
                # larger than the capacity.
                try:
                    if not self.doesProviderHaveQuotaForLabel(
                            provider, label, log, include_usage=False):
                        continue
                except Exception:
                    self.log.exception(
                        "Error checking quota for label %s "
                        "in provider %s", label, provider)
                    continue
                ideal_providers_for_label[i].append(provider)
                if (provider_failure_names[provider.canonical_name]
                        >= provider.launch_attempts):
                    continue
                providers_for_label[i].append(provider)
            ideal_providers_for_all_labels &= set(ideal_providers_for_label[i])
            providers_for_all_labels &= set(providers_for_label[i])

        # If there is at least one provider that can provide all the
        # labels for this request, then we will ensure that we use the
        # same provider for all.
        if require_same_provider := bool(ideal_providers_for_all_labels):
            log.debug("Requiring same provider for all labels")

        # Turn the reduced set union of providers that work for all
        # labels back into an ordered list.
        providers_for_all_labels = [
            p for p in providers if p in providers_for_all_labels]

        main_provider_name = None
        main_provider = None
        most_common = existing_provider_names.most_common()
        if most_common:
            main_provider_name = most_common[0][0]
            log.debug("Using most common provider %s from %s",
                      main_provider_name, most_common)
        elif request.preferred_provider:
            main_provider_name = request.preferred_provider
            log.debug("Using requested provider %s", main_provider_name)
        if main_provider_name:
            for main_provider in providers:
                if main_provider.canonical_name == main_provider_name:
                    break
            else:
                raise Exception(
                    f"Unable to find provider {main_provider_name}")
        elif providers_for_all_labels:
            main_provider = providers_for_all_labels[0]
            log.debug("Using first provider for all labels %s from %s",
                      main_provider.canonical_name, providers_for_all_labels)

        label_providers = []
        for i, label_name in enumerate(request.labels):
            if require_same_provider:
                candidate_providers = providers_for_all_labels
            else:
                candidate_providers = providers_for_label[i]
            if not candidate_providers:
                raise NodesetRequestError(
                    f"No provider found for label {label_name}")
            if main_provider in candidate_providers:
                provider = main_provider
                log.debug(
                    "Selected request main provider %s "
                    "for label %s index %s from candidate providers: %s",
                    provider, label_name, i, candidate_providers)
            else:
                provider = candidate_providers[0]
                log.debug(
                    "Selected provider %s "
                    "for label %s index %s from candidate providers: %s",
                    provider, label_name, i, candidate_providers)
            label = provider.labels[label_name]
            label_providers.append((label, provider))

        return label_providers

    def _requestNode(self, label, request, provider, log, ctx):
        # Create a deterministic node UUID by using
        # the request UUID as namespace.
        node_uuid = uuid.uuid4().hex
        image = provider.images[label.image]
        tags = provider.getNodeTags(
            self.system.system_id, label, node_uuid, provider, request)
        node_class = provider.driver.getProviderNodeClass()
        label_quota = provider.getQuotaForLabel(label)
        with trace.use_span(request._span):
            node_span = self.tracer.start_span("ProviderNode")
        span_info = tracing.getSpanInfo(node_span)
        node = node_class.new(
            ctx,
            uuid=node_uuid,
            min_request_version=request.getZKVersion() + 1,
            label=label.name,
            label_config_hash=label.config_hash,
            max_ready_age=label.max_ready_age,
            host_key_checking=label.host_key_checking,
            boot_timeout=label.boot_timeout,
            executor_zone=label.executor_zone,
            request_id=request.uuid,
            zuul_event_id=request.zuul_event_id,
            span_info=span_info,
            connection_name=provider.connection_name,
            tenant_name=request.tenant_name,
            provider=provider.canonical_name,
            tags=tags,
            image_upload_uuid=request.image_upload_uuid,
            # Set any node attributes we already know here
            connection_port=image.connection_port,
            connection_type=image.connection_type,
            quota=label_quota,
        )
        log.debug("Requested node %s", node)
        return node

    def _checkRequest(self, request, log):
        requested_nodes = [self.api.getProviderNode(node_id) for
                           node_id in request.nodes]
        if any(n.state in n.FAILED_STATES for n in requested_nodes):
            # If any nodes failed, see if we need to change providers
            # for any or all of them.
            label_providers = self._selectProviders(request, None, log)
            for i, node in enumerate(requested_nodes):
                label, provider = label_providers[i]
                if (node.state in node.FAILED_STATES or
                    provider.canonical_name != node.provider):
                    # We're either retrying this node or we're
                    # changing providers.
                    log.info(
                        "Retrying node for label %s index %s with provider %s",
                        label, i, provider)
                    with self.createZKContext(request._lock, log) as ctx:
                        if node.state == node.State.FAILED:
                            add_failed_provider = node.provider
                        else:
                            add_failed_provider = None
                        node = self._requestNode(
                            label, request, provider, log, ctx)
                        requested_nodes[i] = node
                        # if this was a tempfail, retry again as
                        # normal; otherwise, add to the failed
                        # providers list in the request
                        with request.activeContext(ctx):
                            request.updateProviderNode(
                                i, node,
                                add_failed_provider=add_failed_provider,
                            )

        if not all(n.state in n.FINAL_STATES for n in requested_nodes):
            return
        log.debug("Request %s nodes ready: %s", request, requested_nodes)
        failed = not all(n.state in model.ProviderNode.State.READY
                         for n in requested_nodes)
        # TODO:
        # * gracefully handle node failures (retry with another connection)
        # * deallocate ready nodes from the request if finally failed

        state = (model.NodesetRequest.State.FAILED if failed
                 else model.NodesetRequest.State.FULFILLED)
        log.debug("Marking request %s as %s", request, state)

        event = model.NodesProvisionedEvent(
            request.uuid, request.buildset_uuid)
        self.result_events[request.tenant_name][request.pipeline_name].put(
            event)

        with self.createZKContext(request._lock, log) as ctx:
            request.updateAttributes(ctx, state=state)

    def _processNodes(self):
        for node in self.api.getMatchingProviderNodes():
            log = get_annotated_logger(self.log, node, request=node.request_id)
            if not node.hasLock():
                if not self._isNodeActionable(node):
                    continue

                with self.createZKContext(None, log) as ctx:
                    if not node.acquireLock(ctx, blocking=False):
                        log.debug("Failed to lock matching node %s", node)
                        continue
                    node.refresh(ctx)

            request = self.api.getNodesetRequest(node.request_id)
            if ((request or node.request_id is None)
                    and node.state in node.CREATE_STATES):
                try:
                    self._checkNode(node, log)
                except exceptions.QuotaException as e:
                    state = node.State.TEMPFAILED
                    log.info("Marking node %s as %s due to %s", node, state, e)
                    with self.createZKContext(node._lock, self.log) as ctx:
                        with node.activeContext(ctx):
                            node.setState(state)
                        self.wake_event.set()
                except Exception as e:
                    state = node.State.FAILED
                    if isinstance(e, LaunchTimeoutError):
                        log.error("Marking node %s as %s", node, state)
                    else:
                        log.exception("Marking node %s as %s", node, state)
                    with self.createZKContext(node._lock, self.log) as ctx:
                        with node.activeContext(ctx):
                            node.setState(state)
                        self.wake_event.set()

                # Export span for node creation phase
                if (node.state in node.FINAL_STATES and
                        node.create_state_machine):
                    with trace.use_span(tracing.restoreSpan(node.span_info)):
                        with self.tracer.start_as_current_span(
                            "ProviderNodeCreate",
                            start_time=node.create_state_machine.start_time,
                            attributes=node.getSpanAttributes()
                        ):
                            # Nothing to do here; ctx manager is just
                            # a shorthand for span start/end. The
                            # start time is dated back to the start
                            # of the create state machine.
                            pass
            # Deallocate ready node w/o a request for re-use
            if (node.request_id and not request
                    and node.state == node.State.READY):
                log.debug("Deallocating ready node %s from missing request %s",
                          node, node.request_id)
                with self.createZKContext(node._lock, self.log) as ctx:
                    node.updateAttributes(
                        ctx,
                        request_id=None,
                        tenant_name=None,
                        provider=None)

            # Mark outdated nodes w/o a request for cleanup when ...
            if not request and (
                    # ... it expired
                    node.hasExpired() or
                    # ... we are sure that our providers are up-to-date
                    # and we can't find a provider for this node.
                    (not self.layout_updated_event.is_set()
                     and not self._hasProvider(node))):
                state = node.State.OUTDATED
                log.debug("Marking node %s as %s", node, state)
                with self.createZKContext(node._lock, self.log) as ctx:
                    with node.activeContext(ctx):
                        node.setState(state)

            # Clean up the node if ...
            if (
                # ... it is associated with a request that no
                # longer exists
                (node.request_id is not None and not request)
                # ... it is failed/outdated
                or node.state in (node.State.FAILED,
                                  node.State.TEMPFAILED,
                                  node.State.OUTDATED)
            ):
                try:
                    self._cleanupNode(node, log)
                except Exception:
                    log.exception("Error in node cleanup")
                    self.wake_event.set()

            if node.state == model.ProviderNode.State.READY:
                with self.createZKContext(None, self.log) as ctx:
                    node.releaseLock(ctx)

    def _isNodeActionable(self, node):
        if node.is_locked:
            return False

        if node.state in node.LAUNCHER_STATES:
            return True

        if node.state == node.State.HOLD:
            if node.hasHoldExpired():
                return True
            return False

        if node.request_id:
            request_exists = bool(self.api.getNodesetRequest(node.request_id))
            return not request_exists
        elif node.hasExpired():
            return True
        elif not self._hasProvider(node):
            if self.layout_updated_event.is_set():
                # If our providers are not up-to-date we can't be sure
                # there is no provider for this node.
                return False
            # We no longer have a provider that uses the given node
            return True

        return False

    def _checkNode(self, node, log):
        with self.createZKContext(node._lock, self.log) as ctx:
            with node.activeContext(ctx):
                provider = self._getProviderForNode(node)
                if not node.create_state_machine:
                    log.debug("Building node %s", node)
                    image_external_id = self.getImageExternalId(node, provider)
                    log.debug("Node %s external id %s",
                              node, image_external_id)
                    node.create_state_machine = provider.getCreateStateMachine(
                        node, image_external_id, log)

                old_state = node.create_state_machine.state
                if old_state == node.create_state_machine.START:
                    if not self.doesProviderHaveQuotaForNode(
                            provider, node, log):
                        # Consider this provider paused, don't attempt
                        # to create the node until we think we have
                        # quota.
                        self.wake_event.set()
                        return
                    # Start the clock for launch-timeout from this point.
                    node.create_state_machine.start_time = time.time()
                instance = node.create_state_machine.advance()
                new_state = node.create_state_machine.state
                if old_state != new_state:
                    log.debug("Node %s advanced from %s to %s",
                              node, old_state, new_state)
                if (new_state != node.create_state_machine.START and
                    node.state == node.State.REQUESTED):
                    # Set state to building so that we start counting
                    # quota.
                    node.setState(node.State.BUILDING)

                if not node.create_state_machine.complete:
                    if provider.launch_timeout:
                        now = time.time()
                        if (now - node.create_state_machine.start_time >
                            provider.launch_timeout):
                            log.error("Timeout creating node %s", node)
                            raise LaunchTimeoutError("Timeout creating node")
                    self.wake_event.set()
                    return
                # Note this method has the side effect of updating
                # node info from the instance.
                if self._checkNodescanRequest(node, instance, log):
                    node.setState(node.State.READY)
                    node.nodescan_request = None
                    self.wake_event.set()
                    log.debug("Marking node %s as %s", node, node.state)
                else:
                    self.wake_event.set()
                    return
            node.releaseLock(ctx)

    def _checkNodescanRequest(self, node, instance, log):
        if node.nodescan_request is None:
            # We just finished the create state machine, update with
            # new info.
            self._updateNodeFromInstance(node, instance)
            node.nodescan_request = NodescanRequest(node, log)
            self.nodescan_worker.addRequest(node.nodescan_request)
            log.debug(
                "Submitted nodescan request for %s queue length %s",
                node.interface_ip,
                self.nodescan_worker.length())
        if not node.nodescan_request.complete:
            return False
        try:
            keys = node.nodescan_request.result()
        except Exception as e:
            if isinstance(e, exceptions.ConnectionTimeoutException):
                log.warning("Error scanning keys: %s", str(e))
            else:
                log.exception("Exception scanning keys:")
            raise exceptions.LaunchKeyscanException(
                "Can't scan key for %s" % (node,))
        if keys:
            node.host_keys = keys
        return True

    def _cleanupNode(self, node, log):
        with self.createZKContext(node._lock, self.log) as ctx:
            with node.activeContext(ctx):
                self.nodescan_worker.removeRequest(node.nodescan_request)
                node.nodescan_request = None

                if not node.delete_state_machine:
                    log.debug("Cleaning up node %s", node)
                    provider = self._getProviderForNode(
                        node, ignore_label=True)
                    node.delete_state_machine = provider.getDeleteStateMachine(
                        node, log)

                old_state = node.delete_state_machine.state

                now = time.time()
                if (now - node.delete_state_machine.start_time >
                    self.DELETE_TIMEOUT):
                    log.error("Timeout deleting node %s", node)
                    node.delete_state_machine.state =\
                        node.delete_state_machine.COMPLETE
                    node.delete_state_machine.complete = True

                if not node.delete_state_machine.complete:
                    try:
                        node.delete_state_machine.advance()
                        new_state = node.delete_state_machine.state
                        if old_state != new_state:
                            log.debug("Node %s advanced from %s to %s",
                                      node, old_state, new_state)
                    except Exception:
                        log.exception("Error in delete state machine:")
                        node.delete_state_machine.state =\
                            node.delete_state_machine.COMPLETE
                        node.delete_state_machine.complete = True

            if not node.delete_state_machine.complete:
                self.wake_event.set()
                return

            request = self.api.getNodesetRequest(node.request_id)
            request_up_to_date = False
            if request is not None:
                request_version = request.getZKVersion()
                if request_version is not None:
                    if request_version >= node.min_request_version:
                        request_up_to_date = True
            if (request is None or
                (request_up_to_date and
                 node.uuid not in request.nodes)):
                # We can clean up the node if:
                # The request is gone
                # The request exists and our copy is sufficiently new and:
                #   The request no longer references this node
                log.debug("Removing provider node %s", node)
                node.delete(ctx)
                node.releaseLock(ctx)
                # Export provider node spans
                node_span = tracing.restoreSpan(node.span_info)
                with trace.use_span(node_span, end_on_exit=True):
                    node_span.set_attributes(node.getSpanAttributes())
                    if node.delete_state_machine:
                        with self.tracer.start_as_current_span(
                            "ProviderNodeDelete",
                            start_time=node.delete_state_machine.start_time,
                            attributes=node.getSpanAttributes()
                        ):
                            # Nothing to do here; ctx manager is just
                            # a shorthand for span start/end. The
                            # start time is dated back to the start
                            # of the create state machine.
                            pass

    def _processMinReady(self):
        if not self.api.nodes_cache.waitForSync(
                timeout=self.CACHE_SYNC_TIMEOUT):
            self.log.warning("Timeout waiting %ss for node cache to sync",
                             self.CACHE_SYNC_TIMEOUT)
            return

        for label, provider in self._getMissingMinReadySlots():
            node_uuid = uuid.uuid4().hex
            # We don't pass a provider here as the node should not
            # be directly associated with a tenant or provider.
            image = provider.images[label.image]
            tags = provider.getNodeTags(
                self.system.system_id, label, node_uuid)
            node_class = provider.driver.getProviderNodeClass()
            with self.createZKContext(None, self.log) as ctx:
                node = node_class.new(
                    ctx,
                    uuid=node_uuid,
                    label=label.name,
                    label_config_hash=label.config_hash,
                    max_ready_age=label.max_ready_age,
                    host_key_checking=label.host_key_checking,
                    boot_timeout=label.boot_timeout,
                    executor_zone=label.executor_zone,
                    request_id=None,
                    connection_name=provider.connection_name,
                    zuul_event_id=uuid.uuid4().hex,
                    tenant_name=None,
                    provider=None,
                    tags=tags,
                    # Set any node attributes we already know here
                    connection_port=image.connection_port,
                    connection_type=image.connection_type,
                )
                self.log.debug("Created min-ready node %s via provider %s",
                               node, provider)

    def _getMissingMinReadySlots(self):
        candidate_launchers = {
            c.hostname: c for c in COMPONENT_REGISTRY.registry.all("launcher")}
        candidate_names = set(candidate_launchers.keys())
        label_scores = DefaultKeyDict(
            lambda lcn: scores_for_label(lcn, candidate_names))

        # Collect min-ready labels that we need to process
        tenant_labels = collections.defaultdict(
            lambda: collections.defaultdict(list))
        for tenant_name, tenant_providers in self.tenant_providers.items():
            for tenant_provider in tenant_providers:
                for label in tenant_provider.labels.values():
                    if not label.min_ready:
                        continue
                    # Check if this launcher is responsible for
                    # spawning min-ready nodes for this label.
                    if not self._hasHighestMinReadyScore(
                            label.canonical_name,
                            label_scores,
                            candidate_launchers):
                        continue
                    # We collect all label variants to determin if
                    # min-ready is satisfied based on the config hashes
                    tenant_labels[tenant_name][label.name].append(label)

        unassigned_hashes = self._getUnassignedNodeLabelHashes()
        for tenant_name, min_ready_labels in tenant_labels.items():
            for label_name, labels in min_ready_labels.items():
                valid_label_hashes = set(lbl.config_hash for lbl in labels)
                tenant_min_ready = sum(
                    1 for h in unassigned_hashes[label_name]
                    if h in valid_label_hashes
                )
                label_providers = [
                    p for p in self.tenant_providers[tenant_name]
                    if p.hasLabel(label_name)
                ]
                for _ in range(tenant_min_ready, labels[0].min_ready):
                    provider = random.choice(label_providers)
                    label = provider.labels[label_name]
                    yield label, provider
                    unassigned_hashes[label.name].append(label.config_hash)

    def _hasHighestMinReadyScore(
            self, label_cname, label_scores, candidate_launchers):
        scores = sorted(label_scores[label_cname].items())
        for score, launcher_name in scores:
            launcher = candidate_launchers.get(launcher_name)
            if not launcher:
                continue
            if launcher.state != launcher.RUNNING:
                continue
            if (launcher.hostname
                    == self.component_info.hostname):
                return True
            return False
        return False

    def _getUnassignedNodeLabelHashes(self):
        ready_nodes = collections.defaultdict(list)
        for node in self.api.getProviderNodes():
            if node.request_id is not None:
                continue
            ready_nodes[node.label].append(node.label_config_hash)
        return ready_nodes

    def _getUnassignedReadyNodes(self):
        ready_nodes = collections.defaultdict(list)
        for node in self.api.getProviderNodes():
            if node.request_id is not None:
                continue
            if node.is_locked or node.state != node.State.READY:
                continue
            ready_nodes[node.label].append(node)
        return ready_nodes

    def _getProviderForNode(self, node, ignore_label=False):
        # Common case when a node is assigned to a provider
        if node.provider:
            return self._getProviderByCanonicalName(node.provider)

        # Fallback for min-ready nodes w/o a assigned provider
        for provider in self._getProviders():
            if provider.connection_name != node.connection_name:
                continue
            if ignore_label:
                return provider
            if not (label := provider.labels.get(node.label)):
                continue
            if label.config_hash == node.label_config_hash:
                return provider
        raise ProviderNodeError(f"Unable to find provider for node {node}")

    def _updateNodeFromInstance(self, node, instance):
        if instance is None:
            return

        # TODO:
        # if (pool.use_internal_ip and
        #     (instance.private_ipv4 or instance.private_ipv6)):
        #     server_ip = instance.private_ipv4 or instance.private_ipv6
        # else:
        server_ip = instance.interface_ip

        node.interface_ip = server_ip
        node.public_ipv4 = instance.public_ipv4
        node.private_ipv4 = instance.private_ipv4
        node.public_ipv6 = instance.public_ipv6
        node.private_ipv6 = instance.private_ipv6
        node.host_id = instance.host_id
        node.cloud = instance.cloud
        node.region = instance.region
        node.az = instance.az
        node.driver_data = instance.driver_data
        node.slot = instance.slot

        # If we did not know the resource information before
        # launching, update it now.
        node.quota = instance.getQuotaInformation()

        # Optionally, if the node has updated values that we set from
        # the image attributes earlier, set those.
        for attr in ('username', 'python_path', 'shell_type',
                     'connection_port', 'connection_type',
                     'host_keys'):
            if hasattr(instance, attr):
                setattr(node, attr, getattr(instance, attr))

        # As a special case for metastatic, if we got node_attributes
        # from the backing driver, use them as default values and let
        # the values from the pool override.
        instance_node_attrs = getattr(instance, 'node_attributes', None)
        if instance_node_attrs is not None:
            attrs = instance_node_attrs.copy()
            if node.attributes:
                attrs.update(node.attributes)
            node.attributes = attrs

    def _getProvider(self, tenant_name, provider_name):
        for provider in self.tenant_providers[tenant_name]:
            if provider.name == provider_name:
                return provider
        raise ProviderNodeError(
            f"Unable to find {provider_name} in tenant {tenant_name}")

    def _getProviders(self):
        # The same provider can behave differently in different
        # tenants because, for example, different image definitions
        # may appear in the different tenants.  This method will
        # return all of the providers.
        for providers in self.tenant_providers.values():
            for provider in providers:
                yield provider

    def _getUniqueProviders(self):
        # Sometimes (eg, when generating stats) we may not care about
        # the differences between the same provider in different
        # tenants.  This returns unique providers.
        seen = set()
        for providers in self.tenant_providers.values():
            for provider in providers:
                if provider.canonical_name not in seen:
                    yield provider
                    seen.add(provider.canonical_name)

    def _hasProvider(self, node):
        try:
            self._getProviderForNode(node)
        except ProviderNodeError:
            return False
        return True

    def _getProviderByCanonicalName(self, provider_cname):
        # Note this scans all tenants, and identical providers in
        # different tenants may have different python objects, so only
        # use this method if the call site doesn't care which
        # tenant-provider object is returned.
        for tenant_providers in self.tenant_providers.values():
            for provider in tenant_providers:
                if provider.canonical_name == provider_cname:
                    return provider
        raise Exception(f"Unable to find {provider_cname}")

    def start(self):
        self.log.debug("Starting command processor")
        self._command_running = True
        self.command_socket.start()
        self.command_thread = threading.Thread(
            target=self.runCommand, name="command")
        self.command_thread.daemon = True
        self.command_thread.start()

        self.log.debug("Starting nodescan worker")
        self.nodescan_worker.start()

        self.log.debug("Starting launcher thread")
        self.launcher_thread.start()

        if self._start_cleanup:
            self.log.debug("Starting cleanup thread")
            self.cleanup_worker.start()

        self.stats_thread.start()

    def stop(self):
        self.log.debug("Stopping launcher")
        self._running = False
        self.stop_event.set()
        self.wake_event.set()
        self.component_info.state = self.component_info.STOPPED
        self.stopRepl()
        self._command_running = False
        self.command_socket.stop()
        self.log.debug("Stopping stats thread")
        self.stats_election.cancel()
        self.stats_thread.join()
        self.cleanup_worker.stop()
        self.cleanup_worker.join()
        self.upload_executor.shutdown()
        self.endpoint_upload_executor.shutdown()
        self.nodescan_worker.stop()
        self.connections.stop()
        self.monitoring_server.stop()
        # Endpoints are stopped by drivers
        self.log.debug("Stopped launcher")

    def join(self):
        self.log.debug("Joining launcher")
        self.launcher_thread.join()
        # Don't set the join event until after the main thread is
        # joined because doing so will terminate the ZKContext.
        self.join_event.set()
        self.api.stop()
        self.zk_client.disconnect()
        self.tracing.stop()
        self.nodescan_worker.join()
        self.monitoring_server.join()
        self.log.debug("Joined launcher")

    def runCommand(self):
        while self._command_running:
            try:
                command, args = self.command_socket.get()
                if command != '_stop':
                    self.command_map[command](*args)
            except Exception:
                self.log.exception("Exception while processing command")

    def startRepl(self):
        if self.repl:
            return
        self.repl = zuul.lib.repl.REPLServer(self)
        self.repl.start()

    def stopRepl(self):
        if not self.repl:
            return
        self.repl.stop()
        self.repl = None

    def createZKContext(self, lock, log):
        return ZKContext(self.zk_client, lock, self.join_event, log,
                         default_lock_identifier=self.component_info.hostname)

    def updateTenantProviders(self):
        # We need to handle new and deleted tenants, so we need to
        # process all tenants currently known and the new ones.
        tenant_names = set(self.tenant_providers.keys())
        tenant_names.update(self.tenant_layout_state)

        endpoints = {}
        updated = False
        for tenant_name in tenant_names:
            # Reload the tenant if the layout changed.
            if self._updateTenantProviders(tenant_name):
                updated = True

        if updated:
            for providers in self.tenant_providers.values():
                for provider in providers:
                    if (self.connection_filter and
                        provider.connection_name not in
                        self.connection_filter):
                        continue
                    endpoint = provider.getEndpoint()
                    endpoints[endpoint.canonical_name] = endpoint
                    endpoint.start()
                    endpoint.postConfig(provider)
            self.endpoints = endpoints
        return updated

    def _updateTenantProviders(self, tenant_name):
        # Reload the tenant if the layout changed.
        updated = False
        if (self.local_layout_state.get(tenant_name)
                == self.tenant_layout_state.get(tenant_name)):
            return updated
        self.log.debug("Updating tenant %s", tenant_name)
        with tenant_read_lock(self.zk_client, tenant_name, self.log) as tlock:
            layout_state = self.tenant_layout_state.get(tenant_name)

            if layout_state:
                with self.createZKContext(tlock, self.log) as context:
                    providers = list(self.layout_providers_store.get(
                        context, tenant_name))
                    self.tenant_providers[tenant_name] = providers
                    for provider in providers:
                        self.log.debug("Loaded provider %s", provider.name)
                self.local_layout_state[tenant_name] = layout_state
                updated = True
            else:
                self.tenant_providers.pop(tenant_name, None)
                self.local_layout_state.pop(tenant_name, None)
        return updated

    def addImageBuildEvent(self, tenant_name, project_canonical_name,
                           branch, image_names):
        project_hostname, project_name = \
            project_canonical_name.split('/', 1)
        driver = self.connections.drivers['zuul']
        event = driver.getImageBuildEvent(
            list(image_names), project_hostname, project_name, branch)
        self.log.info("Submitting image build event for %s %s",
                      tenant_name, image_names)
        self.trigger_events[tenant_name].put(event.trigger_name, event)

    def addImageValidateEvent(self, image_upload):
        iba = self.image_build_registry.getItem(image_upload.artifact_uuid)
        project_hostname, project_name = \
            iba.project_canonical_name.split('/', 1)
        tenant_name = iba.build_tenant_name
        driver = self.connections.drivers['zuul']
        event = driver.getImageValidateEvent(
            [iba.name], project_hostname, project_name, iba.project_branch,
            image_upload.uuid)
        self.log.info("Submitting image validate event for %s %s",
                      tenant_name, iba.name)
        self.trigger_events[tenant_name].put(event.trigger_name, event)

    def addImageDeleteEvent(self, iba):
        project_hostname, project_name = \
            iba.project_canonical_name.split('/', 1)
        tenant_name = iba.build_tenant_name
        driver = self.connections.drivers['zuul']
        event = driver.getImageDeleteEvent(
            [iba.name], project_hostname, project_name, iba.project_branch,
            iba.uuid)
        self.log.info("Submitting image delete event for %s %s",
                      tenant_name, iba.name)
        self.trigger_events[tenant_name].put(event.trigger_name, event)

    def _waitForStableImageRegistry(self):
        # Wait for any non-ready IBAs to become ready.  This resolves
        # a race condition where the scheduler might have created the
        # first of more than one IBA in a buildset, and we were
        # immediately triggered.  Wait until the scheduler is finished
        # so that if a buildset creates more than one IBA we have all
        # the info.
        now = time.time()
        while True:
            done = True
            for iba in self.image_build_registry.getAllArtifacts():
                if iba.state is not None:
                    continue
                if now - iba.timestamp > 30:
                    # We'll only wait 30 seconds for this so we don't
                    # get stuck.
                    continue
                done = False
                break
            if done:
                return
            time.sleep(1)

    def checkMissingImages(self):
        self.log.debug("Checking for missing images")
        self._waitForStableImageRegistry()
        for tenant_name, providers in self.tenant_providers.items():
            images_by_project_branch = {}
            for provider in providers:
                for image in provider.images.values():
                    if image.type == 'zuul':
                        self.checkMissingImage(tenant_name, image,
                                               images_by_project_branch)
            for ((project_canonical_name, branch), image_names) in \
                images_by_project_branch.items():
                self.addImageBuildEvent(tenant_name, project_canonical_name,
                                        branch, image_names)
        self.log.debug("Done checking for missing images")

    def checkMissingImage(self, tenant_name, image, images_by_project_branch):
        # If there is already a successful build for
        # this image, skip.
        seen_formats = set()
        for iba in self.image_build_registry.getArtifactsForImage(
                image.canonical_name):
            seen_formats.add(iba.format)

        if image.format in seen_formats:
            # We have at least one build with the required
            # formats
            return

        self.log.debug("Missing format %s for image %s",
                       image.format, image.canonical_name)
        # Collect images with the same project-branch so we can build
        # them in one buildset.
        key = (image.project_canonical_name, image.branch)
        images = images_by_project_branch.setdefault(key, set())
        images.add(image.name)

    def checkOldImages(self):
        self.log.debug("Checking for old images")
        self.upload_deleted_event.clear()
        keep_uploads = set()
        known_uploads = set(self.image_upload_registry.getItems())
        known_providers = set()
        for tenant_name, providers in self.tenant_providers.items():
            for provider in providers:
                known_providers.add(provider.canonical_name)
                for image in provider.images.values():
                    if image.type == 'zuul':
                        self.checkOldImage(tenant_name, provider, image,
                                           keep_uploads)

        # Get the list of ibas for which we could consider uploads
        # first (to make sure that we don't race the creation of
        # uploads and setting the iba to ready).
        active_ibas = [iba for iba in self.image_build_registry.getItems()
                       if iba.state in
                       (iba.State.DELETING, iba.State.READY)]

        uploads_by_artifact = collections.defaultdict(list)
        latest_upload_timestamp = 0
        for upload in known_uploads:
            if upload.timestamp > latest_upload_timestamp:
                latest_upload_timestamp = upload.timestamp
            uploads_by_artifact[upload.artifact_uuid].append(upload)
            iba = self.image_build_registry.getItem(upload.artifact_uuid)
            if not iba:
                self.log.warning("Unable to find artifact for upload %s",
                                 upload.artifact_uuid)
                continue
            if set(upload.providers).isdisjoint(known_providers):
                # An orphaned upload means that either
                # a) the provider was removed without following the
                #    provider removal procedure (clear out images before
                #    deleting the provider)
                # or
                # b) that we could not load the provider e.g. due to a
                #    config error.
                # In both cases we want to keep the uploads in case the
                # provider shows up again.
                self.log.warning(
                    "Keeping orphaned upload %s with unknown providers %s",
                    upload, upload.providers)
                continue
            if (iba.state == iba.State.DELETING or
                upload.state == upload.State.DELETING or
                upload not in keep_uploads):
                self.upload_executor.submit(DeleteJob(self, iba, upload).run)
        for iba in active_ibas:
            if (iba.timestamp > latest_upload_timestamp or
                not latest_upload_timestamp):
                # Ignore artifacts that are newer than the newest upload
                continue
            if len(uploads_by_artifact[iba.uuid]) == 0:
                self.log.info("Deleting image build artifact "
                              "with no uploads: %s", iba)
                with self.createZKContext(None, self.log) as ctx:
                    try:
                        with iba.locked(ctx, blocking=False):
                            iba.delete(ctx)
                    except LockException:
                        pass

    def checkOldImage(self, tenant_name, provider, image,
                      keep_uploads):
        image_cname = image.canonical_name
        uploads = self.image_upload_registry.getUploadsForImage(image_cname)
        valid_uploads = [
            upload for upload in uploads
            if (upload.isPermittedForProvider(image, provider) and
                upload.state == upload.State.READY and
                upload.validated and
                upload.external_id)
        ]
        # Keep the 2 most recent validated uploads (uploads are
        # already sorted by timestamp)
        newest_valid_uploads = valid_uploads[-2:]
        keep_uploads.update(set(newest_valid_uploads))
        # And also keep any uploads (regardless of validation) newer
        # than that (since they may have validation jobs running).
        if newest_valid_uploads:
            oldest_good_timestamp = newest_valid_uploads[0].timestamp
        else:
            oldest_good_timestamp = 0
        new_uploads = [
            upload for upload in uploads
            if (upload.isPermittedForProvider(image, provider) and
                upload.timestamp > oldest_good_timestamp)
        ]
        keep_uploads.update(set(new_uploads))

    def checkMissingUploads(self):
        self.log.debug("Checking for missing uploads")
        uploads_by_artifact_id = collections.defaultdict(list)
        self.image_updated_event.clear()
        for upload in self.image_upload_registry.getItems():
            if upload.uuid in self.upload_uuids_in_queue:
                continue
            if upload.endpoint_name not in self.endpoints:
                continue
            iba = self.image_build_registry.getItem(upload.artifact_uuid)
            if not iba:
                self.log.warning("Unable to find artifact for upload %s",
                                 upload.artifact_uuid)
                continue
            if iba.state == iba.State.DELETING:
                continue
            if upload.state == upload.State.UPLOADING:
                # If there is an unlocked upload in uploading state,
                # it has probably crashed.  Reset it.
                if not upload.is_locked:
                    with self.createZKContext(None, self.log) as ctx:
                        try:
                            with upload.locked(ctx, blocking=False):
                                # Double check the state after lock.
                                upload.refresh(ctx)
                                if upload.state == upload.State.UPLOADING:
                                    with upload.activeContext(ctx):
                                        upload.state = upload.State.PENDING
                        except LockException:
                            # Upload locked again (lock / cache update race)
                            pass
            if upload.state != upload.State.PENDING:
                continue
            upload_list = uploads_by_artifact_id[upload.artifact_uuid]
            upload_list.append(upload)

        for artifact_uuid, uploads in uploads_by_artifact_id.items():
            iba = self.image_build_registry.getItem(artifact_uuid)
            for upload in uploads:
                self.upload_uuids_in_queue.add(upload.uuid)
            self.upload_executor.submit(UploadJob(self, iba, uploads).run)

    def _downloadArtifactChunk(self, url, start, end, path):
        headers = {'Range': f'bytes={start}-{end}'}
        with open(path, 'r+b') as f:
            f.seek(start)
            with requests.get(url, stream=True, headers=headers) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=DOWNLOAD_BLOCK_SIZE):
                    f.write(chunk)

    def downloadArtifact(self, url, path):
        futures = []
        with requests.head(url) as resp:
            if resp.status_code == 403:
                self.log.debug(
                    "Received 403 for %s, retrying with range header", url)
                # This may be a pre-signed url that can't handle a
                # HEAD request, retry with GET:
                with requests.get(url,
                                  headers={"Range": "bytes=0-0"}) as resp:
                    resp.raise_for_status()
                    size = int(resp.headers['content-range'].split('/')[-1])
            else:
                resp.raise_for_status()
                size = int(resp.headers['content-length'])
        self.log.debug("Creating %s with size %s", path, size)
        with open(path, 'wb') as f:
            f.truncate(size)
        try:
            with ThreadPoolExecutor(max_workers=5) as executor:
                for start in range(0, size, DOWNLOAD_CHUNK_SIZE):
                    end = start + DOWNLOAD_CHUNK_SIZE - 1
                    futures.append(executor.submit(self._downloadArtifactChunk,
                                                   url,
                                                   start, end, path))
                for future in concurrent.futures.as_completed(futures):
                    future.result()
        except Exception:
            # If we encountered a problem, delete the file so it isn't
            # orphaned.
            if os.path.exists(path):
                os.unlink(path)
                self.log.info("Deleted %s", path)
            raise
        self.log.debug("Downloaded %s bytes to %s", size, path)
        return path

    def getImageExternalId(self, node, provider):
        label = provider.labels[node.label]
        image = provider.images[label.image]
        if image.type != 'zuul':
            return None
        image_cname = image.canonical_name
        uploads = self.image_upload_registry.getUploadsForImage(image_cname)
        if node.image_upload_uuid:
            valid_uploads = [
                u for u in uploads if u.uuid == node.image_upload_uuid
            ]
        else:
            valid_uploads = [
                upload for upload in uploads
                if (upload.isPermittedForProvider(image, provider) and
                    upload.validated and
                    upload.external_id)
            ]
        if not valid_uploads:
            raise Exception("No image found")
        # Uploads are already sorted by timestamp
        image_upload = valid_uploads[-1]
        return image_upload.external_id

    def getQuotaUsed(self, provider, include_requested):
        used = model.QuotaInformation()
        states = model.ProviderNode.ALLOCATED_STATES
        if include_requested:
            states = states + (model.ProviderNode.State.REQUESTED,)
        for node in self.api.getProviderNodes():
            if (provider.canonical_name == node.provider and
                node.state in states):
                used.add(node.quota)
        return used

    def getUnmanagedQuotaUsed(self, provider):
        used = model.QuotaInformation()

        node_ids = [n.uuid for n in self.api.nodes_cache.getItems()]
        endpoint = provider.getEndpoint()
        system_id = self.system.system_id
        for instance in endpoint.listInstances():
            meta = instance.metadata
            if (meta.get('zuul_system_id') == system_id and
                meta.get('zuul_node_uuid') in node_ids):
                continue
            used.add(instance.getQuotaInformation())
        return used

    def getProviderQuota(self, provider):
        val = self._provider_quota_cache.get(provider.canonical_name)
        if val:
            return val

        # This is initialized with the full tenant quota and later becomes
        # the quota available for nodepool.
        quota = provider.getQuotaLimits()
        self.log.debug("Provider quota for %s: %s",
                       provider.name, quota)

        self._provider_quota_cache[provider.canonical_name] = quota
        return quota

    def getProviderQuotaAvailable(self, provider):
        val = self._provider_available_cache.get(provider.canonical_name)
        if val:
            return val

        # This is initialized with the full tenant quota and later becomes
        # the quota available for nodepool.
        quota = self.getProviderQuota(provider).copy()
        unmanaged = self.getUnmanagedQuotaUsed(provider)
        self.log.debug("Provider unmanaged quota used for %s: %s",
                       provider.name, unmanaged)

        # Subtract the unmanaged quota usage from nodepool_max
        # to get the quota available for us.
        quota.subtract(unmanaged)
        self._provider_available_cache[provider.canonical_name] = quota
        return quota

    def getQuotaPercentage(self, provider):
        # This is cached and updated every 5 minutes
        try:
            total = self.getProviderQuotaAvailable(provider).copy()
        except Exception:
            self.log.exception("Unable to get provider quota")
            # If there is an error getting quota information, assume
            # the provider is having problems and report it as full.
            return 1.0
        # This is continuously updated in the background
        used = self.api.nodes_cache.getQuota(provider)
        pct = 0.0
        for resource in total.quota.keys():
            used_r = used.quota.get(resource, used.default)
            total_r = total.quota[resource]
            if not total_r:
                pct = 1.0
                break
            else:
                pct = max(used_r / total_r, pct)
        if pct < 1.0:
            # If we are below 100% usage, lose precision so that we only
            # consider 10% gradiations.  This may help us avoid
            # thundering herds by allowing some randomization among
            # launchers that are within 10% of each other.

            # Over 100% use the exact value so that we always assign
            # to the launcher with the smallest backlog.
            pct = round(pct, 1)
        return pct

    def doesProviderHaveQuotaForLabel(self, provider, label, log,
                                      include_usage=True):
        if include_usage:
            total = self.getProviderQuotaAvailable(provider).copy()
            log.debug("Provider %s quota available before Zuul: %s",
                      provider, total)
            # We include requested nodes here because this is called
            # to decide whether to add a new request to the provider,
            # so we should include other nodes we've already allocated
            # to this provider in the decision.
            total.subtract(self.getQuotaUsed(provider, include_requested=True))
            log.debug("Provider %s quota available including Zuul: %s",
                      provider, total)
        else:
            total = self.getProviderQuota(provider).copy()
            log.debug("Provider %s quota before Zuul: %s", provider, total)

        label_quota = provider.getQuotaForLabel(label)
        total.subtract(label_quota)
        log.debug("Label %s required quota: %s", label, label_quota)
        return total.nonNegative()

    def doesProviderHaveQuotaForNode(self, provider, node, log):
        total = self.getProviderQuotaAvailable(provider).copy()
        log.debug("Provider %s quota before Zuul: %s", provider, total)
        # We do not include requested nodes here because this is
        # called to decide whether to issue the create API call for a
        # node already allocated to the provider.  We only want to
        # "pause" the provider if it really is at quota.
        total.subtract(self.getQuotaUsed(provider, include_requested=False))
        log.debug("Provider %s quota including Zuul: %s", provider, total)
        total.subtract(node.quota)
        log.debug("Node %s required quota: %s", node, node.quota)
        return total.nonNegative()

    def runStatsElection(self):
        while self._running:
            try:
                self.log.debug("Running stats election")
                self.stats_election.run(self.runStats)
            except Exception:
                self.log.exception("Exception running election stats:")
                time.sleep(1)

    def runStats(self):
        self.log.debug("Won stats election")
        while not self.stop_event.wait(self._stats_interval):
            if not self.stats_election.is_still_valid():
                self.log.debug("Stats election no longer valid")
                return
            try:
                self._runStats()
            except Exception:
                self.log.exception("Error in periodic stats:")

    def _runStats(self):
        if not self.statsd:
            return

        node_defaults = {}
        for state in model.ProviderNode.State:
            node_defaults[state] = 0

        nodes = node_defaults.copy()
        provider_nodes = collections.defaultdict(
            lambda: node_defaults.copy())
        provider_label_nodes = collections.defaultdict(
            lambda: collections.defaultdict(
                lambda: node_defaults.copy()))

        for node in self.api.nodes_cache.getItems():
            nodes[node.state] += 1
            if node.provider:
                provider_nodes[node.provider][node.state] += 1
                provider_label_nodes[node.provider][node.label][
                    node.state] += 1
            else:
                for provider in self._getUniqueProviders():
                    if node.isPermittedForProvider(provider):
                        provider_nodes[provider.canonical_name][
                            node.state] += 1
                        provider_label_nodes[
                            provider.canonical_name][node.label][
                                node.state] += 1

        requests = {}
        for state in model.NodesetRequest.State:
            requests[state] = 0
        for request in self.api.requests_cache.getItems():
            if request.state != request.State.TEST_HOLD:
                requests[request.state] += 1

        providers = {}
        for tenant_name, tenant_providers in self.tenant_providers.items():
            for tenant_provider in tenant_providers:
                providers[tenant_provider.canonical_name] = tenant_provider
        for provider in providers.values():
            safe_pname = normalize_statsd_name(provider.canonical_name)
            limits = self.getProviderQuota(provider).getResources()
            # zuul.provider.<provider>.limit.<resource> gauge
            for res, value in limits.items():
                safe_res = normalize_statsd_name(res)
                self.statsd.gauge(
                    f'zuul.provider.{safe_pname}.limit.{safe_res}',
                    value)
            usage = self.api.nodes_cache.getQuota(provider).getResources()
            for res, value in usage.items():
                safe_res = normalize_statsd_name(res)
                self.statsd.gauge(
                    f'zuul.provider.{safe_pname}.usage.{safe_res}',
                    value)
            # zuul.provider.<provider>.nodes.state.<state> gauge
            for state, value in provider_nodes[
                    provider.canonical_name].items():
                self.statsd.gauge(
                    f'zuul.provider.{safe_pname}.nodes.state.{state.value}',
                    value)
            # zuul.provider.<provider>.label.<label>.nodes.state.<state> gauge
            for label, label_nodes in provider_label_nodes[
                    provider.canonical_name].items():
                safe_label = normalize_statsd_name(label)
                for state, value in label_nodes.items():
                    self.statsd.gauge(
                        f'zuul.provider.{safe_pname}.label.{safe_label}.'
                        f'nodes.state.{state.value}',
                        value)
        # zuul.nodes.state.<state> gauge
        for state, value in nodes.items():
            self.statsd.gauge(
                f'zuul.nodes.state.{state.value}',
                value)
        # zuul.nodeset_requests.state.<state> gauge
        for state, value in requests.items():
            self.statsd.gauge(
                f'zuul.nodeset_requests.state.{state.value}',
                value)
