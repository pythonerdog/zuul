#!/bin/bash -e

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

# Rebuild old versions of documentation

ZUUL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

function init () {
    rm -fr /tmp/rebuild
    mkdir /tmp/rebuild
    cd /tmp/rebuild
    git clone https://opendev.org/zuul/zuul
    cd /tmp/rebuild/zuul
    tox -e docs --notest
}

function build {
    mkdir -p /tmp/rebuild/output
    cd /tmp/rebuild/zuul
    git reset --hard origin/master
    git checkout $1
    mkdir -p doc/source/_static
    mkdir -p doc/source/_templates
    cp $ZUUL_DIR/doc/source/_static/* doc/source/_static
    cp $ZUUL_DIR/doc/source/_templates/* doc/source/_templates
    cp $ZUUL_DIR/doc/source/conf.py doc/source
    cp $ZUUL_DIR/doc/requirements.txt doc
    cp $ZUUL_DIR/tox.ini .
    . .tox/docs/bin/activate
    sphinx-build -E -d doc/build/doctrees -b html doc/source/ doc/build/html
    mv doc/build/html /tmp/rebuild/output/$1
    rm -fr doc/build/doctrees
}

# TODO: iterate over tags
init
build 3.3.0
build 3.3.1
build 3.4.0
build 3.5.0
build 3.6.0
build 3.6.1
build 3.7.0
build 3.7.1
build 3.8.0
build 3.8.1
build 3.9.0
build 4.0.0
build 4.1.0
build 4.2.0
build 4.3.0
build 4.4.0
build 4.5.0
build 4.5.1
build 4.6.0
build 4.7.0
build 4.8.0
build 4.8.1
build 4.9.0
build 4.10.0
build 4.10.1
build 4.10.2
build 4.10.3
build 4.10.4
build 4.11.0
