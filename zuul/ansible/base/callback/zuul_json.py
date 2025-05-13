# (c) 2016, Matt Martz <matt@sivel.net>
# (c) 2017, Red Hat, Inc.
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

# Copy of github.com/ansible/ansible/lib/ansible/plugins/callback/json.py
# We need to run as a secondary callback not a stdout and we need to control
# the output file location via a zuul environment variable similar to how we
# do in zuul_stream.
# Subclassing wreaks havoc on the module loader and namepsaces
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import copy
import datetime
import json
import os

from ansible.plugins.loader import PluginLoader
from ansible.plugins.callback import CallbackBase
try:
    # It's here in 2.3
    from ansible.vars import strip_internal_keys
except ImportError:
    try:
        # It's here in 2.4
        from ansible.vars.manager import strip_internal_keys
    except ImportError:
        # It's here in 2.5
        from ansible.vars.clean import strip_internal_keys

from zuul.ansible import logconfig


def current_time():
    return '%sZ' % datetime.datetime.utcnow().isoformat()


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    # aggregate means we can be loaded and not be the stdout plugin
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'zuul_json'

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display)
        self.results = []
        self.playbook = {}
        logging_config = logconfig.load_job_config(
            os.environ['ZUUL_JOB_LOG_CONFIG'])

        self.output_path = os.path.splitext(
            logging_config.job_output_file)[0] + '.json'

        self._playbook_name = None

    def _new_playbook(self, play):
        extra_vars = play._variable_manager._extra_vars
        self._playbook_name = None

        # TODO(mordred) For now, protect specific variable lookups to make it
        # not absurdly strange to run local tests with the callback plugin
        # enabled. Remove once we have a "run playbook like zuul runs playbook"
        # tool.
        phase = extra_vars.get('zuul_execution_phase')
        index = extra_vars.get('zuul_execution_phase_index')
        playbook = extra_vars.get('zuul_execution_canonical_name_and_path')
        trusted = extra_vars.get('zuul_execution_trusted')
        trusted = True if trusted == "True" else False
        branch = extra_vars.get('zuul_execution_branch')

        self.playbook['playbook'] = playbook
        self.playbook['phase'] = phase
        self.playbook['index'] = index
        self.playbook['trusted'] = trusted
        self.playbook['branch'] = branch

    def _new_play(self, play):
        return {
            'play': {
                'name': play.name,
                'id': str(play._uuid),
                'duration': {
                    'start': current_time()
                }
            },
            'tasks': []
        }

    def _new_task(self, task):
        data = {
            'task': {
                'name': task.name,
                'id': str(task._uuid),
                'duration': {
                    'start': current_time()
                }
            },
            'hosts': {}
        }
        if task._role:
            data['role'] = {
                'name': task._role.get_name(),
                'id': str(task._role._uuid),
                'path': task._role._role_path,
            }
        return data

    def v2_playbook_on_start(self, playbook):
        self._playbook_name = os.path.splitext(playbook._file_name)[0]

    def v2_playbook_on_play_start(self, play):
        if self._playbook_name:
            self._new_playbook(play)

        self.results.append(self._new_play(play))

    def v2_playbook_on_task_start(self, task, is_conditional):
        self.results[-1]['tasks'].append(self._new_task(task))

    def v2_playbook_on_handler_task_start(self, task):
        self.v2_playbook_on_task_start(task, False)

    def v2_runner_on_ok(self, result, **kwargs):
        host = result._host
        action = result._task.action
        # strip_internal_keys makes a deep copy of dict items, but
        # not lists, so we need to create our own complete deep
        # copy first so we don't modify the original.
        myresult = copy.deepcopy(result._result)
        clean_result = strip_internal_keys(myresult)
        self.results[-1]['tasks'][-1]['hosts'][host.name] = clean_result
        end_time = current_time()
        self.results[-1]['tasks'][-1]['task']['duration']['end'] = end_time
        self.results[-1]['play']['duration']['end'] = end_time
        self.results[-1]['tasks'][-1]['hosts'][host.name]['action'] = action

    def v2_runner_on_failed(self, result, **kwargs):
        self.v2_runner_on_ok(result, **kwargs)
        self.results[-1]['tasks'][-1]['hosts'][result._host.name].\
            setdefault('failed', True)

    def v2_runner_on_skipped(self, result, **kwargs):
        self.v2_runner_on_ok(result, **kwargs)
        self.results[-1]['tasks'][-1]['hosts'][result._host.name].\
            setdefault('skipped', True)

    def v2_playbook_on_stats(self, stats):
        """Display info about playbook statistics"""
        hosts = sorted(stats.processed.keys())

        summary = {}
        for h in hosts:
            s = stats.summarize(h)
            summary[h] = s

        self.playbook['plays'] = self.results
        self.playbook['stats'] = summary

        first_time = not os.path.exists(self.output_path)

        if first_time:
            with open(self.output_path, 'w') as outfile:
                outfile.write('[\n\n]\n')

        with open(self.output_path, 'r+') as outfile:
            self._append_playbook(outfile, first_time)

    def _append_playbook(self, outfile, first_time):
        file_len = outfile.seek(0, os.SEEK_END)
        # Remove three bytes to eat the trailing newline written by the
        # json.dump. This puts the ',' on the end of lines.
        outfile.seek(file_len - 3)
        if not first_time:
            outfile.write(',\n')
        json.dump(self.playbook, outfile,
                  indent=4, sort_keys=True, separators=(',', ': '))
        outfile.write('\n]\n')

    v2_runner_on_unreachable = v2_runner_on_ok


# Using 'ansible.builtin.command' instead of 'command' bypasses our
# custom plugins, so rewrite any uses of ansible.builtin.X to just X.
# This workaround is temporary until we remove our custom plugins.

# This happens here because Ansible will load the zuul_json plugin for
# any invocation where we care about restricting access, and this is
# the earliest in the Ansible startup procedure we can access.

# Monkepatch some PluginLoader methods to rewrite the modules it is
# loading.
orig_get = PluginLoader.get
orig_find_plugin = PluginLoader.find_plugin


def mp_get(self, name, *args, **kwargs):
    if (name.startswith('ansible.builtin.') or
        name.startswith('ansible.legacy.')):
        name = name.rsplit('.', 1)[-1]
    ret = orig_get(self, name, *args, **kwargs)
    return ret


def mp_find_plugin(self, name, *args, **kwargs):
    if (name.startswith('ansible.builtin.') or
        name.startswith('ansible.legacy.')):
        name = name.rsplit('.', 1)[-1]
    ret = orig_find_plugin(self, name, *args, **kwargs)
    return ret


PluginLoader.get = mp_get
PluginLoader.find_plugin = mp_find_plugin
