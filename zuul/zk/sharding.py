# Copyright 2020 BMW Group
# Copyright 2024 Acme Gating, LLC
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

import io
from contextlib import suppress
import time
import zlib

from zuul.zk.components import COMPONENT_REGISTRY

from kazoo.exceptions import NoNodeError

# The default size limit for a node in Zookeeper is ~1MiB. However, as this
# also includes the size of the key we can not use all of it for data.
# Because of that we will leave ~47 KiB for the key.
NODE_BYTE_SIZE_LIMIT = 1000000


class RawZKIO(io.RawIOBase):
    def __init__(self, client, path, create=False, makepath=True, version=-1):
        self.client = client
        self.path = path
        self.bytes_read = 0
        self.bytes_written = 0
        self.cumulative_read_time = 0.0
        self.cumulative_write_time = 0.0
        self.znodes_read = 0
        self.znodes_written = 0
        self.create = create
        self.makepath = makepath
        self.version = version
        self.zstat = None

    def readable(self):
        return True

    def writable(self):
        return True

    def truncate(self, size=None):
        # We never truncate unless we're going to write, so make this
        # a noop for the single-znode case.
        pass

    def _getData(self, path):
        start = time.perf_counter()
        data, zstat = self.client.get(path)
        self.cumulative_read_time += time.perf_counter() - start
        self.bytes_read += len(data)
        self.znodes_read += 1
        return data, zstat

    def readall(self):
        data, self.zstat = self._getData(self.path)
        return data

    def write(self, data):
        byte_count = len(data)
        if byte_count > NODE_BYTE_SIZE_LIMIT:
            raise Exception(f"ZK data size too large: {byte_count}")
        start = time.perf_counter()
        if self.create:
            _, self.zstat = self.client.create(
                self.path, data, makepath=self.makepath, include_data=True)
        else:
            self.zstat = self.client.set(self.path, data,
                                         version=self.version)
        self.cumulative_write_time += time.perf_counter() - start
        self.bytes_written += byte_count
        self.znodes_written += 1
        return byte_count


class RawShardIO(RawZKIO):
    def __init__(self, *args, old_format=False, makepath=True, **kw):
        # MODEL_API < 31
        self.old_format = old_format
        self.makepath = makepath
        super().__init__(*args, makepath=makepath, **kw)

    def truncate(self, size=None):
        if size != 0:
            raise ValueError("Can only truncate to 0")
        with suppress(NoNodeError):
            self.client.delete(self.path, recursive=True)
        self.zstat = None

    @property
    def _shards(self):
        start = time.perf_counter()
        ret = self.client.get_children(self.path)
        self.cumulative_read_time += time.perf_counter() - start
        return ret

    def readall_old(self, shard0, shard1):
        # Decompress each shard individually and then recompress them
        # as a unit.
        read_buffer = io.BytesIO()
        read_buffer.write(zlib.decompress(shard0))
        read_buffer.write(zlib.decompress(shard1))
        for shard_count, shard_name in enumerate(sorted(self._shards)):
            if shard_count < 2:
                continue
            shard_path = "/".join((self.path, shard_name))
            data = self._getData(shard_path)[0]
            read_buffer.write(zlib.decompress(data))
        self.zstat = self.client.exists(self.path)
        return zlib.compress(read_buffer.getvalue())

    def readall(self):
        read_buffer = io.BytesIO()
        for shard_count, shard_name in enumerate(sorted(self._shards)):
            shard_path = "/".join((self.path, shard_name))
            data = self._getData(shard_path)[0]
            if shard_count == 1 and data[:2] == b'\x78\x9c':
                # If this is the second shard, and it starts with a
                # zlib header, we're probably reading the old format.
                # Double check that we can decompress it, and if so,
                # switch to reading the old format.
                try:
                    zlib.decompress(data)
                    return self.readall_old(
                        read_buffer.getvalue(),
                        data,
                    )
                except zlib.error:
                    # Perhaps we were wrong about the header
                    pass
            read_buffer.write(self._getData(shard_path)[0])
        self.zstat = self.client.exists(self.path)
        return read_buffer.getvalue()

    def write(self, data):
        # Only write one znode at a time and defer writing the rest to
        # the caller
        data_bytes = bytes(data[0:NODE_BYTE_SIZE_LIMIT])
        read_len = len(data_bytes)
        # MODEL_API < 31
        if self.old_format:
            # We're going to add a header and footer that is several
            # bytes, so we definitely need to reduce the size a little
            # bit, but the old format would end up with a considerable
            # amount of headroom due to compressing after chunking, so
            # lets go ahead and reserve 1k of space.
            new_limit = NODE_BYTE_SIZE_LIMIT - 1024
            data_bytes = data_bytes[0:new_limit]
            # Update our return value to indicate how many bytes we
            # actually read from input.
            read_len = len(data_bytes)
            data_bytes = zlib.compress(data_bytes)
        if not (len(data_bytes) <= NODE_BYTE_SIZE_LIMIT):
            raise RuntimeError("Shard too large")
        start = time.perf_counter()
        # The path we pass to a shard writer is  e.g. '/foo/bar'. Now,
        # for shards the makepath argument should only apply to '/foo'
        # but not the 'bar' subnode as it holds the individual shards
        # and will also be deleted recursively on e.g. a truncate.
        while True:
            try:
                self.client.create(
                    "{}/".format(self.path),
                    data_bytes,
                    sequence=True,
                )
                break
            except NoNodeError:
                if not self.makepath:
                    raise
                self.client.ensure_path(self.path)

        self.cumulative_write_time += time.perf_counter() - start
        self.bytes_written += len(data_bytes)
        self.znodes_written += 1
        if self.zstat is None:
            self.zstat = self.client.exists(self.path)
        return read_len


