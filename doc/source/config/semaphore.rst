.. _semaphore:

Semaphore
=========

Semaphores can be used to restrict the number of certain jobs which
are running at the same time.  This may be useful for jobs which
access shared or limited resources.  A semaphore has a value which
represents the maximum number of jobs which use that semaphore at the
same time.

Semaphores, like most configuration items, are unique within a tenant,
though a semaphore may be defined on multiple branches of the same
project as long as the value is the same.  This is to aid in branch
maintenance, so that creating a new branch based on an existing branch
will not immediately produce a configuration error.

Zuul also supports global semaphores (see :ref:`global_semaphore`)
which may only be created by the Zuul administrator, but can be used
to coordinate resources across multiple tenants.

Semaphores are never subject to dynamic reconfiguration.  If the value
of a semaphore is changed, it will take effect only when the change
where it is updated is merged.  However, Zuul will attempt to validate
the configuration of semaphores in proposed updates, even if they
aren't used.

An example usage of semaphores follows:

.. code-block:: yaml

   - semaphore:
       name: semaphore-foo
       max: 5
   - semaphore:
       name: semaphore-bar
       max: 3

.. attr:: semaphore

   The following attributes are available:

   .. attr:: name
      :required:

      The name of the semaphore, referenced by jobs.

   .. attr:: max
      :default: 1

      The maximum number of running jobs which can use this semaphore.

