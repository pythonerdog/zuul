:title: Project Gating

.. _project_gating:

Project Gating
==============

Traditionally, many software development projects merge changes from
developers into the repository, and then identify regressions
resulting from those changes (perhaps by running a test suite with a
continuous integration system), followed by more patches to fix those
bugs.  When the mainline of development is broken, it can be very
frustrating for developers and can cause lost productivity,
particularly so when the number of contributors or contributions is
large.

The process of gating attempts to prevent changes that introduce
regressions from being merged.  This keeps the mainline of development
open and working for all developers, and only when a change is
confirmed to work without disruption is it merged.

Many projects practice an informal method of gating where developers
with mainline commit access ensure that a test suite runs before
merging a change.  With more developers, more changes, and more
comprehensive test suites, that process does not scale very well, and
is not the best use of a developer's time.  Zuul can help automate
this process, with a particular emphasis on ensuring large numbers of
changes are tested correctly.

Testing in parallel
-------------------

A particular focus of Zuul is ensuring correctly ordered testing of
changes in parallel.  A gating system should always test each change
applied to the tip of the branch exactly as it is going to be merged.
A simple way to do that would be to test one change at a time, and
merge it only if it passes tests.  That works very well, but if
changes take a long time to test, developers may have to wait a long
time for their changes to make it into the repository.  With some
projects, it may take hours to test changes, and it is easy for
developers to create changes at a rate faster than they can be tested
and merged.

Zuul's :value:`dependent pipeline manager<pipeline.manager.dependent>`
allows for parallel execution of test jobs for gating while ensuring
changes are tested correctly, exactly as if they had been tested one
at a time.  It does this by performing speculative execution of test
jobs; it assumes that all jobs will succeed and tests them in parallel
accordingly.  If they do succeed, they can all be merged.  However, if
one fails, then changes that were expecting it to succeed are
re-tested without the failed change.  In the best case, as many
changes as execution contexts are available may be tested in parallel
and merged at once.  In the worst case, changes are tested one at a
time (as each subsequent change fails, changes behind it start again).

For example, if a reviewer approves five changes in rapid succession::

  A, B, C, D, E

Zuul queues those changes in the order they were approved, and notes
that each subsequent change depends on the one ahead of it merging:

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];
     A -> B -> C -> D -> E;
   }


Zuul then starts immediately testing all of the changes in parallel.
But in the case of changes that depend on others, it instructs the
test system to include the changes ahead of it, with the assumption
they pass.  That means jobs testing change *B* include change *A* as
well::

  Jobs for A: merge change A, then test
  Jobs for B: merge changes A and B, then test
  Jobs for C: merge changes A, B and C, then test
  Jobs for D: merge changes A, B, C and D, then test
  Jobs for E: merge changes A, B, C, D and E, then test

Hence jobs triggered to tests A will only test A and ignore B, C, D:

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     subgraph cluster_merged {
       label="Merged Changes for A";
       style=filled;
       color=orange;
       node [style=filled,color=black,fillcolor=white];
       master -> A;
     }

     subgraph cluster_ignored {
       label="Ignored Changes";
       style=filled;
       color=lightgrey;
       node [style=filled,color=black,fillcolor=white];
       B -> C -> D -> E;
     }

     A -> B;
   }

The jobs for E would include the whole dependency chain: A, B, C, D, and E.
E will be tested assuming A, B, C, and D passed:

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     subgraph cluster_merged {
       label="Merged Changes for E";
       style=filled;
       color=orange;
       node [style=filled,color=black,fillcolor=white];
       master -> A -> B -> C -> D -> E;
     }
   }

If changes *A* and *B* pass tests (green), and *C*, *D*, and *E* fail (red):

.. graphviz::

   digraph foo{
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     A [style=filled,color=black,fillcolor=lightgreen];
     B [style=filled,color=black,fillcolor=lightgreen];
     C [style=filled,color=black,fillcolor=lightpink];
     D [style=filled,color=black,fillcolor=lightpink];
     E [style=filled,color=black,fillcolor=lightpink];
     master -> A -> B -> C -> D -> E;
   }

