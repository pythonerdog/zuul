# Copyright 2024 BMW Group
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

import collections
import json
import logging
import threading

import mmh3
from kazoo.exceptions import NoNodeError

from zuul.model import NodesetRequest, ProviderNode, QuotaInformation
from zuul.zk.cache import ZuulTreeCache
from zuul.zk.zkobject import ZKContext


def _dictToBytes(data):
    return json.dumps(data).encode("utf-8")


def _bytesToDict(raw_data):
    return json.loads(raw_data.decode("utf-8"))


def launcher_score(name, item):
    return mmh3.hash(f"{name}-{item.uuid}", signed=False)


class LockableZKObjectCache(ZuulTreeCache):

    def __init__(self, zk_client, updated_event, root, items_path,
                 locks_path, zkobject_class):
        self.updated_event = updated_event
        self.items_path = items_path
        self.locks_path = locks_path
        self.zkobject_class = zkobject_class
        super().__init__(zk_client, root)

    def _parsePath(self, path):
        if not path.startswith(self.root):
            return None
        path = path[len(self.root) + 1:]
        parts = path.split('/')
        # We are interested in requests with a parts that look like:
        # ([<self.items_path>, <self.locks_path>], <uuid>, ...)
        if len(parts) < 2:
            return None
        return parts

    def parsePath(self, path):
        parts = self._parsePath(path)
        if parts is None:
            return None
        if len(parts) < 2:
            return None
        if parts[0] != self.items_path:
            return None
        item_uuid = parts[1]
        return (item_uuid,)

    def preCacheHook(self, event, exists, data=None, stat=None):
        parts = self._parsePath(event.path)
        if parts is None:
            return

        # Expecting (<self.locks_path>, <uuid>, <lock>,)
        if len(parts) != 3:
            return

        object_type, request_uuid, *_ = parts
        if object_type != self.locks_path:
            return

        key = (request_uuid,)
        request = self._cached_objects.get(key)

        if not request:
            return

        if request.is_locked != exists:
            request._set(is_locked=exists)
            if self.updated_event:
                self.updated_event()

    def postCacheHook(self, event, data, stat, key, obj):
        if self.updated_event:
            self.updated_event()

    def objectFromRaw(self, key, data, zstat):
        return self.zkobject_class._fromRaw(data, zstat, None)

    def updateFromRaw(self, obj, key, data, zstat):
        obj._updateFromRaw(data, zstat, None)

    def getItem(self, item_id):
        self.ensureReady()
        return self._cached_objects.get((item_id,))

    def getItems(self):
        # get a copy of the values view to avoid runtime errors in the event
        # the _cached_nodes dict gets updated while iterating
        self.ensureReady()
        return list(self._cached_objects.values())

    def getKeys(self):
        self.ensureReady()
        return set(self._cached_objects.keys())


class RequestCache(LockableZKObjectCache):

    def preCacheHook(self, event, exists, data=None, stat=None):
        parts = self._parsePath(event.path)
        if parts is None:
            return

        # Expecting (<self.locks_path>, <uuid>, <lock>,)
        # or (<self.items_path>, <uuid>, revision,)
        if len(parts) != 3:
            return

        object_type, request_uuid, *_ = parts
        key = (request_uuid,)
        request = self._cached_objects.get(key)

        if not request:
            return

        if object_type == self.locks_path:
            request._set(is_locked=exists)
        elif data is not None:
            request._revision._updateFromRaw(data, stat, None)
            return self.STOP_OBJECT_UPDATE


class NodeCache(LockableZKObjectCache):
    def __init__(self, *args, **kw):
        # Key -> quota, for each cached object
        self._cached_quota = {}
        # Provider canonical name -> quota, for each provider
        self._provider_quota = collections.defaultdict(
            lambda: QuotaInformation())
        super().__init__(*args, **kw)

    def postCacheHook(self, event, data, stat, key, obj):
        # Have we previously added quota for this object?
        old_quota = self._cached_quota.get(key)
        if key in self._cached_objects:
            new_quota = obj.quota
        else:
            new_quota = None
        # Now that we've established whether we should count the quota
        # based on object presence, take node state into account.
        if obj is None or obj.state not in obj.ALLOCATED_STATES:
            new_quota = None
        if new_quota != old_quota:
            # Add the new value first so if another thread races these
            # two operations, it sees us go over quota and not under.
            if new_quota is not None:
                self._provider_quota[obj.provider].add(new_quota)
            if old_quota is not None:
                self._provider_quota[obj.provider].subtract(old_quota)
            self._cached_quota[key] = new_quota
        super().postCacheHook(event, data, stat, key, obj)

    def getQuota(self, provider):
        return self._provider_quota[provider.canonical_name]


