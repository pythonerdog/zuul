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

import logging
import os

from zuul.executor.sensors import SensorInterface
from zuul.lib.config import get_default


def get_avail_hdd_inode_pct(path):
    s = os.statvfs(path)
    blocks_used = float(s.f_blocks - s.f_bfree)
    blocks_percent = (blocks_used / s.f_blocks) * 100
    blocks_percent_avail = 100.0 - blocks_percent

    try:
        files_used = float(s.f_files - s.f_ffree)
        files_percent = (files_used / s.f_files) * 100
        files_percent_avail = 100.0 - files_percent
    except ZeroDivisionError:
        files_percent_avail = 100.0  # Assume no limit if f_files=0.

    return (blocks_percent_avail, files_percent_avail)


class HDDSensor(SensorInterface):
    log = logging.getLogger("zuul.executor.sensor.hdd")

    def __init__(self, statsd, base_key, config=None):
        super().__init__(statsd, base_key)
        self.min_avail_hdd = float(
            get_default(config, 'executor', 'min_avail_hdd', '5.0'))
        self.min_avail_inodes = float(
            get_default(config, 'executor', 'min_avail_inodes', '5.0'))
        self.state_dir = get_default(
            config, 'executor', 'state_dir', '/var/lib/zuul', expand_user=True)

    def isOk(self):
        avail_hdd_pct, avail_inodes_pct = get_avail_hdd_inode_pct(
            self.state_dir)

        if self.statsd:
            # We multiply the percentage by 100 so we can report it to
            # 2 decimal points.
            self.statsd.gauge(self.base_key + '.pct_used_hdd',
                              int((100.0 - avail_hdd_pct) * 100))
            self.statsd.gauge(self.base_key + '.pct_used_inodes',
                              int((100.0 - avail_inodes_pct) * 100))

        if avail_hdd_pct < self.min_avail_hdd:
            return False, "low disk space {:3.1f}% < {}".format(
                avail_hdd_pct, self.min_avail_hdd)
        if avail_inodes_pct < self.min_avail_inodes:
            return False, "low disk inodes {:3.1f}% < {}".format(
                avail_inodes_pct, self.min_avail_inodes)

        return True, "hdd {:3.1f}% >= {}%, {:3.1f}% >= {}%".format(
            avail_hdd_pct, self.min_avail_hdd,
            avail_inodes_pct, self.min_avail_inodes)
