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

# This file contains provider-related schema chunks that can be reused
# by multiple drivers.  When adding new configuration options, if they
# can be used by more than one driver, add them here instead of in the
# driver.

import voluptuous as vs
from zuul.lib.voluputil import Required, Optional, Nullable

# Labels

# The label attributes which can appear either in the main body of the
# section stanza, or in a section/provider label, or in a standalone
# label.
common_label = vs.Schema({
    Optional('boot-timeout', default=300): int,
    Optional('executor-zone'): Nullable(str),
})

# The label attributes that can appear in a section/provider label or
# a standalone label (but not in the section body).
base_label = vs.Schema({
    Required('project_canonical_name'): str,
    Required('config_hash'): str,
    Required('name'): str,
    Optional('description'): Nullable(str),
    Optional('image'): Nullable(str),
    Optional('flavor'): Nullable(str),
    Optional('tags', default=dict): {str: str},
    Optional('min-ready', default=0): int,
    Optional('max-ready-age', default=0): int,
})

# Label attributes that are common to any kind of ssh-based driver.
ssh_label = vs.Schema({
    Optional('key-name'): Nullable(str),
    Optional('host-key-checking', default=True): bool,
})

# Images

# The image attributes which can appear either in the main body of the
# section stanza, or in a section/provider image, or in a standalone
# image.
common_image = vs.Schema({
    Optional('username'): Nullable(str),
    Optional('connection-type'): Nullable(str),
    Optional('connection-port'): Nullable(int),
    Optional('python-path'): Nullable(str),
    Optional('shell-type'): Nullable(str),
    Optional('import-timeout', default=300): int,
})

# Same as above, but only for cloud providers.
cloud_image = vs.Schema({
    Optional('userdata'): Nullable(str),
})

# The image attributes that, in addition to those above, can appear in
# a section/provider image or a standalone image (but not in the
# section body).
base_image = vs.Schema({
    Required('project_canonical_name'): str,
    Required('config_hash'): str,
    Required('name'): str,
    Optional('description'): Nullable(str),
    Required('branch'): str,
    Required('type'): vs.Any('cloud', 'zuul'),
})

# Flavors

# The flavor attributes that can appear in a section/provider flavor or
# a standalone flavor (but not in the section body).
base_flavor = vs.Schema({
    Required('project_canonical_name'): str,
    Required('config_hash'): str,
    Required('name'): str,
    Optional('description'): Nullable(str),
})

# Flavor attributes that are common to any kind of cloud driver.
cloud_flavor = vs.Schema({
    Optional('public-ipv4', default=False): bool,
    Optional('public-ipv6', default=False): bool,
})
