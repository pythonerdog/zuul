# Copyright 2016 Red Hat, Inc.
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

from zuul.driver import Driver, ConnectionInterface, TriggerInterface
from zuul.driver import SourceInterface, ReporterInterface
from zuul.driver.gerrit import gerritconnection
from zuul.driver.gerrit import gerritmodel
from zuul.driver.gerrit import gerrittrigger
from zuul.driver.gerrit import gerritsource
from zuul.driver.gerrit import gerritreporter
from zuul.driver.util import to_list


class GerritDriver(Driver, ConnectionInterface, TriggerInterface,
                   SourceInterface, ReporterInterface):
    name = 'gerrit'

    def reconfigure(self, tenant):
        connection_checker_map = {}
        connection_filter_map = {}
        for manager in tenant.layout.pipeline_managers.values():
            pipeline = manager.pipeline
            for trigger in pipeline.triggers:
                if isinstance(trigger, gerrittrigger.GerritTrigger):
                    con = trigger.connection
                    checkers = connection_checker_map.setdefault(con, [])
                    for trigger_item in to_list(trigger.config):
                        if trigger_item['event'] == 'pending-check':
                            d = {}
                            if 'uuid' in trigger_item:
                                d['uuid'] = trigger_item['uuid']
                            elif 'scheme' in trigger_item:
                                d['scheme'] = trigger_item['scheme']
                            checkers.append(d)
            for event_filter in pipeline.event_filters:
                trigger = event_filter.trigger
                if isinstance(trigger, gerrittrigger.GerritTrigger):
                    con = trigger.connection
                    filters = connection_filter_map.setdefault(con, [])
                    filters.append(event_filter)
        for (con, checkers) in connection_checker_map.items():
            # TODO: This is not safe for multiple tenants
            con.setWatchedCheckers(checkers)
        for (con, filters) in connection_filter_map.items():
            con.setWatchedEventFilters(tenant.name, filters)

    def getConnection(self, name, config):
        return gerritconnection.GerritConnection(self, name, config)

    def getTrigger(self, connection, config=None):
        return gerrittrigger.GerritTrigger(self, connection, config)

    def getTriggerEventClass(self):
        return gerritmodel.GerritTriggerEvent

    def getSource(self, connection):
        return gerritsource.GerritSource(self, connection)

    def getReporter(self, connection, pipeline, config=None,
                    parse_context=None):
        return gerritreporter.GerritReporter(self, connection, config)

    def getTriggerSchema(self):
        return gerrittrigger.getSchema()

    def getReporterSchema(self):
        return gerritreporter.getSchema()

    def getRequireSchema(self):
        return gerritsource.getRequireSchema()

    def getRejectSchema(self):
        return gerritsource.getRejectSchema()
