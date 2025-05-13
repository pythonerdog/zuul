# Copyright 2019 Red Hat, Inc.
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

import re
import logging
import urllib

from zuul.model import Project
from zuul.source import BaseSource
from zuul.driver.gitlab.gitlabmodel import GitlabRefFilter
from zuul.driver.util import scalar_or_list, to_list
from zuul.zk.change_cache import ChangeKey


class GitlabSource(BaseSource):
    name = 'gitlab'
    log = logging.getLogger("zuul.source.GitlabSource")

    def __init__(self, driver, connection, config=None):
        hostname = connection.canonical_hostname
        super(GitlabSource, self).__init__(driver, connection,
                                           hostname, config)
        self.change_re = re.compile(r"/(.*?)/(?:-/)?merge_requests/(\d+)")

    def getRefSha(self, project, ref):
        """Return a sha for a given project ref."""
        raise NotImplementedError()

    def waitForRefSha(self, project, ref, old_sha=''):
        """Block until a ref shows up in a given project."""
        raise NotImplementedError()

    def isMerged(self, change, head=None):
        """Determine if change is merge."""
        if not change.number:
            return True
        return change.is_merged

    def canMerge(self, change, allow_needs, event=None, allow_refresh=False):
        """Determine if change can merge."""
        if not change.number:
            return True
        return self.connection.canMerge(change, allow_needs, event=event)

    def postConfig(self):
        """Called after configuration has been processed."""
        raise NotImplementedError()

    def getChangeKey(self, event):
        connection_name = self.connection.connection_name
        if event.change_number:
            return ChangeKey(connection_name, event.project_name,
                             'MergeRequest',
                             str(event.change_number),
                             str(event.patch_number))
        revision = f'{event.oldrev}..{event.newrev}'
        if event.ref and event.ref.startswith('refs/tags/'):
            tag = event.ref[len('refs/tags/'):]
            return ChangeKey(connection_name, event.project_name,
                             'Tag', tag, revision)
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
        try:
            parsed = urllib.parse.urlparse(url)
        except ValueError:
            return None
        m = self.change_re.match(parsed.path)
        if not m:
            return None
        project_name = m.group(1)
        try:
            num = int(m.group(2))
        except ValueError:
            return None
        mr = self.connection.getMR(project_name, num)
        if not mr:
            return None
        change_key = ChangeKey(self.connection.connection_name, project_name,
                               'MergeRequest',
                               str(num), mr['sha'])
        change = self.connection._getChange(change_key, event=event)
        return change

    def getChangesDependingOn(self, change, projects, tenant):
        return self.connection.getChangesDependingOn(
            change, projects, tenant)

    def getCachedChanges(self):
        yield from self.connection._change_cache

    def getProject(self, name):
        p = self.connection.getProject(name)
        if not p:
            p = Project(name, self)
            self.connection.addProject(p)
        return p

    def getProjectBranches(self, project, tenant, min_ltime=-1):
        return self.connection.getProjectBranches(project, tenant, min_ltime)

    def getProjectBranchCacheLtime(self):
        return self.connection._branch_cache.ltime

    def getProjectOpenChanges(self, project):
        """Get the open changes for a project."""
        raise NotImplementedError()

    def updateChange(self, change, history=None):
        """Update information for a change."""
        raise NotImplementedError()

    def getGitUrl(self, project):
        """Get the git url for a project."""
        return self.connection.getGitUrl(project)

    def getGitwebUrl(self, project, sha=None):
        """Get the git-web url for a project."""
        raise NotImplementedError()

    def getRequireFilters(self, config, parse_context):
        f = GitlabRefFilter(
            connection_name=self.connection.connection_name,
            open=config.get('open'),
            merged=config.get('merged'),
            approved=config.get('approved'),
            labels=to_list(config.get('labels')),
        )
        return [f]

    def getRejectFilters(self, config, parse_context):
        raise NotImplementedError()

    def getRefForChange(self, change):
        return "refs/merge-requests/%s/head" % change

    def setChangeAttributes(self, change, **attrs):
        return self.connection.updateChangeAttributes(change, **attrs)


# Require model
def getRequireSchema():
    require = {
        'open': bool,
        'merged': bool,
        'approved': bool,
        'labels': scalar_or_list(str)
    }
    return require


def getRejectSchema():
    reject = {}
    return reject
