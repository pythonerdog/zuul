# Copyright 2015 Rackspace Australia
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

import logging
import re
from collections import OrderedDict
from urllib.parse import urlparse

import zuul.driver.zuul
import zuul.driver.gerrit
import zuul.driver.git
import zuul.driver.github
import zuul.driver.smtp
import zuul.driver.timer
import zuul.driver.sql
import zuul.driver.bubblewrap
import zuul.driver.nullwrap
import zuul.driver.mqtt
import zuul.driver.pagure
import zuul.driver.gitlab
import zuul.driver.elasticsearch
import zuul.driver.aws
import zuul.driver.openstack
from zuul.connection import BaseConnection
from zuul.driver import (
    ProviderInterface,
    ReporterInterface,
    SourceInterface,
    TriggerInterface,
)


class DefaultConnection(BaseConnection):
    pass


class ConnectionRegistry(object):
    """A registry of connections"""

    log = logging.getLogger("zuul.ConnectionRegistry")

    def __init__(self, check_bwrap=False):
        self.connections = OrderedDict()
        self.drivers = {}

        self.registerDriver(zuul.driver.zuul.ZuulDriver())
        self.registerDriver(zuul.driver.gerrit.GerritDriver())
        self.registerDriver(zuul.driver.git.GitDriver())
        self.registerDriver(zuul.driver.github.GithubDriver())
        self.registerDriver(zuul.driver.smtp.SMTPDriver())
        self.registerDriver(zuul.driver.timer.TimerDriver())
        self.registerDriver(zuul.driver.sql.SQLDriver())
        self.registerDriver(
            zuul.driver.bubblewrap.BubblewrapDriver(check_bwrap))
        self.registerDriver(zuul.driver.nullwrap.NullwrapDriver())
        self.registerDriver(zuul.driver.mqtt.MQTTDriver())
        self.registerDriver(zuul.driver.pagure.PagureDriver())
        self.registerDriver(zuul.driver.gitlab.GitlabDriver())
        self.registerDriver(zuul.driver.elasticsearch.ElasticsearchDriver())
        self.registerDriver(zuul.driver.aws.AwsDriver())
        self.registerDriver(zuul.driver.openstack.OpenstackDriver())

    def registerDriver(self, driver):
        if driver.name in self.drivers:
            raise Exception("Driver %s already registered" % driver.name)
        self.drivers[driver.name] = driver

    def registerScheduler(self, sched):
        for driver_name, driver in self.drivers.items():
            driver.registerScheduler(sched)
        for connection_name, connection in self.connections.items():
            connection.registerScheduler(sched)

    def load(self, zk_client, component_registry):
        for connection in self.connections.values():
            connection.onLoad(zk_client, component_registry)

    def reconfigureDrivers(self, tenant):
        for driver in self.drivers.values():
            if hasattr(driver, 'reconfigure'):
                driver.reconfigure(tenant)

    def stop(self):
        for connection_name, connection in self.connections.items():
            connection.onStop()
        for driver in self.drivers.values():
            driver.stop()

    def configure(self, config, database=False, sources=False,
                  triggers=False, reporters=False, providers=False):
        # Register connections from the config
        connections = OrderedDict()

        if database and 'database' in config.sections():
            driver = self.drivers['sql']
            con_config = dict(config.items('database'))

            connection = driver.getConnection('database', con_config)
            connections['database'] = connection

        for section_name in config.sections():
            con_match = re.match(r'^connection ([\'\"]?)(.*)(\1)$',
                                 section_name, re.I)
            if not con_match:
                continue
            con_name = con_match.group(2)
            con_config = dict(config.items(section_name))

            if 'driver' not in con_config:
                raise Exception("No driver specified for connection %s."
                                % con_name)

            con_driver = con_config['driver']
            if (con_driver not in self.drivers) or con_driver == 'sql':
                raise Exception("Unknown driver, %s, for connection %s"
                                % (con_config['driver'], con_name))

            driver = self.drivers[con_driver]

            if (database and driver.name == 'sql' or
                sources and isinstance(driver, SourceInterface) or
                triggers and isinstance(driver, TriggerInterface) or
                reporters and isinstance(driver, ReporterInterface) or
                providers and isinstance(driver, ProviderInterface)):
                # Only create connections for the requested drivers
                connection = driver.getConnection(con_name, con_config)
                connections[con_name] = connection

        # If the [gerrit] or [smtp] sections still exist, load them in as a
        # connection named 'gerrit' or 'smtp' respectfully

        if 'gerrit' in config.sections():
            if 'gerrit' in connections:
                self.log.warning(
                    "The legacy [gerrit] section will be ignored in favour"
                    " of the [connection gerrit].")
            else:
                driver = self.drivers['gerrit']
                connections['gerrit'] = \
                    driver.getConnection(
                        'gerrit', dict(config.items('gerrit')))

        if 'smtp' in config.sections():
            if 'smtp' in connections:
                self.log.warning(
                    "The legacy [smtp] section will be ignored in favour"
                    " of the [connection smtp].")
            else:
                driver = self.drivers['smtp']
                connections['smtp'] = \
                    driver.getConnection(
                        'smtp', dict(config.items('smtp')))

        # Create default connections for drivers which need no
        # connection information (e.g., 'timer' or 'zuul').
        for driver in self.drivers.values():
            if not hasattr(driver, 'getConnection'):
                if (database and driver.name == 'sql' or
                    sources and isinstance(driver, SourceInterface) or
                    triggers and isinstance(driver, TriggerInterface) or
                    reporters and isinstance(driver, ReporterInterface) or
                    providers and isinstance(driver, ProviderInterface)):
                    connections[driver.name] = DefaultConnection(
                        driver, driver.name, {})

        if database:
            if 'database' not in connections:
                raise Exception("Database configuration is required")

        self.connections = connections

    def getSqlConnection(self):
        """
        Gets the SQL connection. This is either the connection
        described in the [database] section, or the first configured
        connection.

        :return: The SQL connection.

        """
        connection = self.connections.get('database')
        if not connection:
            raise Exception("No SQL connections")
        return connection

    def getSqlReporter(self, pipeline):
        """
        Gets the SQL reporter. Such reporter is based on
        `getSqlConnection`.

        :param pipeline: Pipeline
        :return: The SQL reporter

        """
        connection = self.getSqlConnection()
        return connection.driver.getReporter(connection, pipeline)

    def getSource(self, connection_name):
        connection = self.connections[connection_name]
        return connection.driver.getSource(connection)

    def getSources(self):
        sources = []
        for connection in self.connections.values():
            if hasattr(connection.driver, 'getSource'):
                sources.append(connection.driver.getSource(connection))
        return sources

    def getProviderConnections(self):
        return [c for c in self.connections.values()
                if isinstance(c.driver, ProviderInterface)]

    def getReporter(self, connection_name, pipeline, config=None,
                    parse_context=None):
        connection = self.connections[connection_name]
        return connection.driver.getReporter(
            connection, pipeline, config, parse_context)

    def getTrigger(self, connection_name, config=None):
        connection = self.connections[connection_name]
        return connection.driver.getTrigger(connection, config)

    def getTriggerEventClass(self, driver_name: str):
        driver = self.drivers[driver_name]
        return driver.getTriggerEventClass()

    def getSourceByHostname(self, hostname):
        for connection in self.connections.values():
            if hasattr(connection, 'canonical_hostname'):
                if connection.canonical_hostname == hostname:
                    return self.getSource(connection.connection_name)
            if hasattr(connection, 'server'):
                if connection.server == hostname:
                    return self.getSource(connection.connection_name)
            if hasattr(connection, 'baseurl'):
                if urlparse(connection.baseurl).hostname == hostname:
                    return self.getSource(connection.connection_name)
        return None

    def getSourceByCanonicalHostname(self, canonical_hostname):
        for connection in self.connections.values():
            if hasattr(connection, 'canonical_hostname'):
                if connection.canonical_hostname == canonical_hostname:
                    return self.getSource(connection.connection_name)
        return None
