# Copyright 2014 Puppet Labs Inc
# Copyright 2023 Acme Gating, LLC
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
import urllib
import logging
import time
import voluptuous as v

from zuul.source import BaseSource
from zuul.model import MERGER_MAP, Project
from zuul.driver.github.githubmodel import GithubRefFilter
from zuul.driver.util import scalar_or_list
from zuul.zk.change_cache import ChangeKey
from zuul.zk.components import COMPONENT_REGISTRY


class GithubSource(BaseSource):
    name = 'github'
    log = logging.getLogger("zuul.source.GithubSource")

    def __init__(self, driver, connection, config=None):
        hostname = connection.canonical_hostname
        super(GithubSource, self).__init__(driver, connection,
                                           hostname, config)

    def getRefSha(self, project, ref):
        """Return a sha for a given project ref."""
        raise NotImplementedError()

    def waitForRefSha(self, project, ref, old_sha=''):
        """Block until a ref shows up in a given project."""
        raise NotImplementedError()

    def isMerged(self, change, head=None):
        """Determine if change is merged."""
        if not change.number:
            # Not a pull request, considering merged.
            return True
        # We don't need to perform another query because the API call
        # to perform the merge will ensure this is updated.
        return change.is_merged

    def canMerge(self, change, allow_needs, event=None, allow_refresh=False):
        """Determine if change can merge."""

        if not change.number:
            # Not a pull request, considering merged.
            return True
        return self.connection.canMerge(
            change, allow_needs, event=event, allow_refresh=allow_refresh
        )

    def postConfig(self):
        """Called after configuration has been processed."""
        pass

    def getChangeKey(self, event):
        connection_name = self.connection.connection_name
        if event.change_number:
            return ChangeKey(connection_name, event.project_name,
                             'PullRequest',
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

    change_re = re.compile(r"/(.*?)/(.*?)/pull/(\d+)[\w]*")

    def getChangeByURL(self, url, event):
        try:
            parsed = urllib.parse.urlparse(url)
        except ValueError:
            return None
        m = self.change_re.match(parsed.path)
        if not m:
            return None
        org = m.group(1)
        proj = m.group(2)
        try:
            num = int(m.group(3))
        except ValueError:
            return None
        pull, pr_obj = self.connection.getPull(
            '%s/%s' % (org, proj), int(num), event=event)
        if not pull:
            return None
        proj = pull.get('base').get('repo').get('full_name')
        change_key = ChangeKey(self.connection.connection_name, proj,
                               'PullRequest',
                               str(num),
                               pull.get('head').get('sha'))
        change = self.connection._getChange(change_key, event=event)
        return change

    def getChangesDependingOn(self, change, projects, tenant):
        return self.connection.getChangesDependingOn(change, projects, tenant)

    def getCachedChanges(self):
        return list(self.connection._change_cache)

    def getProject(self, name):
        p = self.connection.getProject(name)
        if not p:
            p = Project(name, self)
            self.connection.addProject(p)
        return p

    def getProjectBranches(self, project, tenant, min_ltime=-1):
        return self.connection.getProjectBranches(project, tenant, min_ltime)

    def getProjectMergeModes(self, project, tenant, min_ltime=-1):
        return self.connection.getProjectMergeModes(project, tenant, min_ltime)

    def getProjectDefaultBranch(self, project, tenant, min_ltime=-1):
        # We have to return something here, so try to get it from the
        # cache, and if that fails, return the Zuul default.
        try:
            default_branch = self.connection.getProjectDefaultBranch(
                project, tenant, min_ltime)
        except Exception:
            default_branch = None
        if default_branch is None:
            return super().getProjectDefaultBranch(project, tenant, min_ltime)
        return default_branch

    def getProjectBranchCacheLtime(self):
        return self.connection._branch_cache.ltime

    def getProjectOpenChanges(self, project):
        """Get the open changes for a project."""
        raise NotImplementedError()

    def getProjectDefaultMergeMode(self, project, valid_modes=None):
        if COMPONENT_REGISTRY.model_api < 18:
            return 'merge'
        github_version = self.connection._github_client_manager._github_version
        if github_version and github_version < (3, 8):
            merge_mode = 'merge-recursive'
        else:
            merge_mode = 'merge-ort'
        try:
            if valid_modes and MERGER_MAP[merge_mode] in valid_modes:
                return merge_mode
        except Exception:
            self.log.exception("Failed to get valid merge modes:")
        return 'merge'

    def updateChange(self, change, history=None):
        """Update information for a change."""
        raise NotImplementedError()

    def getGitUrl(self, project):
        """Get the git url for a project."""
        return self.connection.getGitUrl(project)

    def getRetryTimeout(self, project):
        """Get the retry timeout for a project."""
        return self.connection.repo_retry_timeout

    def getGitwebUrl(self, project, sha=None):
        """Get the git-web url for a project."""
        return self.connection.getGitwebUrl(project, sha)

    def _ghTimestampToDate(self, timestamp):
        return time.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')

    def getRequireFilters(self, config, parse_context):
        f = GithubRefFilter.requiresFromConfig(
            self.connection.connection_name,
            config)
        return [f]

    def getRejectFilters(self, config, parse_context):
        f = GithubRefFilter.rejectFromConfig(
            self.connection.connection_name,
            config)
        return [f]

    def getRefForChange(self, change):
        return "refs/pull/%s/head" % change

    def setChangeAttributes(self, change, **attrs):
        return self.connection.updateChangeAttributes(change, **attrs)


review = v.Schema({'username': str,
                   'email': str,
                   'older-than': str,
                   'newer-than': str,
                   'type': str,
                   'permission': v.Any('read', 'write', 'admin'),
                   })


def getRequireSchema():
    require = {'status': scalar_or_list(str),
               'review': scalar_or_list(review),
               'open': bool,
               'merged': bool,
               'current-patchset': bool,
               'draft': bool,
               'label': scalar_or_list(str)}
    return require


def getRejectSchema():
    reject = {'status': scalar_or_list(str),
              'review': scalar_or_list(review),
              'open': bool,
              'merged': bool,
              'current-patchset': bool,
              'draft': bool,
              'label': scalar_or_list(str)}
    return reject