class BufferedZKWriter(io.BufferedWriter):
    def __init__(self, client, path):
        self.__raw = RawZKIO(client, path)
        super().__init__(self.__raw)

    @property
    def bytes_written(self):
        return self.__raw.bytes_written

    @property
    def cumulative_write_time(self):
        return self.__raw.cumulative_write_time

    @property
    def znodes_written(self):
        return self.__raw.znodes_written

    @property
    def zstat(self):
        return self.__raw.zstat


class BufferedZKReader(io.BufferedReader):
    def __init__(self, client, path):
        self.__raw = RawZKIO(client, path)
        super().__init__(self.__raw)

    @property
    def bytes_read(self):
        return self.__raw.bytes_read

    @property
    def cumulative_read_time(self):
        return self.__raw.cumulative_read_time

    @property
    def znodes_read(self):
        return self.__raw.znodes_read

    @property
    def zstat(self):
        return self.__raw.zstat


class BufferedShardWriter(io.BufferedWriter):
    def __init__(self, client, path, create=False, makepath=True, version=-1):
        self.__old_format = COMPONENT_REGISTRY.model_api < 31
        self.__raw = RawShardIO(client, path, create=create, makepath=makepath,
                                version=version, old_format=self.__old_format)
        super().__init__(self.__raw, NODE_BYTE_SIZE_LIMIT)

    @property
    def bytes_written(self):
        return self.__raw.bytes_written

    @property
    def cumulative_write_time(self):
        return self.__raw.cumulative_write_time

    @property
    def znodes_written(self):
        return self.__raw.znodes_written

    @property
    def zstat(self):
        return self.__raw.zstat

    def write(self, data):
        # MODEL_API < 31
        if self.__old_format and data[:2] == b'\x78\x9c':
            data = zlib.decompress(data)
        return super().write(data)


class BufferedShardReader(io.BufferedReader):
    def __init__(self, client, path):
        self.__raw = RawShardIO(client, path)
        super().__init__(self.__raw, NODE_BYTE_SIZE_LIMIT)

    @property
    def bytes_read(self):
        return self.__raw.bytes_read

    @property
    def cumulative_read_time(self):
        return self.__raw.cumulative_read_time

    @property
    def znodes_read(self):
        return self.__raw.znodes_read

    @property
    def zstat(self):
        return self.__raw.zstat
