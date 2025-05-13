.. _glossary:

Glossary
========

.. glossary::
   :sorted:

   abstract job

      A job which cannot be run directly, and is only intended to
      serve as a parent on top of which other jobs are constructed.

   artifact

      A file or set of files created by a build and archived for
      reuse.  The term is usually in reference to primary build
      outputs such as a release package or rendered documentation,
      but can also mean files produced as a byproduct such as logs.

   base job

      A job with no parent.  A base job may only be defined in a
      :term:`config-project`.  Multiple base jobs may be defined, but
      each tenant has a single default job which will be used as the
      parent of any job which does not specify one explicitly.

   build

      Any run of a job.  Every build is assigned a globally unique
      identifier which is used when coordinating between Zuul's
      component services, and for purposes such as addressing log
      streams and results in the status API and Web dashboard.  The
      context for a build comes not only from its job definition,
      but also from the pipeline into which it is scheduled.

   buildset

      A collection of builds which share a common context.  All
      builds in a buildset have the same triggering event and change
      identifier.

   change

      A specific state of a Git repository.  Changes can represent a
      change revision/pull request from a code review system, a
      remote branch tip, a tag, or any other sort of Git ref.  A
      change can also come with additional dependency context,
      either implicit from its commit history or explicit through
      the use of cross-project dependency declarations (for example
      in a commit message or pull request summary, the exact
      mechanism varies by source connection driver).

   child job

      A job which inherits values such as playbooks and variables
      from a parent job.  All jobs are implicitly child jobs, since
      they inherit from at least a base job whether they declare it
      as a parent or not.

   check

      By convention, the name of a pipeline which performs pre-merge
      tests.  Such a pipeline might be triggered by creating a new
      change or pull request.  It may run with changes which have not
      yet seen any human review, so care must be taken in selecting
      the kinds of jobs to run, and what resources will be available
      to them in order to avoid misuse of the system or credential
      compromise.  It usually has an :value:`independent
      <pipeline.manager.independent>` pipeline manager since the final
      sequence of changes to merge is not generally known at the time
      of upload.

   config-project

      One of two types of projects which may be specified by the
      administrator in the tenant config file.  A config-project is
      primarily tasked with holding configuration information and job
      content for Zuul.  Jobs which are defined in a config-project
      are run with elevated privileges, and all Zuul configuration
      items are available for use.  It is expected that changes to
      config-projects will undergo careful scrutiny before being
      merged.

   connection

      A coupling of a triggering and reporting driver with
      credentials and location information for a specific source of
      events, whether that's a code review platform, a generic Git
      hosting site or an emitting protocol such as SMTP or SQL.

   cross-project dependency

      An explicit declaration that a change depends on another
      change, which need not be in the same Git repository or even
      accessible via the same connection.  Zuul is expected to
      incorporate any cross-project dependencies into the context
      for the change declaring that dependency relationship.

   deploy

      By convention, the name of a continuous-deployment pipeline.
      Such a pipeline typically interacts with production systems
      rather than ephemeral test nodes.  By triggering on merge events
      the results of deployment can be reported back to the
      originating change.  The :value:`serial
      <pipeline.manager.serial>` pipeline manager, is recommended if
      multiple repositories are involved and only some jobs (based on
      file matchers) will be run for each change.  If a single repo is
      involved and all deployment jobs run on every change merged,
      then :value:`supercedent <pipeline.manager.supercedent>` may be
      a better fit.

   executor

      The component of Zuul responsible for executing a sandboxed
      Ansible process in order to produce a build.  Some builds may
      run entirely in the executor's provided workspace if the job
      is suitably constructed, or it may require the executor to
      connect to remote nodes for more complex and risky operations.

   final job

      A job which no other jobs are allowed to use as a parent, for
      example in order to prevent the list of tasks they run from
      being altered by potential child jobs.

   gate

      By convention, the name of a pipeline which performs project
      gating.  Such a pipeline might be triggered by a core team
      member approving a change or pull request.  It should have a
      :value:`dependent <pipeline.manager.dependent>` pipeline manager
      so that it can combine and sequence changes as they are
      approved.

   inventory

      The set of hosts and variable assignments Zuul provides to
      Ansible, forming the context for a build.

   job

      A collection of Ansible playbooks, variables, filtering
      conditions and other metadata defining a set of actions which
      should be taken when invoked under the intended circumstances.
      Jobs are anonymous sets of sequenced actions, which when
      executed in the context of a pipeline, result in a build.

   job dependency

      A declared reliance in one job on the completion of builds for
      one or more other jobs or provided artifacts those builds may
      produce.  Jobs may also be conditionally dependent on specific
      build results for their dependencies.

   job variant

      A lightweight modification of another defined job altering
      variables and filtering criteria.

   merger

      The component of Zuul responsible for constructing Git refs
      provided to builds based on supplied change contexts from
      triggering events.  An executor may also be configured to run
      a local merger process for increased efficiency.

   node

      A remote system resource on which Ansible playbooks may be
      executed, for strong isolation from the executor's
      environment.  In Ansible inventory terms, this is a remote
      host.

   nodeset

      An assembly of one or more nodes which, when applied in a job,
      are added as host entries to the Ansible inventory for its
      builds.  Nodes in a nodeset can be given convenient names for
      ease of reference in job playbooks.

   parent job

      A job from which a child job inherits values such as playbooks
      and variables.  Depending on the type of playbooks and
      variables, these may either be merged with or overridden by
      the child job.  Any job which doesn't specify a parent
      inherits from the tenant's base job.

   pipeline

      A set of triggering, prioritizing, scheduling, and reporting
      rules which provide the context for a build.

   pipeline manager

      The algorithm through which a pipeline manages queuing of
      trigger events.  Specifically, this determines whether changes
      are queued independently, sequenced together in the order
      they're approved, or superceded entirely by subsequent events.

   project

      A unique Git source repository available through a connection
      within a tenant.  Projects are identified by their connection
      or hostname, combined with their repository, so as to avoid
      ambiguity when two repositories of the same name are available
      through different connections.

   project gating

      Automatically preventing a proposed change from merging to a
      canonical source code repository for a project until it is
      able to pass declared tests for that repository.  In a project
      gating workflow, cues may be taken from its users, but it is
      ultimately the gating system which controls merging of changes
      and not the users themselves.

   project pipeline

      The application of jobs to a pipeline.  Project pipeline
      entries often include filtering and matching rules specifying
      the conditions under which a job should result in a build, and
      any interdependencies those jobs may have on the build results
      and named artifacts provided by other jobs.

   project queue

      The set of changes sequenced for testing, either explicitly
      through dependency relationships, or implicitly from the
      chronological ordering of triggering events which enqueued
      them.  Project queues can be named and shared by multiple
      projects, ensuring sequential merging of changes across those
      projects.

   project template

      A named mapping of jobs into pipelines, for application to one
      or more projects.  This construct provides a convenient means
      of reusing the same sets of jobs in the same pipelines across
      multiple projects.

   promote

      By convention, the name of a pipeline which uploads previously
      built artifacts.  These artifacts should be constructed in a
      :term:`gate` pipeline and uploaded to a temporary location.
      When all of the jobs in the gate pipeline succeed, the change
      will be merged and may then be enqueued into a promote pipeline.
      Jobs running in this pipeline do so with the understanding that
      since the change merged as it was tested in the gate, any
      artifacts created at that time are now safe to promote to
      production. It is a good choice to use a :value:`supercedent
      <pipeline.manager.supercedent>` pipeline manager so that if many
      changes merge in rapid sequence, Zuul may skip promoting all but
      the latest artifact to production.

   provided artifact

      A named artifact which builds of a job are expected to
      produce, for purposes of dependency declarations in other
      jobs.  Multiple jobs may provide equivalent artifacts with the
      same name, allowing these relationships to be defined
      independent of the specific jobs which provide them.

   post

      By convention, the name of a pipeline which runs after a branch
      is updated.  By triggering on a branch update (rather than a
      merge) event, jobs in this pipeline may run with the final git
      state after the merge (including any merge commits generated by
      the upstream code review system).  This is important when
      building some artifacts in order that the exact commit ids are
      present in the git repo.  The downside to this approach is that
      jobs in this pipeline run without any connection to the
      underlying changes which created the commits.  If only the
      latest updates to a branch matter, then the :value:`supercedent
      <pipeline.manager.supercedent>` pipeline manager is recommended;
      otherwise :value:`independent <pipeline.manager.independent>`
      may be a better choice.  See also :term:`tag` and
      :term:`release`.

   release

      By convention, the name of a pipeline which runs after a
      release-formatted tag is updated.  Other than the matching ref,
      this is typically constructed the same as a :term:`post`
      pipeline.  See also :term:`tag`.

   reporter

      A reporter is a :ref:`pipeline attribute <reporters>` which
      describes the action performed when an item is dequeued after
      its jobs complete.  Reporters are implemented by :ref:`drivers`
      so their actions may be quite varied.  For example, a reporter
      might leave feedback in a remote system on a proposed change,
      send email, or store information in a database.

   required artifact

      An artifact provided by one or more jobs, on which execution
      of the job requiring it depends.

   required project

      A project whose source code is required by the job.  Jobs
      implicitly require the project associated with the event
      which triggered their build, but additional projects can be
      specified explicitly as well.  Zuul supplies merge commits
      representing the speculative future states of all required
      projects for a build.

   scheduler

      The component of Zuul which coordinates source and reporting
      connections as well as requests for nodes, mergers and
      executors for builds triggered by pipeline definitions in the
      tenant configuration.

   speculative execution

      A term borrowed from microprocessor design, the idea that
      sequenced operations can be performed in parallel by
      predicting their possible outcomes and then discarding any
      logical branches which turn out not to be true.  Zuul uses
      optimistic prediction to assume all builds for a change will
      succeed, and then proceeds to run parallel builds for other
      changes which would follow it in sequence.  If a change enters
      a failing state (at least one of its voting builds indicates a
      failure result), then Zuul resets testing for all subsequent
      queue items to no longer include it in their respective
      contexts.

   tag

      By convention, the name of a pipeline which runs after a tag is
      updated.  Other than the matching ref, this is typically
      constructed the same as a :term:`post` pipeline.  See also
      :term:`release`.

   tenant

      A set of projects on which Zuul should operate.  Configuration
      is not shared between tenants, but the same projects from the
      same connections may appear in more than one tenant and the
      same events may even enqueue the same changes in pipelines for
      more than one tenant.  Zuul's HTTP API methods and Web
      dashboard are scoped per tenant, in order to support distinct
      tenant-specific authentication and authorization.

   trigger

      A (typically external) event which Zuul may rely on as a cue
      to enqueue a change into a pipeline.

   trusted execution context

      Playbooks defined in a :term:`config-project` run in the
      *trusted* execution context.  The trusted execution context may
      have access to extra directories within the bubblewrap container
      if the operator has configured these.

   untrusted execution context

      Playbooks defined in an :term:`untrusted-project` run in the
      *untrusted* execution context.

   untrusted-project

      One of two types of projects which may be specified by the
      administrator in the tenant config file.  An untrusted-project
      is one whose primary focus is not to operate Zuul, but rather it
      is one of the projects being tested or deployed.  The Zuul
      configuration language available to these projects is somewhat
      restricted, and jobs defined in these projects run in a
      restricted execution environment since they may be operating on
      changes which have not yet undergone review.

   window

      The portion of a pipeline (most relevant to :value:`dependent
      pipelines <pipeline.manager.dependent>`) that is permitted to
      run jobs.  Zuul has a number of configuration options and
      heuristics designed to match resource usage to pipeline
      throughput in order to merge changes quickly without wasting
      test resources on changes unlikely to merge.
