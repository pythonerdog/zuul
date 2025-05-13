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

"""
Run this to clean up leaked lock entries in the blob store (but only
if there are too many for Zuul to deal with on its own).

Run this command to get a list of potential keys:

  ./bin/zkSnapShotToolkit.sh /data/version-2/snapshot.XXX \
    | grep /zuul/cache/blob/lock

Pass the result as input to this script.
"""

import argparse
import sys

import kazoo.client
from kazoo.exceptions import NotEmptyError


class Cleanup:
    def __init__(self, args):
        kwargs = {}
        if args.cert:
            kwargs['use_ssl'] = True
            kwargs['keyfile'] = args.key
            kwargs['certfile'] = args.cert
            kwargs['ca'] = args.ca
        self.client = kazoo.client.KazooClient(args.host, **kwargs)
        self.client.start()

    def run(self):
        prefix = '/zuul/cache/blob/lock/'

        for line in sys.stdin:
            line = line.strip()
            if not line.startswith(prefix):
                continue
            key = line[len(prefix):]

            blob_path = f"/zuul/cache/blob/data/{key[0:2]}/{key}"
            lock_path = f"/zuul/cache/blob/lock/{key}"
            if self.client.exists(blob_path):
                continue
            try:
                self.client.delete(lock_path)
            except NotEmptyError:
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('host', help='ZK host string')
    parser.add_argument('--cert', help='Path to TLS certificate')
    parser.add_argument('--key', help='Path to TLS key')
    parser.add_argument('--ca', help='Path to TLS CA cert')
    args = parser.parse_args()

    clean = Cleanup(args)
    clean.run()
