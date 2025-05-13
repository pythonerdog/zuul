# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2011 OpenStack LLC
#    Copyright 2012 Hewlett-Packard Development Company, L.P.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json

from importlib import metadata as importlib_metadata

zuul_distribution = importlib_metadata.distribution('zuul')
release_string = zuul_distribution.version

is_release = None
git_version = None
try:
    _metadata = json.loads(zuul_distribution.read_text('pbr.json'))
    if _metadata:
        is_release = _metadata['is_release']
        git_version = _metadata['git_version']
except Exception:
    pass


def get_version_string():
    if is_release:
        return release_string
    return "{} {}".format(release_string, git_version)
