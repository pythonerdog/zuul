:title: Git Driver

Git
===

This driver can be used to load Zuul configuration from public Git repositories,
for instance from ``opendev.org/zuul/zuul-jobs`` that is suitable for use by
any Zuul system. It can also be used to trigger jobs from ``ref-updated`` events
in a pipeline.

Connection Configuration
------------------------

The supported options in ``zuul.conf`` connections are:

.. attr:: <git connection>

   .. attr:: driver
      :required:

      .. value:: git

         The connection must set ``driver=git`` for Git connections.

   .. attr:: baseurl

      Path to the base Git URL. Git repos name will be appended to it.

   .. attr:: poll_delay
      :default: 7200

      The delay in seconds of the Git repositories polling loop.

Trigger Configuration
---------------------

.. attr:: pipeline.trigger.<git source>

   The dictionary passed to the Git pipeline ``trigger`` attribute
   supports the following attributes:

   .. attr:: event
      :required:

      Only ``ref-updated`` is supported.

   .. attr:: ref

      On ref-updated events, a ref such as ``refs/heads/master`` or
      ``^refs/tags/.*$``. This field is treated as a regular expression,
      and multiple refs may be listed.

   .. attr:: ignore-deletes
      :default: true

      When a ref is deleted, a ref-updated event is emitted with a
      newrev of all zeros specified. The ``ignore-deletes`` field is a
      boolean value that describes whether or not these newrevs
      trigger ref-updated events.

   .. attr:: debug
      :default: false

      When set to `true`, this will cause debug messages to be
      included when the queue item is reported.  These debug messages
      may be used to help diagnose why certain jobs did or did not
      run, and in many cases, why the item was not ultimately enqueued
      into the pipeline.

      Setting this value also effectively sets
      :attr:`project.<pipeline>.debug` for affected queue items.

      This only applies to items that arrive at a pipeline via this
      particular trigger.  Since the output is very verbose and
      typically not needed or desired, this allows for a configuration
      where typical pipeline triggers omit the debug output, but
      triggers that match certain specific criteria may be used to
      request debug information.
