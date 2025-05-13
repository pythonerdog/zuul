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

import datetime

from apscheduler.triggers.cron import CronTrigger


class ZuulCronTrigger(CronTrigger):
    def __init__(self, *args, **kw):
        self._zuul_jitter = kw.pop('jitter')
        super().__init__(*args, **kw)

    def get_next_fire_time(self, previous_fire_time, now):
        next_time = super().get_next_fire_time(previous_fire_time, now)
        if self._zuul_jitter:
            next_time = next_time + datetime.timedelta(
                seconds=self._zuul_jitter)
            if self.end_date:
                next_time = min(next_time, self.end_date)
        return next_time
