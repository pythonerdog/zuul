# Copyright 2022 Acme Gating, LLC
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

# Dump the data in ZK to the local filesystem.

import argparse
import os
import zlib

import kazoo.client


def getTree(client, root, path, decompress=False):
    try:
        data, zstat = client.get(path)
    except kazoo.exceptions.NoNodeError:
        print(f"No node at {path}")
        return

    if decompress:
        try:
            data = zlib.decompress(data)
        except Exception:
            pass

    os.makedirs(root + path)
    with open(root + path + '/ZKDATA', 'wb') as f:
        f.write(data)
    for child in client.get_children(path):
        getTree(client, root, path + '/' + child, decompress)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('host', help='ZK host string')
    parser.add_argument('path', help='Filesystem output path for data dump')
    parser.add_argument('--cert', help='Path to TLS certificate')
    parser.add_argument('--key', help='Path to TLS key')
    parser.add_argument('--ca', help='Path to TLS CA cert')
    parser.add_argument('--decompress', action='store_true',
                        help='Decompress data')
    args = parser.parse_args()

    kwargs = {}
    if args.cert:
        kwargs['use_ssl'] = True
        kwargs['keyfile'] = args.key
        kwargs['certfile'] = args.cert
        kwargs['ca'] = args.ca
    client = kazoo.client.KazooClient(args.host, **kwargs)
    client.start()

    getTree(client, args.path, '/zuul', args.decompress)


if __name__ == '__main__':
    main()
