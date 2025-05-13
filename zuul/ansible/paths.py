# Copyright 2016 Red Hat, Inc.
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import importlib
import os
import sys

import ansible.plugins.action


def _full_path(path):
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def _fail_dict(path, prefix='Accessing files from'):
    return dict(
        failed=True,
        path=path,
        msg="{prefix} outside the working dir {curdir} is prohibited".format(
            prefix=prefix,
            curdir=os.path.abspath(os.path.curdir)))


def _import_ansible_action_plugin(name):
    # Ansible forces the import of our action plugins
    # (zuul.ansible.action.foo) as ansible.plugins.action.foo, which
    # is the import path of the ansible implementation.  Our
    # implementations need to subclass that, but if we try to import
    # it with that name, we will get our own module.  This bypasses
    # Python's module namespace to load the actual ansible modules.
    # We need to give it a name, however.  If we load it with its
    # actual name, we will end up overwriting our module in Python's
    # namespace, causing infinite recursion.  So we supply an
    # otherwise unused name for the module:
    # zuul.ansible.protected.action.foo.
    #
    # From https://discuss.python.org/t/how-do-i-migrate-from-imp/27885/3
    # for converting imp module loads to python3.12 compatible code.
    spec = importlib.machinery.PathFinder.find_spec(
        name, ansible.plugins.action.__path__)
    if not spec:
        raise Exception("Could not find %s at module path %s" %
                        (name, ansible.plugins.action.__path__))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules['zuul.ansible.protected.action.' + name] = mod
    return mod


def _sanitize_filename(name):
    return ''.join(c for c in name if c.isalnum())


# Ansible assigns a unique id to every task (Task._uuid).  However, if
# a role is included more than once, the task object is re-used.  In
# order to provide unique log ids for the Zuul command log streaming
# system, this global dictionary is used to map keys that are derived
# from tasks (task._uuid concatenated with the host name) to a counter
# which is incremented each time the task+host combination is
# encountered.  Ansible will not run more than one task on a host
# simultaneously, so this should be sufficiently unique to avoid
# collisions.
#
# We use a global dictionary defined here so that zuul_stream can
# write to it and zuul.ansible.command modules can read it.  Note that
# the command module operates after a fork and therefore it should be
# treated as read-only there.
ZUUL_LOG_ID_MAP = {}
