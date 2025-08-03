# Copyright 2021 Acme Gating, LLC
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

import socket
import threading

import prometheus_client

from zuul.lib.config import get_default


def _get_best_family(address, port):
    """Automatically select address family depending on address"""
    # HTTPServer defaults to AF_INET, which will not start properly if
    # binding an ipv6 address is requested.
    # This function is based on what upstream python did for http.server
    # in https://github.com/python/cpython/pull/11767
    infos = socket.getaddrinfo(address, port)
    family, _, _, _, sockaddr = next(iter(infos))
    return family, sockaddr[0]


class MonitoringServer:
    def __init__(self, config, section, component_info):
        if not config.has_option(section, 'prometheus_port'):
            self.httpd = None
            return

        self.component_info = component_info
        port = int(config.get(section, 'prometheus_port'))
        addr = get_default(
            config, section, 'prometheus_addr', '0.0.0.0')

        self.prometheus_app = prometheus_client.make_wsgi_app(
            prometheus_client.registry.REGISTRY)

        class TmpServer(prometheus_client.exposition.ThreadingWSGIServer):
            """Copy of ThreadingWSGIServer to update address_family locally"""
        TmpServer.address_family, addr = _get_best_family(addr, port)

        self.httpd = prometheus_client.exposition.make_server(
            addr, port,
            self.handleRequest,
            TmpServer,
            handler_class=prometheus_client.exposition._SilentHandler)
        # The unit tests pass in 0 for the port
        self.port = self.httpd.socket.getsockname()[1]

    def start(self):
        if self.httpd is None:
            return
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        if self.httpd is None:
            return
        self.httpd.shutdown()

    def join(self):
        if self.httpd is None:
            return
        self.thread.join()
        self.httpd.socket.close()

    def handleRequest(self, environ, start_response):
        headers = []
        output = b''
        if environ['PATH_INFO'] == '/health/live':
            status = '200 OK'
        elif environ['PATH_INFO'] == '/health/ready':
            if (self.component_info.state in (
                    self.component_info.RUNNING,
                    self.component_info.PAUSED)):
                status = '200 OK'
            else:
                status = '503 Service Unavailable'
        elif environ['PATH_INFO'] == '/health/status':
            status = '200 OK'
            headers = [('Content-Type', 'text/plain')]
            output = str(self.component_info.state).encode('utf8').upper()
        elif environ['PATH_INFO'] in ('/metrics', '/'):
            # The docs say '/metrics' but '/' worked and was likely
            # used by users, so let's support both for now.
            return self.prometheus_app(environ, start_response)
        else:
            status = '404 Not Found'
        # Return output
        start_response(status, headers)
        return [output]
