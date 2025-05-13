:title: Timer Driver

Timer
=====

The timer driver supports triggers only.  It is used for configuring
pipelines so that jobs run at scheduled times.  No connection
configuration is required.

Trigger Configuration
---------------------

Timers don't require a special connection or driver. Instead they can
simply be used by listing ``timer`` as the trigger.

This trigger will run based on a cron-style time specification.  It
will enqueue an event into its pipeline for every project and branch
defined in the configuration.  Any job associated with the pipeline
will run in response to that event.

Zuul implements the timer using `apscheduler`_, Please check the
`apscheduler documentation`_ for more information about the syntax.

.. attr:: pipeline.trigger.timer

   The timer trigger supports the following attributes:

   .. attr:: time
      :required:

      The time specification in cron syntax.  Only the 5 part syntax
      is supported, not the symbolic names.  Example: ``0 0 * * *``
      runs at midnight.

      An optional 6th part specifies seconds.  The optional 7th part
      specifies a jitter in seconds. This delays the trigger randomly,
      limited by the specified value.  Example ``0 0 * * * * 60`` runs
      at midnight or randomly up to 60 seconds later.  The jitter is
      applied individually to each project-branch combination.  While
      the jitter is initialized to a random value, the same value will
      often be used for a given project-branch combination (in other
      words, it is not guaranteed to vary from one run of the timer
      trigger to the next).

   .. warning::
       Be aware the day-of-week value differs from from cron.
       The first weekday is Monday (0), and the last is Sunday (6).


.. _apscheduler: https://apscheduler.readthedocs.io/
.. _apscheduler documentation: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html#module-apscheduler.triggers.cron
