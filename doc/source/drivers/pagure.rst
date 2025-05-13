:title: Pagure Driver

.. _pagure_driver:

Pagure
======

The Pagure driver supports sources, triggers, and reporters.  It can
interact with the public Pagure.io service as well as site-local
installations of Pagure.

Configure Pagure
----------------

The user's API token configured in zuul.conf must have the following
ACL rights:

- "Merge a pull-request" set to on (optional, only for gating)
- "Flag a pull-request" set to on
- "Comment on a pull-request" set to on
- "Modify an existing project" set to on

Each project to be integrated with Zuul needs:

- "Web hook target" set to
  http://<zuul-web>/zuul/api/connection/<conn-name>/payload
- "Pull requests" set to on
- "Open metadata access to all" set to off (optional, expected if approval
  based on PR a metadata tag)
- "Minimum score to merge pull-request" set to the same value than
  the score requierement (optional, expected if score requierement is
  defined in a pipeline)

Furthermore, the user must be added as project collaborator
(**ticket** access level), to be able to read the project's
webhook token. This token is used to validate webhook's payload. But
if Zuul is configured to merge pull requests then the access level
must be **commit**.

Connection Configuration
------------------------

The supported options in ``zuul.conf`` connections are:

.. attr:: <pagure connection>

   .. attr:: driver
      :required:

      .. value:: pagure

         The connection must set ``driver=pagure`` for Pagure connections.

   .. attr:: api_token

      The user's API token with the ``Modify an existing project`` capability.

   .. attr:: server
      :default: pagure.io

      Hostname of the Pagure server.

   .. attr:: canonical_hostname

      The canonical hostname associated with the git repos on the
      Pagure server.  Defaults to the value of :attr:`<pagure
      connection>.server`.  This is used to identify projects from
      this connection by name and in preparing repos on the filesystem
      for use by jobs.  Note that Zuul will still only communicate
      with the Pagure server identified by **server**; this option is
      useful if users customarily use a different hostname to clone or
      pull git repos so that when Zuul places them in the job's
      working directory, they appear under this directory name.

   .. attr:: baseurl
      :default: https://{server}

      Path to the Pagure web and API interface.

   .. attr:: cloneurl
      :default: https://{baseurl}

      Path to the Pagure Git repositories. Used to clone.

   .. attr:: app_name
      :default: Zuul

      Display name that will appear as the application name in front
      of each CI status flag.

   .. attr:: source_whitelist
      :default: ''

      A comma separated list of source ip adresses from which webhook
      calls are whitelisted. If the source is not whitelisted, then
      call payload's signature is verified using the project webhook
      token. An admin access to the project is required by Zuul to read
      the token. White listing a source of hook calls allows Zuul to
      react to events without any authorizations. This setting should
      not be used in production.


Trigger Configuration
---------------------
Pagure webhook events can be configured as triggers.

A connection name with the Pagure driver can take multiple events with
the following options.

.. attr:: pipeline.trigger.<pagure source>

   The dictionary passed to the Pagure pipeline ``trigger`` attribute
   supports the following attributes:

   .. attr:: event
      :required:

      The event from Pagure. Supported events are:

      .. value:: pg_pull_request

      .. value:: pg_pull_request_review

      .. value:: pg_push

   .. attr:: action

      A :value:`pipeline.trigger.<pagure source>.event.pg_pull_request`
      event will have associated action(s) to trigger from. The
      supported actions are:

      .. value:: opened

         Pull request opened.

      .. value:: changed

         Pull request synchronized.

      .. value:: closed

         Pull request closed.

      .. value:: comment

         Comment added to pull request.

      .. value:: status

         Status set on pull request.

      .. value:: tagged

         Tag metadata set on pull request.

      A :value:`pipeline.trigger.<pagure
      source>.event.pg_pull_request_review` event will have associated
      action(s) to trigger from. The supported actions are:

      .. value:: thumbsup

         Positive pull request review added.

      .. value:: thumbsdown

         Negative pull request review added.

   .. attr:: comment

      This is only used for ``pg_pull_request`` and ``comment`` actions.  It
      accepts a list of regexes that are searched for in the comment
      string. If any of these regexes matches a portion of the comment
      string the trigger is matched.  ``comment: retrigger`` will
      match when comments containing 'retrigger' somewhere in the
      comment text are added to a pull request.

   .. attr:: status

      This is used for ``pg_pull_request`` and ``status`` actions. It
      accepts a list of strings each of which matches the user setting
      the status, the status context, and the status itself in the
      format of ``status``.  For example, ``success`` or ``failure``.

   .. attr:: tag

      This is used for ``pg_pull_request`` and ``tagged`` actions. It
      accepts a list of strings and if one of them is part of the
      event tags metadata then the trigger is matched.

   .. attr:: ref

      This is only used for ``pg_push`` events. This field is treated as
      a regular expression and multiple refs may be listed. Pagure
      always sends full ref name, eg. ``refs/tags/bar`` and this
      string is matched against the regular expression.

Reporter Configuration
----------------------
Zuul reports back to Pagure via Pagure API. Available reports include a PR
comment containing the build results, a commit status on start, success and
failure, and a merge of the PR itself. Status name, description, and context
is taken from the pipeline.

.. attr:: pipeline.<reporter>.<pagure source>

   To report to Pagure, the dictionaries passed to any of the pipeline
   :ref:`reporter<reporters>` attributes support the following
   attributes:

   .. attr:: status

      String value (``pending``, ``success``, ``failure``) that the
      reporter should set as the commit status on Pagure.

   .. attr:: comment
      :default: true

      Boolean value that determines if the reporter should add a
      comment to the pipeline status to the Pagure Pull Request. Only
      used for Pull Request based items.

   .. attr:: merge
      :default: false

      Boolean value that determines if the reporter should merge the
      pull Request. Only used for Pull Request based items.


Requirements Configuration
--------------------------

As described in :attr:`pipeline.require` pipelines may specify that items meet
certain conditions in order to be enqueued into the pipeline.  These conditions
vary according to the source of the project in question.  To supply
requirements for changes from a Pagure source named ``pagure``, create a
configuration such as the following:

.. code-block:: yaml

   pipeline:
     require:
       pagure:
         score: 1
         merged: false
         status: success
         tags:
           - gateit

This indicates that changes originating from the Pagure connection
must have a score of *1*, a CI status *success* and not being already merged.

.. attr:: pipeline.require.<pagure source>

   The dictionary passed to the Pagure pipeline `require` attribute
   supports the following attributes:

   .. attr:: score

      If present, the minimal score a Pull Request must reached.

   .. attr:: status

      If present, the CI status a Pull Request must have.

   .. attr:: merged

      A boolean value (``true`` or ``false``) that indicates whether
      the Pull Request must be merged or not in order to be enqueued.

   .. attr:: open

      A boolean value (``true`` or ``false``) that indicates whether
      the Pull Request must be open or closed in order to be enqueued.

   .. attr:: tags

      if present, the list of tags a Pull Request must have.


Reference pipelines configuration
---------------------------------

Here is an example of standard pipelines you may want to define:

.. literalinclude:: /examples/pipelines/pagure-reference-pipelines.yaml
   :language: yaml
