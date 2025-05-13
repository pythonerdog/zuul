# Copyright 2017 Red Hat, Inc.
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

import logging
import voluptuous as v
from zuul.trigger import BaseTrigger
from zuul.driver.git.gitmodel import GitEventFilter
from zuul.driver.util import scalar_or_list, to_list, make_regex, ZUUL_REGEX


class GitTrigger(BaseTrigger):
    name = 'git'
    log = logging.getLogger("zuul.GitTrigger")

    def getEventFilters(self, connection_name, trigger_conf,
                        parse_context):
        efilters = []
        pcontext = parse_context
        for trigger in to_list(trigger_conf):
            with pcontext.confAttr(trigger, 'ref') as attr:
                refs = [make_regex(x, pcontext)
                        for x in to_list(attr)]

            f = GitEventFilter(
                connection_name=connection_name,
                trigger=self,
                types=to_list(trigger['event']),
                refs=refs,
                ignore_deletes=trigger.get(
                    'ignore-deletes', True)
            )
            efilters.append(f)

        return efilters


def getSchema():
    git_trigger = {
        v.Required('event'):
            scalar_or_list(v.Any('ref-updated')),
        'ref': scalar_or_list(v.Any(ZUUL_REGEX, str)),
        'ignore-deletes': bool,
    }

    return git_trigger