Zuul will merge change *A* followed by change *B*, leaving this queue:

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     C [style=filled,color=black,fillcolor=lightpink];
     D [style=filled,color=black,fillcolor=lightpink];
     E [style=filled,color=black,fillcolor=lightpink];
     C -> D -> E;
   }

Since *D* was dependent on *C*, it is not clear whether *D*'s failure is the
result of a defect in *D* or *C*:

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     C [style=filled,color=black,fillcolor=lightpink];
     D [label="D\n?"];
     E [label="E\n?"];
     C -> D -> E;
   }

Since *C* failed, Zuul will report its failure and drop *C* from the queue,
keeping D and E:

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     D [label="D\n?"];
     E [label="E\n?"];
     D -> E;
   }

This queue is the same as if two new changes had just arrived, so Zuul
starts the process again testing *D* against the tip of the branch, and
*E* against *D*:

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     subgraph cluster_merged {
       label="Merged Changes for D";
       style=filled;
       color=orange;
       node [style=filled,color=black,fillcolor=white];
       master -> D;
     }

     subgraph cluster_skip {
       label="Skip";
       style=filled;
       color=lightgrey;
       node [style=filled,color=black,fillcolor=white];
       E;
     }

     D -> E;
   }

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     subgraph cluster_merged {
       label="Merged Changes for E";
       style=filled;
       color=orange;
       node [style=filled,color=black,fillcolor=white];
       master -> D -> E;
     }
   }

.. _pipeline_window:

Pipeline Window
~~~~~~~~~~~~~~~

Zuul allows for some control over this process.  Pipelines have a
:term:`window` which is portion of the pipeline where jobs are
permitted to run.  The window is the number of changes at the head of
the queue where Zuul will start jobs.  Any changes beyond this number
are held in the queue without running jobs.  As changes exit the head
of the queue, the changes outside the window will move up and
eventually start their jobs.

.. graphviz::

   digraph foo {
     bgcolor="transparent";
     rankdir="LR";
     node [shape=box];
     edge [dir=back];

     subgraph cluster_active {
       label="Pipeline Active Window";
       style=filled;
       color=lightblue1;
       node [style=filled,color=black,fillcolor=white];
       A -> B -> C;
     }

     subgraph cluster_inactive {
       label="Waiting to run jobs";
       style=filled;
       color=lightgrey;
       node [style=filled,color=black,fillcolor=white];
       D -> E;
     }

     master -> A;
     C -> D;
   }

The window is designed to control the amount of resources used for
parallel testing.  As described above, if changes fail testing in a
dependent pipeline, build results are discarded and new builds are
started without the failing changes.  If this happens frequently, then
Zuul can end up using increasingly large amounts of test resources for
little gain.  Ideally if builds frequently succeed, the window should
be large in order to maximize throughput, and if they frequently fail,
it should be small in order to minimize waste.

By default, Zuul uses an algorithm inspired by the Transmission
Control Protocol's flow control to determine the window size.  It
starts with the window set to a certain value (twenty changes by
default).  Each time a change successfully merges, the window is
increased by one.  Each time a change fails, the window is halved.
This allows the window to shrink rapidly when changes start to fail,
and recover slowly if they succeed.  A floor is set to ensure that (by
default) there is always at least some amount of parallel testing, and
a ceiling may be set to prevent a wildly successful pipeline from
starving others of resources.

All of the parameters above can be customized to match local needs,
but the defaults are a good starting point.  See
:attr:`pipeline.window` for details.

The window parameters are set on the pipeline, but each :term:`project
queue` within that pipeline maintains its own window so that
unreliable tests in one project queue don't affect the window of other
project queues.

While every pipeline has a window, only pipelines using the
:value:`dependent <pipeline.manager.dependent>` pipeline manager allow
configuration of the window.  Other pipeline managers use fixed values
to implement their particular behaviors.  For example,
:value:`independent <pipeline.manager.independent>` pipelines always
have unlimited windows, and :value:`serial <pipeline.manager.serial>`
pipelines have a fixed window size of 1.

