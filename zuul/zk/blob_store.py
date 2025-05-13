# Copyright 2020 BMW Group
# Copyright 2022, 2024 Acme Gating, LLC
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

import hashlib
import time
import zlib

from kazoo.exceptions import NoNodeError, NotEmptyError
from kazoo.retry import KazooRetry

from zuul.zk.locks import locked, SessionAwareLock
from zuul.zk.zkobject import LocalZKContext, ZKContext
from zuul.zk import sharding


class BlobStore:
    _retry_interval = 5
    lock_grace_period = 300
    data_root = "/zuul/cache/blob/data"
    lock_root = "/zuul/cache/blob/lock"

    def __init__(self, context):
        self.context = context

    def _getRootPath(self, key):
        return f"{self.data_root}/{key[0:2]}/{key}"

    def _getPath(self, key):
        root = self._getRootPath(key)
        return f"{root}/data"

    def _getFlagPath(self, key):
        root = self._getRootPath(key)
        return f"{root}/complete"

    def _getLockPath(self, key):
        return f"{self.lock_root}/{key}"

    def _retry(self, context, func, *args, max_tries=-1, **kw):
        kazoo_retry = KazooRetry(max_tries=max_tries,
                                 interrupt=context.shouldAbortRetry,
                                 delay=self._retry_interval, backoff=0,
                                 ignore_expire=False)
        try:
            return kazoo_retry(func, *args, **kw)
        except InterruptedError:
            pass

    @staticmethod
    def _retryableLoad(context, key, path, flag):
        if not context.client.exists(flag):
            raise KeyError(key)
        with sharding.BufferedShardReader(context.client, path) as stream:
            data = zlib.decompress(stream.read())
            context.cumulative_read_time += stream.cumulative_read_time
            context.cumulative_read_objects += 1
            context.cumulative_read_znodes += stream.znodes_read
            context.cumulative_read_bytes += stream.bytes_read
        return data, stream.bytes_read

    def get(self, key):
        path = self._getPath(key)
        flag = self._getFlagPath(key)

        if self.context.sessionIsInvalid():
            raise Exception("ZooKeeper session or lock not valid")

        data, compressed_size = self._retry(self.context, self._retryableLoad,
                                            self.context, key, path, flag)
        return data

    def _checkKey(self, key):
        # This returns whether the key is in the store.  If it is in
        # the store, it also touches the flag file so that the cleanup
        # routine can know the last time an entry was used.  Because
        # of the critical section between the get and delete calls in
        # the delete method, this must be called with the key lock.
        flag = self._getFlagPath(key)

        if self.context.sessionIsInvalid():
            raise Exception("ZooKeeper session or lock not valid")

        ret = self._retry(self.context, self.context.client.exists,
                          flag)
        if not ret:
            return False
        self._retry(self.context, self.context.client.set,
                    flag, b'')
        return True

    @staticmethod
    def _retryableSave(context, path, flag, data):
        with sharding.BufferedShardWriter(context.client, path) as stream:
            stream.truncate(0)
            stream.write(zlib.compress(data))
            stream.flush()
            context.client.ensure_path(flag)
            context.cumulative_write_time += stream.cumulative_write_time
            context.cumulative_write_objects += 1
            context.cumulative_write_znodes += stream.znodes_written
            context.cumulative_write_bytes += stream.bytes_written
        return stream.bytes_written

    def put(self, data):
        if isinstance(self.context, LocalZKContext):
            return None

        if self.context.sessionIsInvalid():
            raise Exception("ZooKeeper session or lock not valid")

        hasher = hashlib.sha256()
        hasher.update(data)
        key = hasher.hexdigest()

        path = self._getPath(key)
        flag = self._getFlagPath(key)
        lock_path = self._getLockPath(key)
        with locked(
                SessionAwareLock(
                    self.context.client,
                    lock_path),
                blocking=True
        ) as lock:
            if self._checkKey(key):
                return key

            # make a new context based on the old one
            with ZKContext(self.context.client, lock,
                           self.context.stop_event,
                           self.context.log) as locked_context:
                self._retry(
                    locked_context,
                    self._retryableSave,
                    locked_context, path, flag, data)
                self.context.updateStatsFromOtherContext(locked_context)
        return key

    def delete(self, key, ltime):
        path = self._getRootPath(key)
        flag = self._getFlagPath(key)
        lock_path = self._getLockPath(key)
        if self.context.sessionIsInvalid():
            raise Exception("ZooKeeper session or lock not valid")
        deleted = False
        try:
            with locked(
                    SessionAwareLock(
                        self.context.client,
                        lock_path),
                    blocking=True
            ) as lock:
                # make a new context based on the old one
                with ZKContext(self.context.client, lock,
                               self.context.stop_event,
                               self.context.log) as locked_context:

                    # Double check that it hasn't been used since we
                    # decided to delete it
                    data, zstat = self._retry(locked_context,
                                              self.context.client.get,
                                              flag)
                    if zstat.last_modified_transaction_id < ltime:
                        self._retry(locked_context, self.context.client.delete,
                                    path, recursive=True)
                        deleted = True
        except NoNodeError:
            raise KeyError(key)
        if deleted:
            try:
                lock_path = self._getLockPath(key)
                self._retry(self.context, self.context.client.delete,
                            lock_path)
            except Exception:
                self.context.log.exception(
                    "Error deleting lock path %s:", lock_path)

    def __iter__(self):
        try:
            hashdirs = self.context.client.get_children(self.data_root)
        except NoNodeError:
            return

        for hashdir in hashdirs:
            try:
                for key in self.context.client.get_children(
                        f'{self.data_root}/{hashdir}'):
                    yield key
            except NoNodeError:
                pass

    def __len__(self):
        return len([x for x in self])

    def getKeysLastUsedBefore(self, ltime):
        ret = set()
        for key in self:
            flag = self._getFlagPath(key)
            data, zstat = self._retry(self.context, self.context.client.get,
                                      flag)
            if zstat.last_modified_transaction_id < ltime:
                ret.add(key)
        return ret

    def cleanupLockDirs(self, start_ltime, live_blobs):
        # This cleanup was not present in an earlier version of Zuul,
        # therefore lock directory entries could grow without bound.
        # If there are too many entries, we won't be able to list them
        # in order to delete them and the connection will be closed.
        # Before we proceed, make sure that isn't the case here.
        # The size of the packet will be:
        # (num_children * (hash_length + int_size))
        # (num_children * (64 + 4)) = num_children * 68
        max_children = sharding.NODE_BYTE_SIZE_LIMIT / 68
        zstat = self._retry(self.context, self.context.client.exists,
                            self.lock_root)
        if not zstat:
            # Lock root does not exist
            return
        if zstat.children_count > max_children:
            self.context.log.error(
                "Unable to cleanup blob store lock directory "
                "due to too many lock znodes.")
            return

        # We're not retrying here just in case we calculate wrong and
        # we get a ZK disconnection.  We could change this in the
        # future when we're no longer worried about the number of
        # children.
        keys = self.context.client.get_children(self.lock_root)
        for key in keys:
            if key in live_blobs:
                # No need to check a live blob
                continue
            path = self._getLockPath(key)
            zstat = self._retry(self.context, self.context.client.exists,
                                path)
            if not zstat:
                continue
            # Any lock dir that is not for a live blob is either:
            # 1) leaked
            #    created time will be old, okay to delete
            # 2) is for a newly created blob
            #    created time will be new, not okay to delete
            # 3) is for a previously used blob about to be re-created
            #    created time will be old, not okay to delete
            # We can not detect case 3, but it is unlikely to happen,
            # and if it does, the locked context manager in the put
            # method will recreate the lock directory after we delete
            # it.
            now = time.time()
            if ((zstat.created > now - self.lock_grace_period) or
                (zstat.creation_transaction_id > start_ltime)):
                # The lock was recently created, we may have caught it
                # while it's being created.
                continue
            try:
                self.context.log.debug("Deleting unused key dir: %s", path)
                self.context.client.delete(path)
            except NotEmptyError:
                # It may still be in use
                pass
            except NoNodeError:
                pass
            except Exception:
                self.context.log.exception(
                    "Error deleting lock path %s:", path)

    def cleanup(self, start_ltime, live_blobs):
        # get the set of blob keys unused since the start time
        # (ie, we have already filtered any newly added keys)
        unused_blobs = self.getKeysLastUsedBefore(start_ltime)
        # remove the current refences
        unused_blobs -= live_blobs
        # delete what's left
        for key in unused_blobs:
            self.context.log.debug("Deleting unused blob: %s", key)
            self.delete(key, start_ltime)
        self.cleanupLockDirs(start_ltime, live_blobs)
