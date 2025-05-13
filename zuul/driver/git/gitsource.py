# Copyright 2012 Hewlett-Packard Development Company, L.P.
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
from zuul.source import BaseSource
from zuul.model import Project
from zuul.zk.change_cache import ChangeKey


class GitSource(BaseSource):
    name = 'git'
    log = logging.getLogger("zuul.source.Git")

    def __init__(self, driver, connection, config=None):
        hostname = connection.canonical_hostname
        super(GitSource, self).__init__(driver, connection,
                                        hostname, config)

    def getRefSha(self, project, ref):
        raise NotImplementedError()

    def isMerged(self, change, head=None):
        raise NotImplementedError()

    def canMerge(self, change, allow_needs, event=None, allow_refresh=False):
        raise NotImplementedError()

    def getChangeKey(self, event):
        connection_name = self.connection.connection_name
        revision = f'{event.oldrev}..{event.newrev}'
        if event.ref and event.ref.startswith('refs/heads/'):
            branch = event.ref[len('refs/heads/'):]
            return ChangeKey(connection_name, event.project_name,
                             'Branch', branch, revision)
        if event.ref:
            return ChangeKey(connection_name, event.project_name,
                             'Ref', event.ref, revision)
        self.log.warning("Unable to format change key for %s" % (self,))

    def getChange(self, change_key, refresh=False, event=None):
        return self.connection.getChange(change_key, refresh=refresh,
                                         event=event)

    def getChangeByURL(self, url, event):
        return None

    def getChangesDependingOn(self, change, projects, tenant):
        return []

    def getCachedChanges(self):
        return []

    def getProject(self, name):
        p = self.connection.getProject(name)
        if not p:
            p = Project(name, self)
            self.connection.addProject(p)
        return p

    def getProjectBranches(self, project, tenant, min_ltime=-1):
        return self.connection.getProjectBranches(project, tenant, min_ltime)

    def getProjectBranchCacheLtime(self):
        return -1

    def getGitUrl(self, project):
        return self.connection.getGitUrl(project)

    def getProjectOpenChanges(self, project):
        raise NotImplementedError()

    def getRequireFilters(self, config, parse_context):
        return []

    def getRejectFilters(self, config, parse_context):
        return []

    def getRefForChange(self, change):
        raise NotImplementedError()
