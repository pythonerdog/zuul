# Copyright 2025 Acme Gating, LLC
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
import os
import os.path

from zuul.executor.sensors import SensorInterface


class ProcessSensor(SensorInterface):
    log = logging.getLogger("zuul.executor.sensor.process")

    def __init__(self, statsd, base_key, config=None):
        super().__init__(statsd, base_key)
        # The executor and ansible require a number of processes to function
        # minimally: the executor itself, ansible, ssh control persistence,
        # ssh and so on. Set a minimum of room for 10 processes before we
        # stop.
        self._min_headroom = 10
        self._safety_factor = 0.05
        self._uid = os.getuid()
        self._pid_max = self._get_pid_max()
        self._root_cgroup_max_file = '/sys/fs/cgroup/pids.max'
        self._root_cgroup_cur_file = '/sys/fs/cgroup/pids.current'
        # This appears to be systemd specific behavior with cgroups that
        # reflects the ulimit values. This way we don't need to have a
        # separate system for ulimit checking.
        self._user_cgroup_max_file = f'/sys/fs/cgroup/user.slice' \
                                     f'/user-{self._uid}.slice/pids.max'
        self._user_cgroup_cur_file = f'/sys/fs/cgroup/user.slice' \
                                     f'/user-{self._uid}.slice/pids.current'

    def _get_pid_max(self):
        # Default for x86_64
        default = 2 ** 22
        path = '/proc/sys/kernel/pid_max'
        if os.path.exists(path):
            with open(path) as f:
                s = f.read().strip()
                try:
                    i = int(s)
                except ValueError:
                    self.log.exception('Unable to determine pid_max')
                    i = default
                return i
        else:
            return default

    def isOk(self):
        # Processes running in the root cgroup won't have these values
        # but containers do.
        # If no max is found assume pid_max. If no current usage is found
        # assume 1 for the current process.
        root_max = self._get_root_cgroup_max() or self._pid_max
        root_current = self._get_root_cgroup_current() or 1
        # Processes running under systemd will have these values.
        user_max = self._get_user_slice_max() or self._pid_max
        user_current = self._get_user_slice_current() or 1

        limit = min(root_max, user_max)
        usage = max(root_current, user_current)
        min_headroom = limit * self._safety_factor
        if min_headroom < self._min_headroom:
            min_headroom = self._min_headroom
        # This shouldn't ever be negative but I'm not sure if you can reduce
        # cgroup limits below the current usage at runtime.
        headroom = max(limit - usage, 0)

        if self.statsd:
            self.statsd.gauge(self.base_key + '.max_process',
                              limit)
            self.statsd.gauge(self.base_key + '.cur_process',
                              usage)

        if min_headroom >= headroom:
            return False, f'high process utilization: {usage} max: {limit}'
        return True, f'process utilization: {usage} max: {limit}'

    def _get_root_cgroup_max(self):
        return self._get_cgroup_value(self._root_cgroup_max_file)

    def _get_root_cgroup_current(self):
        return self._get_cgroup_value(self._root_cgroup_cur_file)

    def _get_user_slice_max(self):
        return self._get_cgroup_value(self._user_cgroup_max_file)

    def _get_user_slice_current(self):
        return self._get_cgroup_value(self._user_cgroup_cur_file)

    def _get_cgroup_value(self, path):
        if os.path.exists(path):
            with open(path) as f:
                s = f.read().strip()
                if s == 'max':
                    return self._pid_max
                else:
                    try:
                        i = int(s)
                    except ValueError:
                        self.log.exception('Unable to convert cgroup '
                                           'process value')
                        i = None
                    return i
        else:
            return None
