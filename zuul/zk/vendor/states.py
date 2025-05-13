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

class AddWatchMode(object):
    """Modes for use with :meth:`~kazoo.client.KazooClient.add_watch`

    .. attribute:: PERSISTENT

        The watch is not removed when trigged.

    .. attribute:: PERSISTENT_RECURSIVE

        The watch is not removed when trigged, and applies to all
        paths underneath the supplied path as well.
    """

    PERSISTENT = 0
    PERSISTENT_RECURSIVE = 1


class WatcherType(object):
    """Watcher types for use with
    :meth:`~kazoo.client.KazooClient.remove_all_watches`

    .. attribute:: CHILDREN

        Child watches.

    .. attribute:: DATA

        Data watches.

    .. attribute:: ANY

        Any type of watch (child, data, persistent, or persistent
        recursive).

    """

    CHILDREN = 1
    DATA = 2
    ANY = 3
