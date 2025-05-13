# This file is derived from the Kazoo project
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

from collections import namedtuple

from kazoo.protocol.serialization import (
    int_struct,
    write_string,
)


class RemoveWatches(namedtuple("RemoveWatches", "path watcher_type")):
    type = 18

    def serialize(self):
        b = bytearray()
        b.extend(write_string(self.path))
        b.extend(int_struct.pack(self.watcher_type))
        return b

    @classmethod
    def deserialize(cls, bytes, offset):
        return None


class AddWatch(namedtuple("AddWatch", "path watcher mode")):
    type = 106

    def serialize(self):
        b = bytearray()
        b.extend(write_string(self.path))
        b.extend(int_struct.pack(self.mode))
        return b

    @classmethod
    def deserialize(cls, bytes, offset):
        return None
