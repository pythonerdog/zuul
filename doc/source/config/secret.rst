.. _secret:

Secret
======

A Secret is a collection of private data for use by one or more jobs.
In order to maintain the security of the data, the values are usually
encrypted, however, data which are not sensitive may be provided
unencrypted as well for convenience.

A Secret may only be used by jobs defined within the same project.
Note that they can be used by any branch of that project, so if a
project's branches have different access controls, consider whether
all branches of that project are equally trusted before using secrets.

To use a secret, a :ref:`job` must specify the secret in
:attr:`job.secrets`.  With one exception, secrets are bound to the
playbooks associated with the specific job definition where they were
declared.  Additional pre or post playbooks which appear in child jobs
will not have access to the secrets, nor will playbooks which override
the main playbook (if any) of the job which declared the secret.  This
protects against jobs in other repositories declaring a job with a
secret as a parent and then exposing that secret.

The exception to the above is if the
:attr:`job.secrets.pass-to-parent` attribute is set to true.  In that
case, the secret is made available not only to the playbooks in the
current job definition, but to all playbooks in all parent jobs as
well.  This allows for jobs which are designed to work with secrets
while leaving it up to child jobs to actually supply the secret.  Use
this option with care, as it may allow the authors of parent jobs to
accidentially or intentionally expose secrets.  If a secret with
`pass-to-parent` set in a child job has the same name as a secret
available to a parent job's playbook, the secret in the child job will
not override the parent, instead it will simply not be available to
that playbook (but will remain available to others).

It is possible to use secrets for jobs defined in :term:`config
projects <config-project>` as well as :term:`untrusted projects
<untrusted-project>`, however their use differs slightly.  Because
playbooks in a config project which use secrets run in the
:term:`trusted execution context` where proposed changes are not used
in executing jobs, it is safe for those secrets to be used in all
types of pipelines.  However, because playbooks defined in an
untrusted project are run in the :term:`untrusted execution context`
where proposed changes are used in job execution, it is dangerous to
allow those secrets to be used in pipelines which are used to execute
proposed but unreviewed changes.  By default, pipelines are considered
`pre-review` and will refuse to run jobs which have playbooks that use
secrets in the untrusted execution context (including those subject to
:attr:`job.secrets.pass-to-parent` secrets) in order to protect
against someone proposing a change which exposes a secret.  To permit
this (for instance, in a pipeline which only runs after code review),
the :attr:`pipeline.post-review` attribute may be explicitly set to
``true``.

In some cases, it may be desirable to prevent a job which is defined
in a config project from running in a pre-review pipeline (e.g., a job
used to publish an artifact).  In these cases, the
:attr:`job.post-review` attribute may be explicitly set to ``true`` to
indicate the job should only run in post-review pipelines.

If a job with secrets is unsafe to be used by other projects, the
:attr:`job.allowed-projects` attribute can be used to restrict the
projects which can invoke that job.  If a job with secrets is defined
in an `untrusted-project`, `allowed-projects` is automatically set to
that project only, and can not be overridden (though a
:term:`config-project` may still add the job to any project's pipeline
regardless of this setting; do so with caution as other projects may
expose the source project's secrets).

Secrets, like most configuration items, are unique within a tenant,
though a secret may be defined on multiple branches of the same
project as long as the contents are the same.  This is to aid in
branch maintenance, so that creating a new branch based on an existing
branch will not immediately produce a configuration error.

When the values of secrets are passed to Ansible, the ``!unsafe`` YAML
tag is added which prevents them from being evaluated as Jinja
expressions.  This is to avoid a situation where a child job might
expose a parent job's secrets via template expansion.

However, if it is known that a given secret value can be trusted, then
this limitation can be worked around by using the following construct
in a playbook:

.. code-block:: yaml

   - set_fact:
       unsafe_var_eval: "{{ hostvars['localhost'].secretname.var }}"

This will force an explicit template evaluation of the `var` attribute
on the `secretname` secret.  The results will be stored in
unsafe_var_eval.

.. attr:: secret

   The following attributes must appear on a secret:

   .. attr:: name
      :required:

      The name of the secret, used in a :ref:`job` definition to
      request the secret.

   .. attr:: data
      :required:

      A dictionary which will be added to the Ansible variables
      available to the job.  The values can be any of the normal YAML
      data types (strings, integers, dictionaries or lists) or
      encrypted strings.  See :ref:`encryption` for more information.
