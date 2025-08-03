:title: Zuul Driver

Zuul
====

The Zuul driver supports triggers only.  It is used for triggering
pipelines based on internal Zuul events.

Trigger Configuration
---------------------

Zuul events don't require a special connection or driver. Instead they
can simply be used by listing ``zuul`` as the trigger.

.. attr:: pipeline.trigger.zuul

   The Zuul trigger supports the following attributes:

   .. attr:: event
      :required:

      The event name.  Currently supported events:

      .. value:: project-change-merged

         When Zuul merges a change to a project, it generates this
         event for every open change in the project.  If there are a
         large number of open changes, this may produce a large number
         of events and result in poor performance.

         .. warning::

            Triggering on this event can cause poor performance when
            using the GitHub driver with a large number of
            installations.

      .. value:: parent-change-enqueued

         When Zuul enqueues a change into any pipeline, it generates
         this event for every child of that change.  If there are a
         large number of open changes, this may produce a large number
         of events and result in poor performance.

         .. note:: The dependent pipeline manager automatically
                   enqueues forward, reverse, and if configured,
                   circular dependencies of any change that is
                   enqueued.  It is not necessary to add this trigger
                   to :term:`gate` pipelines.

   .. attr:: pipeline

      Only available for ``parent-change-enqueued`` events.  This is
      the name of the pipeline in which the parent change was
      enqueued.

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
