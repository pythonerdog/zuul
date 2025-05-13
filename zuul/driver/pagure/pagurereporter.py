# Copyright 2018 Red Hat, Inc.
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

import time
import logging

import voluptuous as v

from zuul.reporter import BaseReporter
from zuul.exceptions import DeprecationWarning, MergeFailure
from zuul.driver.pagure.paguresource import PagureSource


class PagureStatusUrlDeprecation(DeprecationWarning):
    zuul_error_name = 'Pagure status-url Deprecation'
    zuul_error_message = """The 'status-url' reporter attribute
is deprecated."""


class PagureReporter(BaseReporter):
    """Sends off reports to Pagure."""

    name = 'pagure'
    log = logging.getLogger("zuul.PagureReporter")

    def __init__(self, driver, connection, pipeline, config=None,
                 parse_context=None):
        super(PagureReporter, self).__init__(driver, connection, config,
                                             parse_context)
        self._commit_status = self.config.get('status', None)
        self._create_comment = self.config.get('comment', True)
        self._merge = self.config.get('merge', False)

        if 'status-url' in self.config and parse_context:
            parse_context.accumulator.addError(PagureStatusUrlDeprecation)

    def getContext(self, manager):
        return "{}/{}".format(manager.tenant.name,
                              manager.pipeline.name)

    def report(self, item, phase1=True, phase2=True):
        """Report on an event."""
        for change in item.changes:
            self._reportChange(item, change, phase1, phase2)
        return []

    def _reportChange(self, item, change, phase1=True, phase2=True):
        """Report on an event."""

        # If the source is not PagureSource we cannot report anything here.
        if not isinstance(change.project.source, PagureSource):
            return

        # For supporting several Pagure connections we also must filter by
        # the canonical hostname.
        if change.project.source.connection.canonical_hostname != \
                self.connection.canonical_hostname:
            return

        if phase1:
            if self._commit_status is not None:
                if (hasattr(change, 'patchset') and
                        change.patchset is not None):
                    self.setCommitStatus(item, change)
                elif (hasattr(change, 'newrev') and
                        change.newrev is not None):
                    self.setCommitStatus(item, change)
            if hasattr(change, 'number'):
                if self._create_comment:
                    self.addPullComment(item, change)
        if phase2 and self._merge:
            self.mergePull(item, change)
            if not change.is_merged:
                msg = self._formatItemReportMergeConflict(item, change)
                self.addPullComment(item, change, msg)

    def _formatItemReportJobs(self, item):
        # Return the list of jobs portion of the report
        ret = ''
        jobs_fields, skipped = self._getItemReportJobsFields(item)
        for job_fields in jobs_fields:
            ret += '- [%s](%s) : %s%s%s%s\n' % job_fields[:6]
        if skipped:
            jobtext = 'job' if skipped == 1 else 'jobs'
            ret += 'Skipped %i %s\n' % (skipped, jobtext)
        return ret

    def addPullComment(self, item, change, comment=None):
        message = comment or self._formatItemReport(item)
        project = change.project.name
        pr_number = change.number
        self.log.debug(
            'Reporting change %s, params %s, message: %s' %
            (change, self.config, message))
        self.connection.commentPull(project, pr_number, message)

    def setCommitStatus(self, item, change):
        project = change.project.name
        if hasattr(change, 'patchset'):
            sha = change.patchset
        elif hasattr(change, 'newrev'):
            sha = change.newrev
        state = self._commit_status
        change_number = change.number

        url = item.formatItemUrl()
        description = '%s status: %s (%s)' % (
            item.manager.pipeline.name, self._commit_status, sha)

        self.log.debug(
            'Reporting change %s, params %s, '
            'context: %s, state: %s, description: %s, url: %s' %
            (change, self.config,
             self.getContext(item.manager), state, description, url))

        self.connection.setCommitStatus(
            project, change_number, state, url, description,
            self.getContext(item.manager))

    def mergePull(self, item, change):
        project = change.project.name
        pr_number = change.number

        for i in [1, 2]:
            try:
                self.connection.mergePull(project, pr_number)
                change.is_merged = True
                return
            except MergeFailure:
                self.log.exception(
                    'Merge attempt of change %s  %s/2 failed.' %
                    (change, i), exc_info=True)
                if i == 1:
                    time.sleep(2)
        self.log.warning(
            'Merge of change %s failed after 2 attempts, giving up' %
            change)

    def getSubmitAllowNeeds(self, manager):
        return []


def getSchema():
    pagure_reporter = v.Schema({
        'status': v.Any('pending', 'success', 'failure'),
        # MODEL_API < 31
        'status-url': str,
        'comment': bool,
        'merge': bool,
    })
    return pagure_reporter
