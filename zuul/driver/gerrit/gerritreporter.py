# Copyright 2013 Rackspace Australia
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
import voluptuous as v

from zuul.driver.gerrit.gerritsource import GerritSource
from zuul.driver.gerrit.gerritmodel import GerritChange
from zuul.lib.logutil import get_annotated_logger
from zuul.model import Change
from zuul.reporter import BaseReporter

# commentSizeLimit default set by Gerrit.  Gerrit is a bit
# vague about what this means, it says
#
#  Comments which exceed this size will be rejected ... Size
#  computation is approximate and may be off by roughly 1% ...
#  Default is 16k
#
# This magic number is int((16 << 10) * 0.98).  Robot comments
# are accounted for separately.
GERRIT_HUMAN_MESSAGE_LIMIT = 16056


class GerritReporter(BaseReporter):
    """Sends off reports to Gerrit."""

    name = 'gerrit'
    log = logging.getLogger("zuul.GerritReporter")

    def __init__(self, driver, connection, config=None):
        super(GerritReporter, self).__init__(driver, connection, config)
        action = self.config.copy()
        self._create_comment = action.pop('comment', True)
        self._submit = action.pop('submit', False)
        self._checks_api = action.pop('checks-api', None)
        self._notify = action.pop('notify', None)
        self._labels = {str(k): v for k, v in action.items()}

    def __repr__(self):
        return f"<GerritReporter: {self._action}>"

    def report(self, item, phase1=True, phase2=True):
        """Send a message to gerrit."""
        log = get_annotated_logger(self.log, item.event)

        ret = []
        for change in item.changes:
            err = self._reportChange(item, change, log, phase1, phase2)
            if err:
                ret.append(err)
        return ret

    def _reportChange(self, item, change, log, phase1=True, phase2=True):
        """Send a message to gerrit."""
        # If the source is no GerritSource we cannot report anything here.
        if not isinstance(change.project.source, GerritSource):
            return

        # We can only report changes, not plain branches
        if not isinstance(change, Change):
            return

        # For supporting several Gerrit connections we also must filter by
        # the canonical hostname.
        if change.project.source.connection.canonical_hostname != \
                self.connection.canonical_hostname:
            return

        comments = self.getFileComments(item, change)
        if self._create_comment:
            message = self._formatItemReport(item, change=change)

            b_len = len(message.encode('utf-8'))
            if b_len >= GERRIT_HUMAN_MESSAGE_LIMIT:
                log.info("Message too long, using short form")
                message = self._formatItemReport(item, change=change,
                                                 short=True)
            b_len = len(message.encode('utf-8'))
            if b_len >= GERRIT_HUMAN_MESSAGE_LIMIT:
                log.info("Message truncated %d > %d" %
                         (b_len, GERRIT_HUMAN_MESSAGE_LIMIT))
                message = ("%s... (truncated)" %
                           message[:GERRIT_HUMAN_MESSAGE_LIMIT - 20])
        else:
            message = ''

        log.debug("Report change %s, params %s, message: %s, comments: %s",
                  change, self.config, message, comments)
        if phase2 and self._submit and not hasattr(change, '_ref_sha'):
            # If we're starting to submit a bundle, save the current
            # ref sha for every item in the bundle.
            # Store a dict of project,branch -> sha so that if we have
            # duplicate project/branches, we only query once.
            ref_shas = {}
            for other_change in item.changes:
                if not isinstance(other_change, GerritChange):
                    continue
                key = (other_change.project, other_change.branch)
                ref_sha = ref_shas.get(key)
                if not ref_sha:
                    ref_sha = other_change.project.source.getRefSha(
                        other_change.project,
                        'refs/heads/' + other_change.branch)
                    ref_shas[key] = ref_sha
                other_change._ref_sha = ref_sha

        return self.connection.review(item, change, message,
                                      self._submit, self._labels,
                                      self._checks_api, self._notify,
                                      comments,
                                      phase1, phase2,
                                      zuul_event_id=item.event)

    def getSubmitAllowNeeds(self, manager):
        """Get a list of code review labels that are allowed to be
        "needed" in the submit records for a change, with respect
        to this queue.  In other words, the list of review labels
        this reporter itself is likely to set before submitting.
        """
        return self._labels


def getSchema():
    gerrit_reporter = v.Any(str, v.Schema(dict))
    return gerrit_reporter
