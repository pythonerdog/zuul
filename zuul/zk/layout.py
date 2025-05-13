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

import json
from collections.abc import MutableMapping
from contextlib import suppress
from functools import total_ordering
import logging
import time
import zlib

from kazoo.exceptions import NoNodeError

from zuul.zk import sharding, ZooKeeperBase, ZooKeeperSimpleBase
from zuul.provider import BaseProvider


@total_ordering
class LayoutState:
    """Representation of a tenant's layout state.

    The layout state holds information about a certain version of a
    tenant's layout. It is used to coordinate reconfigurations across
    multiple schedulers by comparing a local tenant layout state
    against the current version in Zookeeper. In case it detects that
    a local layout state is outdated, this scheduler is not allowed to
    process this tenant (events, pipelines, ...) until the layout is
    updated.

    The important information of the layout state is the logical
    timestamp (ltime) that is used to detect if the layout on a
    scheduler needs to be updated. The ltime is the last modified
    transaction ID (mzxid) of the corresponding Znode in Zookeeper.

    The hostname of the scheduler creating the new layout state and the
    timestamp of the last reconfiguration are only informational and
    may aid in debugging.
    """

    def __init__(self, tenant_name, hostname, last_reconfigured, uuid,
                 branch_cache_min_ltimes, last_reconfigure_event_ltime,
                 ltime=-1):
        self.uuid = uuid
        self.ltime = ltime
        self.tenant_name = tenant_name
        self.hostname = hostname
        self.last_reconfigured = last_reconfigured
        self.last_reconfigure_event_ltime =\
            last_reconfigure_event_ltime
        self.branch_cache_min_ltimes = branch_cache_min_ltimes

    def toDict(self):
        return {
            "tenant_name": self.tenant_name,
            "hostname": self.hostname,
            "last_reconfigured": self.last_reconfigured,
            "last_reconfigure_event_ltime":
            self.last_reconfigure_event_ltime,
            "uuid": self.uuid,
            "branch_cache_min_ltimes": self.branch_cache_min_ltimes,
        }

    @classmethod
    def fromDict(cls, data):
        return cls(
            data["tenant_name"],
            data["hostname"],
            data["last_reconfigured"],
            data.get("uuid"),
            data.get("branch_cache_min_ltimes"),
            data.get("last_reconfigure_event_ltime", -1),
            data.get("ltime", -1),
        )

    def __eq__(self, other):
        if not isinstance(other, LayoutState):
            return False
        return self.uuid == other.uuid

    def __gt__(self, other):
        if not isinstance(other, LayoutState):
            return False
        return self.ltime > other.ltime

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} {self.tenant_name}: "
            f"ltime={self.ltime}, "
            f"hostname={self.hostname}, "
            f"last_reconfigured={self.last_reconfigured}>"
        )


