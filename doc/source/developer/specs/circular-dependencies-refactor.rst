Refactor Circular Dependencies
==============================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

Zuul currently supportes circular dependencies and recent work has
extended that support to include optimizations such as deduplicating
builds (one of the challenges noted in the original spec for circular
dependencies).  The original implementation of circular dependencies
is characterized by an attempt to minimize changes to the existing
dependency system and pipeline management algorithms in Zuul.  It did
this principally by retaining the 1:1 relationship between queue items
and changes (so that a pipeline queue retained the characteristic that
it is a strict linear ordering of individual changes) and adding the
concept of a "bundle" representing the circular dependency as a
relationship superimposed on the pipeline queue.

As Zuul has grown more complex, this is proving more difficult to
manage, resulting in more code errors and maintenance burden.  In
particular, increasingly large amounts of the pipeline management code
is bifurcated with ``if item.bundle`` conditionals, which can result
in exponentially increasing complexity as we design test scenarios to
try to cover all the cases.

Originally, the "Nearest Non-Failing Item" (NNFI) algorithm in Zuul
was quite simple: if the change ahead of the current change is not the
nearest change ahead which is not failing, move the current change
behind the NNFI and restart jobs.  This required only two pieces of
information, the item ahead and the NNFI, both of which can be
determined by a strictly linear walk down the queue.  Bundles,
however, are starting to require more looks ahead and behind at other
items in the queue, making the algorithm much harder to understand and
validate.

This spec proposes a refactoring of the circular dependency code with
the intention that we return the main pipeline management algorithms
to something closer to their original simplicity.  We should be able
to minimize looking behind items in the queue while continuing to
support circular dependencies and related features like deduplication.

Proposed Change
---------------

We should update the QueueItem class to support multiple changes at
once, and remove the concept of Bundles altogether.  In this way, we
will no longer link cycles across queue items, but rather have a
single queue item that represents an entire cycle.

In the case that circular dependencies are not required, the queue
item will simply have a list of included changes of length 1.  Any
code that processes queue items will in all cases iterate over all
changes in that queue item when dealing with it, whether that list is
1 or >1.

The process of reporting will be similar, and likely simpler.
Currently when a change in a bundle is reported, we report the entire
bundle at once (even queue items that we haven't actually processed
yet).  The actual sequence of remote API calls will be the same, but
conceptually, we will be reporting a single item in Zuul.

Currently, build deduplication causes us to link builds across
different queue items (and even different queues in independent
pipelines).  Since pipelines can treat all changes in a cycle as a
single queue item, that will no longer be necessary; the process of
deduplicating builds will only need to consider builds within a single
queue item.  And it may make things more clear to users when they see
cyclical changes enqueued together instead of a series of
invisibly-linked changes in a dependent pipeline, or as a repeated
series of the same changes in an independent pipeline.

Challenges
----------

Multiple Jobs with Same Name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A major issue to consider is how to deal with multiple jobs with the
same name.  Consider two projects where each project runs a `linters`
job individually and they also run an `integration` job that tests the
two projects together.  In Zuul, we eschew the idea of having a
distinct job name for every project in favor of fewer jobs that
understand they may be run in different contexts.  So instead of
having `project1-linters` and `project2-linters`, we just have
`linters` that is run with context variables indicating the name of
the project that it should be testing.

Since a buildset belongs to a single queue item and a queue item is
for a single change, every build in Zuul, be it a single-repo job like
`linters` or multi-repo like `integration` knows the change context in
which it is being run.  If we are to have multiple changes for a queue
item, we still need to be able to run the `linters` job for both
`project1` and `project2`, so we need to resolve that ambiguity.

To do so, we will retain the concept of having a single buildset for a
queue item, but instead of assuming that a job name is a unique
identifier in a buildset, we will now require the tuple of (job,
change) to uniquely identify the build.

This will allow us to deduplicate builds at the buildset level in some
cases, and not deduplicate them in others.  A potential two-change
cycle may produce the following buildset:

+--------------+--------+
| Job Name     | Change |
+==============+========+
| linters      | 1      |
+--------------+--------+
| linters      | 2      |
+--------------+--------+
| integration  | 1      |
+--------------+--------+

Rather than running `integration` a second time, it will be
deduplicated (just as it is today) and run in the context of one of
the changes in the cycle.

This will require changes not only to internal data storage in the
model and ZK, but also the SQL database.

SQL Changes
~~~~~~~~~~~

The SQL database will be updated to the following schema (only
relevant tables included; build artifacts, events, etc will remain
unchanged).