The window can be visualized in the web interface by inspecting the
icon to the left of a change.  If a change is outside the window, it
will have an hourglass icon and the mouseover text will indicate that
jobs will start when the change moves closer to the head of the queue.


Cross Project Testing
---------------------

When your projects are closely coupled together, you want to make sure
changes entering the gate are going to be tested with the version of
other projects currently enqueued in the gate (since they will
eventually be merged and might introduce breaking features).

Such relationships can be defined in Zuul configuration by placing
projects in a shared queue within a dependent pipeline.  Whenever
changes for any project enter a pipeline with such a shared queue,
they are tested together, such that the commits for the changes ahead
in the queue are automatically present in the jobs for the changes
behind them.  See :ref:`project` for more details.

A given dependent pipeline may have as many shared change queues as
necessary, so groups of related projects may share a change queue
without interfering with unrelated projects.
:value:`Independent pipelines <pipeline.manager.independent>` do
not use shared change queues, however, they may still be used to test
changes across projects using cross-project dependencies.

.. _dependencies:

Cross-Project Dependencies
--------------------------

Zuul permits users to specify dependencies across projects.  Using a
special footer, users may specify that a change depends on another
change in any repository known to Zuul.  In Gerrit based projects
this footer needs to be added to the git commit message.  In GitHub
based projects this footer must be added to the pull request description.

Zuul's cross-project dependencies behave like a directed acyclic graph
(DAG), like git itself, to indicate a one-way dependency relationship
between changes in different git repositories.  Change A may depend on
B, but B may not depend on A.

