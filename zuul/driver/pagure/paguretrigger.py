# Copyright 2018 Red Hat, Inc.
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
from zuul.driver.pagure.paguremodel import PagureEventFilter
from zuul.driver.util import scalar_or_list, to_list, make_regex, ZUUL_REGEX


class PagureTrigger(BaseTrigger):
    name = 'pagure'
    log = logging.getLogger("zuul.trigger.PagureTrigger")

    def getEventFilters(self, connection_name, trigger_config,
                        parse_context):
        efilters = []
        pcontext = parse_context
        for trigger in to_list(trigger_config):
            with pcontext.confAttr(trigger, 'event') as attr:
                types = [make_regex(x, pcontext)
                         for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'ref') as attr:
                refs = [make_regex(x, pcontext)
                        for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'comment') as attr:
                comments = [make_regex(x, pcontext)
                            for x in to_list(attr)]

            f = PagureEventFilter(
                connection_name=connection_name,
                trigger=self,
                types=types,
                actions=to_list(trigger.get('action')),
                refs=refs,
                comments=comments,
                statuses=to_list(trigger.get('status')),
                tags=to_list(trigger.get('tag')),
            )
            efilters.append(f)

        return efilters

    def onPullRequest(self, payload):
        pass


def getSchema():
    pagure_trigger = {
        v.Required('event'):
            # Cannot use same event type than github as it collapse
            # with Registered github triggers if any. The Event filter
            # does not have the connections info like the Ref filter (require)
            # have. See manager/__init__.py:addChange
            scalar_or_list(v.Any('pg_pull_request',
                                 'pg_pull_request_review',
                                 'pg_push')),
        'action': scalar_or_list(str),
        'ref': scalar_or_list(v.Any(ZUUL_REGEX, str)),
        'comment': scalar_or_list(v.Any(ZUUL_REGEX, str)),
        'status': scalar_or_list(str),
        'tag': scalar_or_list(str)
    }

    return pagure_trigger