.. graphviz::
   :align: center

   digraph G {
       graph [layout=sfdp, overlap_scaling=4]
       node [shape=none, margin=0]
       edge [arrowsize=2]
       zuul_buildset [label=<
           <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
               <tr><td port="_table" bgcolor="black"><font color="white">zuul_buildset</font></td></tr>
               <tr><td port="id" align="left">id</td></tr>
               <tr><td align="left">uuid</td></tr>
               <tr><td align="left">tenant</td></tr>
               <tr><td align="left">pipeline</td></tr>
               <tr><td align="left">result</td></tr>
               <tr><td align="left">message</td></tr>
               <tr><td align="left">event_id</td></tr>
               <tr><td align="left">event_timestamp</td></tr>
               <tr><td align="left">first_build_start_time</td></tr>
               <tr><td align="left">last_build_end_time</td></tr>
               <tr><td align="left">updated</td></tr>
           </table>
       >]

       zuul_ref [label=<
           <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
               <tr><td port="_table" bgcolor="black"><font color="white">zuul_ref</font></td></tr>
               <tr><td port="id" align="left">id</td></tr>
               <tr><td align="left">project</td></tr>
               <tr><td align="left">change</td></tr>
               <tr><td align="left">patchset</td></tr>
               <tr><td align="left">ref</td></tr>
               <tr><td align="left">ref_url</td></tr>
               <tr><td align="left">oldrev</td></tr>
               <tr><td align="left">newrev</td></tr>
               <tr><td align="left">branch</td></tr>
           </table>
       >]

       zuul_buildset_ref [label=<
           <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
               <tr><td port="_table" bgcolor="black"><font color="white">zuul_buildset_ref</font></td></tr>
               <tr><td port="buildset_id" align="left">buildset_id</td></tr>
               <tr><td port="ref_id" align="left">ref_id</td></tr>
           </table>
       >]

       zuul_build [label=<
           <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
               <tr><td port="_table" bgcolor="black"><font color="white">zuul_build</font></td></tr>
               <tr><td port="id" align="left">id</td></tr>
               <tr><td port="buildset_id" align="left">buildset_id</td></tr>
               <tr><td port="ref_id" align="left">ref_id</td></tr>
               <tr><td align="left">uuid</td></tr>
               <tr><td align="left">job_name</td></tr>
               <tr><td align="left">result</td></tr>
               <tr><td align="left">start_time</td></tr>
               <tr><td align="left">end_time</td></tr>
               <tr><td align="left">voting</td></tr>
               <tr><td align="left">log_url</td></tr>
               <tr><td align="left">error_detail</td></tr>
               <tr><td align="left">final</td></tr>
               <tr><td align="left">held</td></tr>
               <tr><td align="left">nodeset</td></tr>
           </table>
       >]

       zuul_build:buildset_id -> zuul_buildset:id
       zuul_buildset_ref:buildset_id -> zuul_buildset:id
       zuul_buildset_ref:ref_id-> zuul_ref:id
       zuul_build:ref_id -> zuul_ref:id
   }

Information about changes (refs) is moved to a new ``zuul_refs`` table
in order to reduce duplication.  Buildsets are linked to refs
many-to-many (in order to represent that a buildset is for the set of
changes that were attached to the queue item).  Builds are also linked
to a single ref in order to indicate the change context that was used
for the build.  The combinations of (job_name, ref_id) in a buildset
are unique.

Provides/Requires
~~~~~~~~~~~~~~~~~

Currently the provides/requires system only considers jobs in other
queue items.  That is, if a job for item A provides something that a
job for item B requires, even if A and B are in a dependency cycle,
they will be linked since they are in different queue items (though
this may only work for dependency cycle items ahead of an item in the
queue, not behind, thus illustrating another example of the
complexities motivating this change).

With this change, we should attempt to maintain the status quo by
searching for builds which can provide requirements only in items
ahead.  This means that provides/requires will not take effect at all
within items of a cycle.  That is a small change from today, in that
today there are some cases where that can happen, however, the current
behavior is so inconsistent that it would better to normalize it to
the current definition.  In other words, we will maintain the behavior
where jobs in the same queue item's job graph are not linked by
provides/requires.

Having done that, we can choose to, in a future change, expand the
search to include the job graph for a queue item, so that
provides/requires are satisfied via jobs for the same queue item or
even the same change.  This would apply equally to dependency cycles
or standalone changes.  This is often a point of confusion to users
and after the dependency cycle refactor would be a good time to
clarify it.  But in order to minimize behavioral changes during the
dependency refactor, we should evaluate and make that change
separately in the future, if desired.

