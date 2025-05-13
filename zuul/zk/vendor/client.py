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

from collections import defaultdict

from kazoo.client import (
    _prefix_root,
    KazooClient,
)
from kazoo.protocol.states import (
    Callback,
    EventType,
    WatchedEvent,
)

from zuul.zk.vendor.states import (
    AddWatchMode,
    WatcherType,
)
from zuul.zk.vendor.serialization import (
    AddWatch,
    RemoveWatches,
)


class ZuulKazooClient(KazooClient):
    def __init__(self, *args, **kw):
        self._persistent_watchers = defaultdict(set)
        self._persistent_recursive_watchers = defaultdict(set)
        super().__init__(*args, **kw)

    def _reset_watchers(self):
        watchers = []
        for child_watchers in self._child_watchers.values():
            watchers.extend(child_watchers)

        for data_watchers in self._data_watchers.values():
            watchers.extend(data_watchers)

        for persistent_watchers in self._persistent_watchers.values():
            watchers.extend(persistent_watchers)

        for pr_watchers in self._persistent_recursive_watchers.values():
            watchers.extend(pr_watchers)

        self._child_watchers = defaultdict(set)
        self._data_watchers = defaultdict(set)
        self._persistent_watchers = defaultdict(set)
        self._persistent_recursive_watchers = defaultdict(set)

        ev = WatchedEvent(EventType.NONE, self._state, None)
        for watch in watchers:
            self.handler.dispatch_callback(Callback("watch", watch, (ev,)))

    def add_watch(self, path, watch, mode):
        """Add a watch.

        This method adds persistent watches.  Unlike the data and
        child watches which may be set by calls to
        :meth:`KazooClient.exists`, :meth:`KazooClient.get`, and
        :meth:`KazooClient.get_children`, persistent watches are not
        removed after being triggered.

        To remove a persistent watch, use
        :meth:`KazooClient.remove_all_watches` with an argument of
        :attr:`~kazoo.protocol.states.WatcherType.ANY`.

        The `mode` argument determines whether or not the watch is
        recursive.  To set a persistent watch, use
        :class:`~kazoo.protocol.states.AddWatchMode.PERSISTENT`.  To set a
        persistent recursive watch, use
        :class:`~kazoo.protocol.states.AddWatchMode.PERSISTENT_RECURSIVE`.

        :param path: Path of node to watch.
        :param watch: Watch callback to set for future changes
                      to this path.
        :param mode: The mode to use.
        :type mode: int

        :raises:
            :exc:`~kazoo.exceptions.MarshallingError` if mode is
            unknown.

            :exc:`~kazoo.exceptions.ZookeeperError` if the server
            returns a non-zero error code.
        """
        return self.add_watch_async(path, watch, mode).get()

    def add_watch_async(self, path, watch, mode):
        """Asynchronously add a watch. Takes the same arguments as
        :meth:`add_watch`.
        """
        if not isinstance(path, str):
            raise TypeError("Invalid type for 'path' (string expected)")
        if not callable(watch):
            raise TypeError("Invalid type for 'watch' (must be a callable)")
        if not isinstance(mode, int):
            raise TypeError("Invalid type for 'mode' (int expected)")
        if mode not in (
            AddWatchMode.PERSISTENT,
            AddWatchMode.PERSISTENT_RECURSIVE,
        ):
            raise ValueError("Invalid value for 'mode'")

        async_result = self.handler.async_result()
        self._call(
            AddWatch(_prefix_root(self.chroot, path), watch, mode),
            async_result,
        )
        return async_result

    def remove_all_watches(self, path, watcher_type):
        """Remove watches from a path.

        This removes all watches of a specified type (data, child,
        any) from a given path.

        The `watcher_type` argument specifies which type to use.  It
        may be one of:

        * :attr:`~kazoo.protocol.states.WatcherType.DATA`
        * :attr:`~kazoo.protocol.states.WatcherType.CHILDREN`
        * :attr:`~kazoo.protocol.states.WatcherType.ANY`

        To remove persistent watches, specify a watcher type of
        :attr:`~kazoo.protocol.states.WatcherType.ANY`.

        :param path: Path of watch to remove.
        :param watcher_type: The type of watch to remove.
        :type watcher_type: int
        """

        return self.remove_all_watches_async(path, watcher_type).get()

    def remove_all_watches_async(self, path, watcher_type):
        """Asynchronously remove watches. Takes the same arguments as
        :meth:`remove_all_watches`.
        """
        if not isinstance(path, str):
            raise TypeError("Invalid type for 'path' (string expected)")
        if not isinstance(watcher_type, int):
            raise TypeError("Invalid type for 'watcher_type' (int expected)")
        if watcher_type not in (
            WatcherType.ANY,
            WatcherType.CHILDREN,
            WatcherType.DATA,
        ):
            raise ValueError("Invalid value for 'watcher_type'")

        async_result = self.handler.async_result()
        self._call(
            RemoveWatches(_prefix_root(self.chroot, path), watcher_type),
            async_result,
        )
        return async_result
