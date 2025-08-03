# Copyright 2012-2014 Hewlett-Packard Development Company, L.P.
# Copyright 2013 OpenStack Foundation
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
from zuul.driver.zuul.zuulmodel import ZuulEventFilter
from zuul.driver.util import scalar_or_list, to_list, make_regex, ZUUL_REGEX


class ZuulTrigger(BaseTrigger):
    name = 'zuul'
    log = logging.getLogger("zuul.ZuulTrigger")

    def __init__(self, connection, config=None):
        super(ZuulTrigger, self).__init__(connection, config)
        self._handle_parent_change_enqueued_events = False
        self._handle_project_change_merged_events = False

    def getEventFilters(self, connection_name, trigger_conf,
                        parse_context):
        efilters = []
        pcontext = parse_context
        for trigger in to_list(trigger_conf):
            with pcontext.confAttr(trigger, 'event') as attr:
                types = [make_regex(x, pcontext)
                         for x in to_list(attr)]
            with pcontext.confAttr(trigger, 'pipeline') as attr:
                pipelines = [make_regex(x, pcontext)
                             for x in to_list(attr)]
            f = ZuulEventFilter(
                connection_name=connection_name,
                trigger=self,
                types=types,
                pipelines=pipelines,
                debug=trigger.get('debug'),
            )
            efilters.append(f)

        return efilters


def getSchema():
    zuul_trigger = {
        v.Required('event'):
        scalar_or_list(v.Any(
            'parent-change-enqueued',
            'project-change-merged',
            'image-build',
            'image-validate',
        )),
        'pipeline': scalar_or_list(v.Any(ZUUL_REGEX, str)),
        'debug': bool,
    }

    return zuul_trigger