Job Graph
~~~~~~~~~

When freezing the job graph, all changes in a queue item will be
considered.  A rough algorithm is:

#. Start with an empty job graph
#. For each change on the item:

   #. Freeze each job for that change
   #. Add it to the graph

#. Once all jobs are frozen, establish dependencies between jobs
#. Deduplicate jobs in the graph

   #. If a to-be-deduplicated job depends on a non-deduplicated job,
      it will treat each (job, ref) instance as a parent.
   #. Otherwise, each job will depend only on jobs for the same ref.

This maintains the status quo where users generally only need to
consider a single project when creating a project-pipeline definition,
but we will automatically merge those in a seamless way for dependency
cycles.

Upgrades
~~~~~~~~

We can perform some prep work to update internal data storage to
support the new system, but it may not be practical to actually
support both behaviors in code (to do so may require carrying two
copies of the model and pipeline manager codebases).  If this proves
impractical, as expected, then we won't be able to have a seamless
online upgrade, however, we can still have a zero-downtime upgrade
with a minimum of user-visible impact.

For any upgrades where we can't support both behaviors simultanously,
we can have the new components startup but avoid processing data until
all components have been upgraded.  In this way, we can startup new
schedulers (which may take tens of minutes to fully startup), and let
them idle while older schedulers continue to do work.  Once an
operator has started a sufficient number of schedulers, they can shut
down the old ones and the new ones will immediately resume work.  This
will leave operators with fewer operating schedulers during the
transition, but that time can be made very brief, with only delayed
job starts as user-visible impact.

Bundle Changes
~~~~~~~~~~~~~~

One of the complexities motiving this work is that the members of a
dependency cycle can change over time, potentially without updates to
the underlying changes (in GitHub via editing a PR message, and in
Gerrit by editing a change topic).  In these cases, the normal systems
that eject and potentially re-enqueue changes don't operate.

The new system will be better suited to this, as when we evaluate each
queue item, we can verify that the dependency cycle of its changes
matches its changes.  However, we should understand what should happen
in various cases.

If a change is added to a cycle, we should run the `addChange` method
(or equivalent) for every change in the cycle to ensure that all
dependencies of all of the items changes are enqueued ahead of it.

If the new change is not already in the pipeline, it will appear to
simply be added to the item.  If it is already in the pipeline behind
the current item, it will appear to move up in the pipeline.  The
reverse case will not happen because we will process each dependency
cycle the first time it appears in a pipeline.

As we process each item, we should check whether it is already
enqueued ahead (because it was added to an item ahead due to the
preceding process), and if so, dequeue it.

If a change is removed from a dependency cycle, it should be enqueued
directly ahead the item it was previously a part of.  Depending on
response time, this may happen automatically anyway as splitting a
cycle may still leave a one-way dependency between the two parts.

It may be desirable to perform two pipeline processing passes; one
where we adjust sequencing for any cycle changes, and a second where
we run the NNFI algorithm to make any necessary changes to buildsets.

The stable buildset UUID concept introduced by Simon in
https://review.opendev.org/895936 may be useful for this.

Work Items
----------

* Change the frozen job data storage in ZK from being identified by
  name to UUID.  This allows us to handle multiple frozen jobs in a
  buildset with the same name.  This can be done as an early
  standalone change.

* Make job dependency resolution happen at job graph freeze time.
  This lets us point to specific frozen jobs and we don't need to
  constantly recalculate them.  This will keep the determination of
  job parents as simple as possible as we perform the refactor.  This
  can be done as an early standalone change.

* Update SQL database.  We should be able to update the database to
  the new schema and map the current behavior onto it (since it's
  effectively the n=1 case).  This can be done as an early standalone
  change.

* Update the status page to handle multiple changes per item.  We can
  do the work needed to render multiple changes for a queue item, and
  again, use that with the current system as an n=1 case.  This can be
  done as an early standalone change.

* Update the BuildSet.job_map to transform it from from `{job.name:
  job}` to `{job.name: {change.cache_key: job}}`.  This will
  facilitate having multiple jobs with the same name in a buildset
  later, but again, will work for the n=1 case now.  This can be
  done as an early standalone change.

* Index the build dictionary on the BuildSet by job uuid.

* NodeRequests and Build*Events should also refer to job uuids.

* Update items to support multiple changes.  This is likely to be a
  large change where we simultaneously update anything where we can't
  support both systems ahead of time.
