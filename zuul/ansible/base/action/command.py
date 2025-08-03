# Copyright 2018 BMW Car IT GmbH
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

import os

from zuul.ansible import paths, stream_setup

command = paths._import_ansible_action_plugin("command")


class ActionModule(command.ActionModule):

    def run(self, tmp=None, task_vars=None):
        # we need the zuul_log_id on shell and command tasks
        if self._task.action in (
                'command', 'shell',
                'ansible.builtin.command', 'ansible.builtin.shell'):
            stream_setup.stream_setup_run(self, task_vars)
            # TODO: remove after deprecation period
            self._task.args["zuul_ansible_split_streams"] = (
                os.environ["ZUUL_ANSIBLE_SPLIT_STREAMS"] == "True")
        return super(ActionModule, self).run(tmp, task_vars)
