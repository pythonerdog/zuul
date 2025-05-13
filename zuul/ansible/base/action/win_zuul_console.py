# Copyright 2025 Acme Gating, LLC
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

import importlib.resources

from ansible.plugins.action import ActionBase
from ansible.utils.vars import merge_hash

START_SCRIPT = """
(Add-Type -Path "{remote_cs_path}")
[WinZuulConsole]::Main($args)
"""


class ActionModule(ActionBase):
    TRANSFERS_FILES = True

    def run(self, tmp=None, task_vars=None):
        results = super(ActionModule, self).run(tmp, task_vars)

        # Copy our csharp server code over
        local_path = str(importlib.resources.files('zuul').joinpath(
            'ansible/win_zuul_console.cs'))
        remote_cs_path = self._connection._shell.join_path(
            self._connection._shell.tmpdir,
            'win_zuul_console.cs')
        self._transfer_file(local_path, remote_cs_path)

        # Copy the bootstrap script
        remote_ps_path = self._connection._shell.join_path(
            self._connection._shell.tmpdir,
            'win_zuul_console_start.ps1')
        self._transfer_data(
            remote_ps_path,
            START_SCRIPT.format(remote_cs_path=remote_cs_path))
        self._task.args['_zuul_console_exec_path'] = remote_ps_path

        # Run the module
        results = merge_hash(results, self._execute_module(
            module_name='win_zuul_console', task_vars=task_vars))
        return results
