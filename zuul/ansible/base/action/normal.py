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

from zuul.ansible import paths, stream_setup

normal = paths._import_ansible_action_plugin("normal")

# Map the various names to our custom module
module_map = {
    'win_shell': 'zuul_win_shell',
    'win_command': 'zuul_win_command',
    'ansible.legacy.win_shell': 'zuul_win_shell',
    'ansible.legacy.win_command': 'zuul_win_command',
    'ansible.windows.win_shell': 'zuul_win_shell',
    'ansible.windows.win_command': 'zuul_win_command',
}

# Never let users specify these directly
module_blocklist = [
    'zuul_win_shell',
    'zuul_win_command',
]


class ActionModule(normal.ActionModule):

    def run(self, tmp=None, task_vars=None):
        module_name = self._task.action
        if module_name in module_blocklist:
            raise Exception(f"Module {module_name} may not be used directly")
        if module_name in module_map:
            if not stream_setup.zuul_console_disabled(self):
                stream_setup.stream_setup_run(self, task_vars)
        return super(ActionModule, self).run(tmp, task_vars)

    def _execute_module(self, module_name=None, *args, **kw):
        if module_name is None:
            module_name = self._task.action
        # If the user has not disabled the zuul console, then switch
        # to our custom module.
        if module_name in module_map:
            if not stream_setup.zuul_console_disabled(self):
                module_name = module_map.get(module_name)
        return super(ActionModule, self)._execute_module(
            module_name=module_name, *args, **kw)