To use them, include ``Depends-On: <change-url>`` in the footer of a
commit message or pull request.  For example, a change which depends
on a GitHub pull request (PR #4) might have the following footer::

  Depends-On: https://github.com/example/test/pull/4

.. note::

   For Github the ``Depends-On:`` footer must be in the *Pull Request*
   description, which is separate and often different to the commit
   message (i.e. the text submitted with ``git commit``).  This is in
   contrast to Gerrit where the change description is always the
   commit message.

A change which depends on a Gerrit change (change number 3)::

  Depends-On: https://review.example.com/3

Changes may depend on changes in any other project, even projects not
on the same system (i.e., a Gerrit change may depend on a GitHub pull
request).

.. note::

   An older syntax of specifying dependencies using Gerrit change-ids
   is still supported, however it is deprecated and will be removed in
   a future version.

Dependent Pipeline
~~~~~~~~~~~~~~~~~~

When Zuul sees changes with cross-project dependencies, it serializes
them in the usual manner when enqueuing them into a pipeline.  This
means that if change A depends on B, then when they are added to a
dependent pipeline, B will appear first and A will follow:

.. graphviz::

   digraph crd {
     bgcolor="transparent";
     stat_B [shape=circle,style=filled,color=black,fillcolor=forestgreen,label=""];
     stat_A [shape=circle,style=filled,color=black,fillcolor=forestgreen,label=""];
     stat_B -> stat_A [arrowhead="none"];

     change_B [shape=box,fixedsize=true,width=1.75,height=0.75,label="Change B\nURL: .../4"];
     change_A [shape=box,fixedsize=true,width=1.75,height=0.75,label="Change A\nDepends-On: .../4"];

     change_B -> change_A [dir=back];
   }

If tests for B fail, both B and A will be removed from the pipeline, and
it will not be possible for A to merge until B does.


.. note::

   If changes with cross-project dependencies do not share a change
   queue then Zuul is unable to enqueue them together, and the first
   will be required to merge before the second can be enqueued. If the
   second change is approved before the first is merged, Zuul can't act
   on the approval and won't automatically enqueue the second change,
   requiring a new approval event to enqueue it after the first change
   merges.

Independent Pipeline
~~~~~~~~~~~~~~~~~~~~

When changes are enqueued into an independent pipeline, all of the
related dependencies (both normal git-dependencies that come from
parent commits as well as cross-project dependencies) appear in a
dependency graph, as in a dependent pipeline. This means that even in
an independent pipeline, your change will be tested with its
dependencies.  Changes that were previously unable to be fully tested
until a related change landed in a different repository may now be
tested together from the start.

All of the changes are still independent (you will note that the whole
pipeline does not share a graph as in a dependent pipeline), but for
each change tested, all of its dependencies are visually connected to
it, and they are used to construct the git repositories that Zuul uses
when testing.

When looking at this graph on the status page, you will note that the
dependencies show up as grey dots, while the actual change tested shows
up as red or green (depending on the jobs results):

.. graphviz::

   digraph crdgrey {
     bgcolor="transparent";
     stat_B [shape=circle,style=filled,color=black,fillcolor=grey,label=""];
     stat_A [shape=circle,style=filled,color=black,fillcolor=forestgreen,label=""];
     stat_B -> stat_A [arrowhead="none"];

     change_B [shape=box,fixedsize=true,width=1.75,height=0.75,label="Change B\nURL: .../4"];
     change_A [shape=box,fixedsize=true,width=1.75,height=0.75,label="Change A\nDepends-On: .../4"];

     change_B -> change_A [dir=back];
   }

This is to indicate that the grey changes are only there to establish
dependencies.  Even if one of the dependencies is also being tested, it
will show up as a grey dot when used as a dependency, but separately and
additionally will appear as its own red or green dot for its test.


Multiple Changes
~~~~~~~~~~~~~~~~

A change may list more than one dependency by simply adding more
``Depends-On:`` lines to the commit message footer.  It is possible
for a change in project A to depend on a change in project B and a
change in project C.

.. graphviz::

   digraph crdmultichanges {
     bgcolor="transparent";
     splines=ortho;
     stat_B [shape=circle,style=filled,color=black,fillcolor=forestgreen,label=""];
     stat_C [shape=circle,style=filled,color=black,fillcolor=forestgreen,label=""];
     stat_A [shape=circle,style=filled,color=black,fillcolor=forestgreen,label=""];
     stat_B -> stat_C -> stat_A [arrowhead="none"];

     subgraph cluster_deps {
       label="Dependencies";
       style=filled;
       color=lightgrey;
       node [style=filled,color=black,fillcolor=white];
       repo_B [shape=box,fixedsize=true,width=1.75,height=0.75,label="Repo B\nURL: .../3",group=redir];
       repo_C [shape=box,fixedsize=true,width=1.75,height=0.75,label="Repo C\nURL: .../4",group=redir];
       {rank=same;repo_B;redir_B}
       // We use the redirect point, group redir, and ortho splines to keep
       // repo A,B,C nodes in a vertical line then draw lines from A around
       // C to B.
       redir_B [label="",shape=point,height=.005];
       // This is an invisible edge because we want them vertically aligned
       // and ordered but there is no git/zuul dependency between the changes
       // so we don't draw the edge.
       repo_B -> repo_C [style=invis];
     }

     repo_A [shape=box,fixedsize=true,width=1.75,height=0.75,label="Repo A\nDepends-On: .../3\nDepends-On: .../4",group=redir];
     repo_B -> redir_B [dir=back];
     redir_B -> repo_A [arrowhead=none];
     repo_C -> repo_A [dir=back];
   }

Cycles
~~~~~~

Zuul supports cycles that are created by use of cross-project dependencies.
However this feature is opt-in and can be configured on the queue.
See :attr:`queue.allow-circular-dependencies` for information on how to
configure this.

.. _global_repo_state:

Global Repo State
~~~~~~~~~~~~~~~~~

If a git repository is used by at least one job for a queue item, then
Zuul will freeze the repo state (i.e., branch heads and tags) and use
that same state for every job run for that queue item.  Not every job
will get a git repo checkout of every repo, but for any repo that is
checked out, it will have the same state.  Because of this, authors
can be sure that jobs running on the same queue item have a consistent
view of all involved git repos, even if one job starts running much
later than another.
