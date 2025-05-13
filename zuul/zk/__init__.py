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
import logging
import time
from abc import ABCMeta
from configparser import ConfigParser
from threading import Thread
from typing import List, Callable

import kazoo.client
from kazoo.exceptions import NoNodeError, NodeExistsError
from kazoo.handlers.threading import KazooTimeoutError
from kazoo.protocol.states import KazooState

from zuul.lib.config import get_default
from zuul.zk.exceptions import NoClientException
from zuul.zk.handler import PoolSequentialThreadingHandler
from zuul.zk.vendor.client import ZuulKazooClient
from zuul.zk.vendor.connection import ZuulConnectionHandler

kazoo.client.ConnectionHandler = ZuulConnectionHandler


class ZooKeeperClient(object):
    log = logging.getLogger("zuul.zk.base.ZooKeeperClient")

    # Log zookeeper retry every 10 seconds
    retry_log_rate = 10

    def __init__(
        self,
        hosts,
        read_only=False,
        timeout=10.0,
        tls_cert=None,
        tls_key=None,
        tls_ca=None,
    ):
        """
        Initialize the ZooKeeper base client object.

        :param str hosts: Comma-separated list of hosts to connect to (e.g.
            127.0.0.1:2181,127.0.0.1:2182,[::1]:2183).
        :param bool read_only: If True, establishes a read-only connection.
        :param float timeout: The ZooKeeper session timeout, in
            seconds (default: 10.0).
        :param str tls_key: Path to TLS key
        :param str tls_cert: Path to TLS cert
        :param str tls_ca: Path to TLS CA cert
        """
        self.hosts = hosts
        self.read_only = read_only
        self.timeout = timeout
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        self.tls_ca = tls_ca
        self.was_lost = False

        self.client = None

        # Verify that we can read the cert files (Kazoo doesn't
        # provide useful error messages).
        for fn in (tls_cert, tls_key, tls_ca):
            if fn:
                with open(fn):
                    pass

        self._last_retry_log: int = 0
        self.on_connect_listeners: List[Callable[[], None]] = []
        self.on_disconnect_listeners: List[Callable[[], None]] = []
        self.on_connection_lost_listeners: List[Callable[[], None]] = []
        self.on_reconnect_listeners: List[Callable[[], None]] = []
        self.on_suspended_listeners = []

    def _connectionListener(self, state):
        """
        Listener method for Kazoo connection state changes.

        .. warning:: This method must not block.
        """
        session_id = 0
        if client_id := self.client.client_id:
            session_id, _ = client_id

        if state == KazooState.LOST:
            self.log.debug("ZooKeeper connection (session: %#x): LOST",
                           session_id)
            self.was_lost = True
            for listener in self.on_connection_lost_listeners:
                try:
                    listener()
                except Exception:
                    self.log.exception("Exception calling listener:")
        elif state == KazooState.SUSPENDED:
            self.log.debug("ZooKeeper connection (session: %#x): SUSPENDED",
                           session_id)
            for listener in self.on_suspended_listeners:
                try:
                    listener()
                except Exception:
                    self.log.exception("Exception calling listener:")
        else:
            self.log.debug("ZooKeeper connection (session: %#x): CONNECTED",
                           session_id)
            # Create a throwaway thread since zk operations can't
            # happen in this one.
            if self.was_lost:
                self.was_lost = False
                for listener in self.on_reconnect_listeners:
                    t = Thread(target=listener)
                    t.daemon = True
                    t.start()

    @property
    def connected(self):
        return self.client and self.client.state == KazooState.CONNECTED

    @property
    def suspended(self):
        return self.client and self.client.state == KazooState.SUSPENDED

    @property
    def lost(self):
        return not self.client or self.client.state == KazooState.LOST

    def logConnectionRetryEvent(self):
        now = time.monotonic()
        if now - self._last_retry_log >= self.retry_log_rate:
            self.log.warning("Retrying zookeeper connection")
            self._last_retry_log = now

    def connect(self):
        if self.client is None:
            args = dict(
                hosts=self.hosts,
                read_only=self.read_only,
                timeout=self.timeout,
                handler=PoolSequentialThreadingHandler(),
            )
            if self.tls_key:
                args['use_ssl'] = True
                args['keyfile'] = self.tls_key
                args['certfile'] = self.tls_cert
                args['ca'] = self.tls_ca
            self.client = ZuulKazooClient(**args)
            self.client.add_listener(self._connectionListener)
            # Manually retry initial connection attempt
            while True:
                try:
                    self.client.start(1)
                    break
                except KazooTimeoutError:
                    self.logConnectionRetryEvent()

            for listener in self.on_connect_listeners:
                listener()

    def disconnect(self):
        """
        Close the ZooKeeper cluster connection.

        You should call this method if you used connect() to establish a
        cluster connection.
        """
        for listener in self.on_disconnect_listeners:
            listener()

        if self.client is not None and self.client.connected:
            self.client.stop()
            self.client.close()
            self.client = None

    def resetHosts(self, hosts):
        """
        Reset the ZooKeeper cluster connection host list.

        :param str hosts: Comma-separated list of hosts to connect to (e.g.
            127.0.0.1:2181,127.0.0.1:2182,[::1]:2183).
        """
        if self.client is not None:
            self.client.set_hosts(hosts=hosts)

    @classmethod
    def fromConfig(cls, config: ConfigParser) -> "ZooKeeperClient":
        hosts = get_default(config, "zookeeper", "hosts")
        if not hosts:
            raise Exception("The zookeeper hosts config value is required")
        tls_key = get_default(config, "zookeeper", "tls_key")
        tls_cert = get_default(config, "zookeeper", "tls_cert")
        tls_ca = get_default(config, "zookeeper", "tls_ca")
        if not all([tls_key, tls_cert, tls_ca]):
            raise Exception(
                "A TLS ZooKeeper connection is required; please supply the "
                "tls_* zookeeper config values."
            )
        timeout = float(
            get_default(config, "zookeeper", "session_timeout", 120.0)
        )

        return cls(
            hosts=hosts,
            timeout=timeout,
            tls_key=tls_key,
            tls_cert=tls_cert,
            tls_ca=tls_ca,
        )

    def commitTransaction(self, tr):
        results = tr.commit()
        for res in results:
            self.log.debug("Transaction response %s", repr(res))
        for res in results:
            if isinstance(res, Exception):
                raise res
        return results

    def getCurrentLtime(self):
        """Get the logical timestamp as seen by the Zookeeper cluster."""
        try:
            zstat = self.client.set("/zuul/ltime", b"")
        except NoNodeError:
            try:
                self.client.create("/zuul/ltime", b"", makepath=True)
                zstat = self.client.set("/zuul/ltime", b"")
            except NodeExistsError:
                zstat = self.client.set("/zuul/ltime", b"")
        return zstat.last_modified_transaction_id

    def _fastRecursiveDelete(self, path, results):
        try:
            children = self.client.get_children(path)
        except NoNodeError:
            return
        if children:
            for child in children:
                self._fastRecursiveDelete(f'{path}/{child}', results)
        results.append(self.client.delete_async(path, -1))

    def fastRecursiveDelete(self, path):
        results = []
        self._fastRecursiveDelete(path, results)
        for res in results:
            try:
                res.get()
            except NoNodeError:
                pass


class ZooKeeperSimpleBase(metaclass=ABCMeta):
    """Base class for stateless Zookeeper interaction."""

    def __init__(self, client: ZooKeeperClient):
        self.client = client

    @property
    def kazoo_client(self) -> ZuulKazooClient:
        if not self.client.client:
            raise NoClientException()
        return self.client.client


class ZooKeeperBase(ZooKeeperSimpleBase):
    """Base class for registering state handling methods with ZooKeeper."""

    def __init__(self, client: ZooKeeperClient):
        super().__init__(client)
        if client:
            self.client.on_connect_listeners.append(self._onConnect)
            self.client.on_disconnect_listeners.append(self._onDisconnect)
            self.client.on_reconnect_listeners.append(self._onReconnect)
            self.client.on_suspended_listeners.append(self._onSuspended)

    def _onConnect(self):
        pass

    def _onDisconnect(self):
        pass

    def _onReconnect(self):
        pass

    def _onSuspended(self):
        pass
