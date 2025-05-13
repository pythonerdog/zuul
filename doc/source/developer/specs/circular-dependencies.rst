Circular Dependencies
=====================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

The current assumption in Zuul is that dependencies form a Directed Acyclic
Graph (DAG). This is also what should be considered best practice. However,
there can be cases where we have circular dependencies and with that no longer
a DAG.

The current implementation to detect and prevent cycles will visit all vertices
of the dependency graph and bail out if an item is encountered twice. This
method is no longer feasible when we want to allow circular dependencies
between changes.

Instead, we need to find the `strongly connected components`_ (changes) of a
given dependency graph. The individual changes in those subgraphs need to know
about each other.

Circular dependency handling needs to be configurable on a per tenant and
project basis.

.. _strongly connected components: https://en.wikipedia.org/wiki/Strongly_connected_component


Proposed change
---------------

By default, Zuul will retain the current behavior of preventing dependency
cycles. The circular dependency handling must be explicitly enabled in the
tenant configuration.

.. code-block:: yaml

   allow-circular-dependencies: true

In addition, the tenant default may be overridden on a per-project basis:

.. code-block:: yaml

   [...]

   untrusted-projects:
     - org/project:
         allow-circular-dependencies: true

   [...]

Changes with cross-repo circular dependencies are required to share the same
change queue. We would still enqueue one queue item per change but hold back
reporting of the cycle until all items have finished. All the items in a cycle
would reference a shared bundle item.

A different approach would be to allow the enqueuing of changes across change
queues. This, however, would be a very substantial change with a lot of edge
cases and will therefore not be considered.

Dependencies are currently expressed with a ``Depends-On`` in the footer of a
commit message or pull-request body. This information is already used for
detecting cycles in the dependency graph.

A cycle is created by having a mutual ``Depends-On`` for the changes that
depend on each other.

We might need a way to prevent changes from being enqueued before all changes
that are part of a cycle are prepared. For this, we could introduce a special
value (e.g. ``null``) for the ``Depends-On`` to indicate that the cycle is not
complete yet. This is since we don't know the change URLs ahead of time.

From a user's perspective this would look as follows:

1. Set ``Depends-On: null`` on the first change that is uploaded.

2. Reference the change URL of the previous change in the ``Depends-On``.
   Repeat this for all changes that are part of the cycle.

3. Set the ``Depends-On`` (e.g. pointing to the last uploaded change) to
   complete the cycle.


Implementation
--------------

1. Detect strongly connected changes using e.g. `Tarjan's algorithm`_, when
   enqueuing a change and its dependencies.

   .. _Tarjan's algorithm: https://en.wikipedia.org/wiki/Tarjan%27s_strongly_connected_components_algorithm

2. Introduce a new class (e.g. ``Bundle``) that will hold a list of strongly
   connected components (changes) in the order in which they need to be merged.

   In case a circular dependency is detected all instances of ``QueueItem``
   that are strongly connected will hold a reference to the same ``Bundle``
   instance. In case there is no cycle, this reference will be ``None``.

3. The merger call for a queue item that has an associated bundle item will
   always include all changes in the bundle.

   However each ``QueueItem`` will only have and execute the job graph for a
   particular change.

4. Hold back reporting of a ``QueueItem`` in case it has an associated
   ``Bundle`` until all related ``QueueItem`` have finished.

   Report the individual job results for a ``QueueItem`` as usual. The last
   reported item will also report a summary of the overall bundle result to
   each related change.


Challenges
----------

Ordering of changes
   Usually, the order of change in a strongly connected component doesn't
   matter.  However for sources that have the concept of a parent-child
   relationship (e.g. Gerrit changes) we need to keep the order and report a
   parent change before the child.

   This information is available in ``Change.git_needs_changes``.

   To not change the reporting logic too much (currently only the first item in
   the queue can report), the changes need to be enqueued in the correct order.
   Due to the recursive implementation of ``PipelineManager.addChange()``, this
   could mean that we need to allow enqueuing changes ahead of others.

Windows size in the dependent pipeline manager
   Since we need to postpone reporting until all items of a bundle have
   finished those items will be kept in the queue. This will prevent new
   changes from entering the active window. It might even lead to a deadlock in
   case the number of changes within the strongly connected component is larger
   than the current window size.

   One solution would be to increase the size of the window by one every time
   we hold an item that has finished but is still waiting for other items in a
   bundle.

Reporting of bundle items
   The current logic will try to report an item as soon as all jobs have
   finished. In case this item is part of a bundle we have to hold back the
   reporting until all items that are part of the bundle have succeeded or we
   know that the whole bundle will fail.

   In case the first item of a bundle did already succeed but a subsequent item
   fails we must not reset the builds of queue items that are part of this
   bundle, as it would currently happen when the jobs are canceled. Instead, we
   need to keep the existing results for all items in a bundle.

   When reporting a queue item that is part of a bundle, we need to make sure
   to also report information related to the bundle as a whole. Otherwise, the
   user might not be able to identify why a failure is reported even though all
   jobs succeeded.

   The reporting of the bundle summary needs to be done in the last item of a
   bundle because only then we know if the complete bundle was submitted
   successfully or not.

Recovering from errors
    Allowing circular dependencies introduces the risk to end up with a broken
    state when something goes wrong during the merge of the bundled changes.

    Currently, there is no way to more or less atomically submit multiple
    changes at once. Gerrit offers an option to submit a complete topic. This,
    however, also doesn't offer any guarantees for being atomic across
    repositories [#atomic]_. When considering changes with a circular
    dependency, spanning multiple sources (e.g. Gerrit + Github) this seems no
    longer possible at all.

    Given those constraints, Zuul can only work on a best effort basis by
    trying hard to make sure to not start merging the chain of dependent
    changes unless it is safe to assume that the merges will succeed.

    Even in those cases, there is a chance that e.g. due to a network issue,
    Zuul fails to submit all changes of a bundle.

    In those cases, the best way would be to automatically recover from the
    situation. However, this might mean pushing a revert or force-pushing to
    the target branch and reopening changes, which will introduce a new set of
    problems on its own. In addition, the recovery might be affected by e.g.
    network issues as well and can potentially fail.

    All things considered, it's probably best to perform a gate reset as with a
    normal failing item and require human intervention to bring the
    repositories back into a consistent state. Zuul can assist in that by
    logging detailed information about the performed steps and encountered
    errors to the affected change pages.

Execution overhead
    Without any de-duplication logic, every change that is part of a bundle
    will have its jobs executed. For circular dependent changes with the same
    jobs configured this could mean executing the same jobs twice.

.. rubric:: Footnotes

.. [#atomic] https://groups.google.com/forum/#!topic/repo-discuss/OuCXboAfEZQ
