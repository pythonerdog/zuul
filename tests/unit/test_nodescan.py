# Copyright (C) 2023 Acme Gating, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest.mock import patch

import testtools

from zuul import exceptions
from zuul.model import ProviderNode
from zuul.launcher.server import NodescanWorker, NodescanRequest
from zuul.zk import zkobject

from tests.base import (
    BaseTestCase,
    iterate_timeout,
    okay_tracebacks,
)
from tests.fake_nodescan import (
    FakeSocket,
    FakePoll,
    FakeTransport,
)


class DummyProviderNode(ProviderNode, subclass_id="dummy-nodescan"):
    pass


class TestNodescanWorker(BaseTestCase):

    def createZKContext(self, lock=None):
        return zkobject.ZKContext(self.zk_client, lock,
                                  None, self.log)

    @patch('paramiko.transport.Transport')
    @patch('socket.socket')
    @patch('select.epoll')
    def test_nodescan(self, mock_epoll, mock_socket, mock_transport):
        # Test the nodescan worker
        fake_socket = FakeSocket()
        mock_socket.return_value = fake_socket
        mock_epoll.return_value = FakePoll()
        mock_transport.return_value = FakeTransport()
        worker = NodescanWorker()
        node = DummyProviderNode()
        node._set(
            interface_ip='198.51.100.1',
            connection_port=22,
            connection_type='ssh',
            host_key_checking=True,
            boot_timeout=300,
        )
        worker.start()
        request = NodescanRequest(node, self.log)
        worker.addRequest(request)
        for _ in iterate_timeout(30, 'waiting for nodescan'):
            if request.complete:
                break
        result = request.result()
        self.assertEqual(result, ['fake key fake base64'])
        worker.stop()
        worker.join()

    @patch('paramiko.transport.Transport')
    @patch('socket.socket')
    @patch('select.epoll')
    def test_nodescan_connection_timeout(
            self, mock_epoll, mock_socket, mock_transport):
        # Test a timeout during socket connection
        fake_socket = FakeSocket()
        mock_socket.return_value = fake_socket
        mock_epoll.return_value = FakePoll(_fail=True)
        mock_transport.return_value = FakeTransport()
        worker = NodescanWorker()
        node = DummyProviderNode()
        node._set(
            interface_ip='198.51.100.1',
            connection_port=22,
            connection_type='ssh',
            host_key_checking=True,
            boot_timeout=1,
        )
        worker.start()
        request = NodescanRequest(node, self.log)
        worker.addRequest(request)
        for _ in iterate_timeout(30, 'waiting for nodescan'):
            if request.complete:
                break
        with testtools.ExpectedException(
                exceptions.ConnectionTimeoutException):
            request.result()
        worker.stop()
        worker.join()

    @patch('paramiko.transport.Transport')
    @patch('socket.socket')
    @patch('select.epoll')
    def test_nodescan_ssh_timeout(
            self, mock_epoll, mock_socket, mock_transport):
        # Test a timeout during ssh connection
        fake_socket = FakeSocket()
        mock_socket.return_value = fake_socket
        mock_epoll.return_value = FakePoll()
        mock_transport.return_value = FakeTransport(_fail=True)
        worker = NodescanWorker()
        node = DummyProviderNode()
        node._set(
            interface_ip='198.51.100.1',
            connection_port=22,
            connection_type='ssh',
            host_key_checking=True,
            boot_timeout=1,
        )
        worker.start()
        request = NodescanRequest(node, self.log)
        worker.addRequest(request)
        for _ in iterate_timeout(30, 'waiting for nodescan'):
            if request.complete:
                break
        with testtools.ExpectedException(
                exceptions.ConnectionTimeoutException):
            request.result()
        worker.stop()
        worker.join()

    @patch('paramiko.transport.Transport')
    @patch('socket.socket')
    @patch('select.epoll')
    @okay_tracebacks('Fake ssh error')
    def test_nodescan_ssh_error(
            self, mock_epoll, mock_socket, mock_transport):
        # Test an ssh error
        fake_socket = FakeSocket()
        mock_socket.return_value = fake_socket
        mock_epoll.return_value = FakePoll()
        mock_transport.return_value = FakeTransport(active=False)
        worker = NodescanWorker()
        node = DummyProviderNode()
        node._set(
            interface_ip='198.51.100.1',
            connection_port=22,
            connection_type='ssh',
            host_key_checking=True,
            boot_timeout=1,
        )
        worker.start()
        request = NodescanRequest(node, self.log)
        worker.addRequest(request)
        for _ in iterate_timeout(30, 'waiting for nodescan'):
            if request.complete:
                break
        with testtools.ExpectedException(
                exceptions.ConnectionTimeoutException):
            request.result()
        worker.stop()
        worker.join()

    @patch('paramiko.transport.Transport')
    @patch('socket.socket')
    @patch('select.epoll')
    def test_nodescan_queue(self, mock_epoll, mock_socket, mock_transport):
        # Test the max_requests queing function
        fake_socket1 = FakeSocket()
        fake_socket2 = FakeSocket()
        fake_socket2.fd = 2
        # We get two sockets for each host
        sockets = [fake_socket1, fake_socket1, fake_socket2, fake_socket2]

        def getsocket(*args, **kw):
            return sockets.pop(0)

        mock_socket.side_effect = getsocket
        mock_epoll.return_value = FakePoll()
        mock_transport.return_value = FakeTransport()
        worker = NodescanWorker()
        worker.MAX_REQUESTS = 1
        node1 = DummyProviderNode()
        node1._set(
            interface_ip='198.51.100.1',
            connection_port=22,
            connection_type='ssh',
            host_key_checking=True,
            boot_timeout=300,
        )
        node2 = DummyProviderNode()
        node2._set(
            interface_ip='198.51.100.2',
            connection_port=22,
            connection_type='ssh',
            host_key_checking=True,
            boot_timeout=300,
        )

        request1 = NodescanRequest(node1, self.log)
        request2 = NodescanRequest(node2, self.log)
        worker.addRequest(request1)
        worker.addRequest(request2)
        worker.start()
        for _ in iterate_timeout(5, 'waiting for nodescan'):
            if request1.complete and request2.complete:
                break
        result1 = request1.result()
        result2 = request2.result()
        self.assertEqual(result1, ['fake key fake base64'])
        self.assertEqual(result2, ['fake key fake base64'])
        worker.stop()
        worker.join()