class LayoutStateStore(ZooKeeperBase, MutableMapping):
    log = logging.getLogger("zuul.LayoutStore")

    layout_root = "/zuul/layout"
    layout_data_root = "/zuul/layout-data"

    def __init__(self, client, callback):
        super().__init__(client)
        self._watched_tenants = set()
        self._callback = callback
        self.kazoo_client.ensure_path(self.layout_root)
        self.kazoo_client.ChildrenWatch(self.layout_root, self._layoutCallback)

    def _layoutCallback(self, tenant_list, event=None):
        new_tenants = set(tenant_list) - self._watched_tenants
        for tenant_name in new_tenants:
            self.kazoo_client.DataWatch(f"{self.layout_root}/{tenant_name}",
                                        self._callbackWrapper)

    def _callbackWrapper(self, data, stat, event):
        self._callback()

    def __getitem__(self, tenant_name):
        try:
            data, zstat = self.kazoo_client.get(
                f"{self.layout_root}/{tenant_name}")
        except NoNodeError:
            raise KeyError(tenant_name)

        if not data:
            raise KeyError(tenant_name)

        return LayoutState.fromDict({
            "ltime": zstat.last_modified_transaction_id,
            **json.loads(data)
        })

    def __setitem__(self, tenant_name, state):
        path = f"{self.layout_root}/{tenant_name}"
        data = json.dumps(state.toDict(), sort_keys=True).encode("utf-8")
        if self.kazoo_client.exists(path):
            zstat = self.kazoo_client.set(path, data)
        else:
            _, zstat = self.kazoo_client.create(path, data, include_data=True)
        # Set correct ltime of the layout in Zookeeper
        state.ltime = zstat.last_modified_transaction_id

    def __delitem__(self, tenant_name):
        try:
            self.kazoo_client.delete(f"{self.layout_root}/{tenant_name}")
        except NoNodeError:
            raise KeyError(tenant_name)

    def __iter__(self):
        try:
            tenant_names = self.kazoo_client.get_children(self.layout_root)
        except NoNodeError:
            return
        yield from tenant_names

    def __len__(self):
        zstat = self.kazoo_client.exists(self.layout_root)
        if zstat is None:
            return 0
        return zstat.children_count

    def getMinLtimes(self, layout_state):
        try:
            path = f"{self.layout_data_root}/{layout_state.uuid}"
            with sharding.BufferedShardReader(
                    self.kazoo_client, path) as stream:
                data = zlib.decompress(stream.read())
        except NoNodeError:
            return None

        try:
            return json.loads(data)['min_ltimes']
        except Exception:
            return None

    def setMinLtimes(self, layout_state, min_ltimes):
        data = dict(min_ltimes=min_ltimes)
        encoded_data = json.dumps(data).encode("utf-8")

        path = f"{self.layout_data_root}/{layout_state.uuid}"
        with sharding.BufferedShardWriter(
                self.kazoo_client, path) as stream:
            stream.write(zlib.compress(encoded_data))

    def cleanup(self, delay=300):
        self.log.debug("Starting layout data cleanup")
        known_layouts = set()
        for tenant in self.kazoo_client.get_children(
                self.layout_root):
            state = self.get(tenant)
            if state:
                known_layouts.add(state.uuid)

        for layout_uuid in self.kazoo_client.get_children(
                self.layout_data_root):
            if layout_uuid in known_layouts:
                continue

            path = f"{self.layout_data_root}/{layout_uuid}"
            zstat = self.kazoo_client.exists(path)
            if zstat is None:
                continue

            now = time.time()
            if now - zstat.created >= delay:
                self.log.debug("Deleting unused layout data for %s",
                               layout_uuid)
                with suppress(NoNodeError):
                    self.kazoo_client.delete(path, recursive=True)
        self.log.debug("Finished layout data cleanup")


class LayoutProvidersStore(ZooKeeperSimpleBase):
    log = logging.getLogger("zuul.LayoutProvidersStore")

    tenant_root = "/zuul/tenant"

    def __init__(self, client, connections, system_id):
        super().__init__(client)
        self.connections = connections
        self.system_id = system_id

    def get(self, context, tenant_name):
        path = f"{self.tenant_root}/{tenant_name}/provider"
        try:
            repo_names = self.kazoo_client.get_children(path)
        except NoNodeError:
            repo_names = []
        for repo in repo_names:
            path = f"{self.tenant_root}/{tenant_name}/provider/{repo}"
            try:
                provider_names = self.kazoo_client.get_children(path)
            except NoNodeError:
                provider_names = []
            for provider_name in provider_names:
                provider_path = (f"{path}/{provider_name}/config")
                yield BaseProvider.fromZK(
                    context, provider_path, self.connections, self.system_id
                )

    def set(self, context, tenant_name, providers):
        self.clear(tenant_name)
        path = f"{self.tenant_root}/{tenant_name}/provider"
        self.kazoo_client.ensure_path(path)
        for provider in providers:
            provider.internalCreate(context)

    def clear(self, tenant_name):
        path = f"{self.tenant_root}/{tenant_name}/provider"
        self.kazoo_client.delete(path, recursive=True)
