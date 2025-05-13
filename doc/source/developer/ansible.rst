Ansible Integration
===================

Zuul contains Ansible modules and plugins to control the execution of Ansible
Job content.

Zuul provides realtime build log streaming to end users so that users
can watch long-running jobs in progress.

Streaming job output
--------------------

All jobs run with the :py:mod:`zuul.ansible.base.callback.zuul_stream` callback
plugin enabled, which writes the build log to a file so that the
:py:class:`zuul.lib.log_streamer.LogStreamer` can provide the data on demand
over the finger protocol. Finally, :py:class:`zuul.web.LogStreamHandler`
exposes that log stream over a websocket connection as part of
:py:class:`zuul.web.ZuulWeb`.

.. autoclass:: zuul.ansible.base.callback.zuul_stream.CallbackModule
.. autoclass:: zuul.lib.log_streamer.LogStreamer
.. autoclass:: zuul.web.LogStreamHandler
.. autoclass:: zuul.web.ZuulWeb

In addition to real-time streaming, Zuul also installs another callback module,
:py:mod:`zuul.ansible.base.callback.zuul_json.CallbackModule` that collects all
of the information about a given run into a json file which is written to the
work dir so that it can be published along with build logs.

.. autoclass:: zuul.ansible.base.callback.zuul_json.CallbackModule

Since the streaming log is by necessity a single text stream, choices
have to be made for readability about what data is shown and what is
not shown. The json log file is intended to allow for a richer more
interactive set of data to be displayed to the user.

.. _zuul_console_streaming:

Capturing live command output
-----------------------------

As jobs may execute long-running shell scripts or other commands,
additional effort is expended to stream ``stdout`` and ``stderr`` of
shell tasks as they happen rather than waiting for the command to
finish.

The global job configuration should run the ``zuul_console`` task as a
very early prerequisite step.

.. automodule:: zuul.ansible.base.library.zuul_console

This will start a daemon that listens on TCP port 19885 on the testing
node.  This daemon can be queried to stream back the output of shell
tasks as described below.

Zuul contains a modified version of Ansible's
:ansible:module:`command` module that overrides the default
implementation.

.. automodule:: zuul.ansible.base.library.command

This library will capture the output of the running
command and write it to a temporary file on the host the command is
running on.  These files are named in the format
``/tmp/console-<uuid>-<task_id>-<host>.log``

The ``zuul_stream`` callback mentioned above will send a request to
the remote ``zuul_console`` daemon, providing the uuid and task id of
the task it is currently processing.  The ``zuul_console`` daemon will
then read the logfile from disk and stream the data back as it
appears, which ``zuul_stream`` will then present as described above.

The ``zuul_stream`` callback will indicate to the ``zuul_console``
daemon when it has finished reading the task, which prompts the remote
side to remove the temporary streaming output files.  In some cases,
aborting the Ansible process may not give the ``zuul_stream`` callback
the chance to send this notice, leaking the temporary files.  If nodes
are ephemeral this makes little difference, but these files may be
visible on static nodes.
