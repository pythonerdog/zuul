#!powershell

# Copyright (C) 2025 Acme Gating, LLC
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

#AnsibleRequires -CSharpUtil Ansible.Basic
#AnsibleRequires -PowerShell Ansible.ModuleUtils.AddType

# We put the logs in this location to approximate the global /tmp on
# unix.  We can't use the individual user's home directory because it
# may not be writeable if "become" is used.

$LOG_STREAM_FILE = "C:/ProgramData/Zuul/Zuul/console-{0}.log"
$LOG_STREAM_PORT = 19886

$spec = @{
    options = @{
        _zuul_console_exec_path = @{ type = "str" }
        path = @{ type = "str"; default = $LOG_STREAM_FILE }
        port = @{ type = "int"; default = $LOG_STREAM_PORT }
        state = @{ type = "str"; choices = "absent", "present" }
    }
}
$module = [Ansible.Basic.AnsibleModule]::Create($args, $spec)

function Base64-Encode {
    param ($Str)
    [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Str))
}

# The log path can have {} characters in it for python string
# interpolation; avoid shell issues by base64 encoding it.
$LogPath = Base64-Encode $module.Params.path

if ($module.Params.state -eq "absent") {
    try {
        # Identify the process by port and kill it.
        Get-Process -Id (Get-NetTCPConnection -LocalPort $module.Params.port).OwningProcess | Stop-Process
        $module.Result.changed = $true
    } catch {}
} else {
    try {
        # If we can find a process listening on this port, assume it
        # is a pre-existing daemon and skip the rest.
        Get-Process -Id (Get-NetTCPConnection -LocalPort $module.Params.port).OwningProcess | Out-Null
    } catch {
        $ConsoleCommand = "powershell -executionpolicy bypass -File $($module.Params._zuul_console_exec_path) $($LogPath) $($module.Params.port)"
        # This method of starting a new process completely detaches it
        # from the ssh process.
        Invoke-WmiMethod -Path 'Win32_Process' -Name Create -ArgumentList $ConsoleCommand | Out-Null
        $module.Result.changed = $true
        # Return the resulting command for debugging.
        $module.Result.cmd = $ConsoleCommand
    }
}

$module.ExitJson()
