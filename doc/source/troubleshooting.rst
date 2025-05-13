Troubleshooting
---------------

In addition to inspecting :ref:`service debug logs <operation>`, some
advanced troubleshooting options are provided below.  These are
generally very low-level and are not normally required.

Thread Dumps and Profiling
==========================

If you send a SIGUSR2 to one of the daemon processes, it will dump a
stack trace for each running thread into its debug log. It is written
under the log bucket ``zuul.stack_dump``.  This is useful for tracking
down deadlock or otherwise slow threads::

  sudo kill -USR2 `cat /var/run/zuul/executor.pid`
  view /var/log/zuul/executor-debug.log +/zuul.stack_dump

When `yappi <https://code.google.com/p/yappi/>`_ (Yet Another Python
Profiler) is available, additional functions' and threads' stats are
emitted as well. The first SIGUSR2 will enable yappi, on the second
SIGUSR2 it dumps the information collected, resets all yappi state and
stops profiling. This is to minimize the impact of yappi on a running
system.
