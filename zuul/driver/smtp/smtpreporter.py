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

from zuul.lib.logutil import get_annotated_logger
from zuul.reporter import BaseReporter


class SMTPReporter(BaseReporter):
    """Sends off reports to emails via SMTP."""

    name = 'smtp'
    log = logging.getLogger("zuul.SMTPReporter")

    def report(self, item, phase1=True, phase2=True):
        """Send the compiled report message via smtp."""
        if not phase1:
            return
        log = get_annotated_logger(self.log, item.event)
        message = self._formatItemReport(item)

        log.debug("Report %s, params %s, message: %s",
                  item, self.config, message)

        from_email = self.config['from'] \
            if 'from' in self.config else None
        to_email = self.config['to'] \
            if 'to' in self.config else None

        if 'subject' in self.config:
            subject = self.config['subject'].format(
                change=item.changes[0],
                changes=item.changes,
                pipeline=item.manager.pipeline.getSafeAttributes())
        else:
            subject = "Report for changes {changes} against {ref}".format(
                changes=' '.join([str(c) for c in item.changes]),
                ref=' '.join([c.ref for c in item.changes]))

        self.connection.sendMail(subject, message, from_email, to_email,
                                 zuul_event_id=item.event)
        return []


def getSchema():
    smtp_reporter = v.Schema({
        'to': str,
        'from': str,
        'subject': str,
    })
    return smtp_reporter