class LauncherApi:
    log = logging.getLogger("zuul.LauncherApi")

    def __init__(self, zk_client, component_registry, component_info,
                 event_callback, connection_filter=None):
        self.zk_client = zk_client
        self.component_registry = component_registry
        self.component_info = component_info
        self.event_callback = event_callback
        self.requests_cache = RequestCache(
            self.zk_client,
            self.event_callback,
            root=NodesetRequest.ROOT,
            items_path=NodesetRequest.REQUESTS_PATH,
            locks_path=NodesetRequest.LOCKS_PATH,
            zkobject_class=NodesetRequest)
        self.nodes_cache = NodeCache(
            self.zk_client,
            self.event_callback,
            root=ProviderNode.ROOT,
            items_path=ProviderNode.NODES_PATH,
            locks_path=ProviderNode.LOCKS_PATH,
            zkobject_class=ProviderNode)
        self.connection_filter = connection_filter
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()
        self.requests_cache.stop()
        self.nodes_cache.stop()

    def getMatchingRequests(self):
        candidate_launchers = {
            c.hostname: c for c in self.component_registry.all("launcher")}
        candidate_names = set(candidate_launchers.keys())

        for request in sorted(self.requests_cache.getItems()):
            if request.hasLock():
                # We are holding a lock, so short-circuit here.
                yield request
            if request.is_locked:
                # Request is locked by someone else
                continue
            if request.state == NodesetRequest.State.TEST_HOLD:
                continue

            score_launchers = (
                set(request._lscores.keys()) if request._lscores else set())
            missing_scores = candidate_names - score_launchers
            if missing_scores or request._lscores is None:
                # (Re-)compute launcher scores
                request._set(_lscores={launcher_score(n, request): n
                                       for n in candidate_names})

            launcher_scores = sorted(request._lscores.items())
            # self.log.debug("Launcher scores: %s", launcher_scores)
            for score, launcher_name in launcher_scores:
                launcher = candidate_launchers.get(launcher_name)
                if not launcher:
                    continue
                if launcher.state != launcher.RUNNING:
                    continue
                if launcher.hostname == self.component_info.hostname:
                    yield request
                break

    def getNodesetRequest(self, request_id):
        return self.requests_cache.getItem(request_id)

    def getNodesetRequests(self):
        return sorted(self.requests_cache.getItems())

    def getMatchingProviderNodes(self):
        all_launchers = {
            c.hostname: c for c in self.component_registry.all("launcher")}

        for node in self.nodes_cache.getItems():
            if node.hasLock():
                # We are holding a lock, so short-circuit here.
                yield node
            if node.is_locked:
                # Node is locked by someone else
                continue

            candidate_launchers = {
                n: c for n, c in all_launchers.items()
                if not c.connection_filter
                or node.connection_name in c.connection_filter}
            candidate_names = set(candidate_launchers)
            if node._lscores is None:
                missing_scores = candidate_names
            else:
                score_launchers = set(node._lscores.keys())
                missing_scores = candidate_names - score_launchers

            if missing_scores or node._lscores is None:
                # (Re-)compute launcher scores
                node._set(_lscores={launcher_score(n, node): n
                                    for n in candidate_names})

            launcher_scores = sorted(node._lscores.items())

            for score, launcher_name in launcher_scores:
                launcher = candidate_launchers.get(launcher_name)
                if not launcher:
                    # Launcher is no longer online
                    continue
                if launcher.state != launcher.RUNNING:
                    continue
                if launcher.hostname == self.component_info.hostname:
                    yield node
                break

    def getProviderNode(self, node_id):
        return self.nodes_cache.getItem(node_id)

    def getProviderNodes(self):
        return self.nodes_cache.getItems()

    def createZKContext(self, lock=None, log=None):
        return ZKContext(
            self.zk_client, lock, self.stop_event, log or self.log)

    def cleanupNodes(self):
        # TODO: This method currently just performs some basic cleanup and
        # might need to be extended in the future.
        for node in self.getProviderNodes():
            if node.state != ProviderNode.State.USED:
                continue
                # FIXME: check if the node request still exists
            if node.is_locked:
                continue
            if self.getNodesetRequest(node.request_id):
                continue
            with self.createZKContext(None) as outer_ctx:
                if lock := node.acquireLock(outer_ctx):
                    with self.createZKContext(lock) as ctx:
                        try:
                            node.delete(ctx)
                        except NoNodeError:
                            # Node is already deleted
                            pass
                        finally:
                            node.releaseLock(ctx)
