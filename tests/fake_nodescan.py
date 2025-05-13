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

class FakeSocket:
    def __init__(self):
        self.blocking = True
        self.fd = 1

    def setblocking(self, b):
        self.blocking = b

    def getsockopt(self, level, optname):
        return None

    def connect(self, addr):
        if not self.blocking:
            raise BlockingIOError()
        raise Exception("blocking connect attempted")

    def fileno(self):
        return self.fd


class FakePoll:
    def __init__(self, _fail=False):
        self.fds = []
        self._fail = _fail

    def register(self, fd, bitmap):
        self.fds.append(fd)

    def unregister(self, fd):
        if fd in self.fds:
            self.fds.remove(fd)

    def poll(self, timeout=None):
        if self._fail:
            return []
        fds = self.fds[:]
        self.fds = [f for f in fds if not isinstance(f, FakeSocket)]
        fds = [f.fileno() if hasattr(f, 'fileno') else f for f in fds]
        return [(f, 0) for f in fds]


class Dummy:
    pass


class FakeKey:
    def get_name(self):
        return 'fake key'

    def get_base64(self):
        return 'fake base64'


class FakeTransport:
    def __init__(self, _fail=False, active=True):
        self.active = active
        self._fail = _fail

    def start_client(self, event=None, timeout=None):
        if not self._fail:
            event.set()

    def get_security_options(self):
        ret = Dummy()
        ret.key_types = ['rsa']
        return ret

    def get_remote_server_key(self):
        return FakeKey()

    def get_exception(self):
        return Exception("Fake ssh error")
