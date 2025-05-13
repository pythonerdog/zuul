Zuul Runner
===========

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

While Zuul can be deployed to reproduce a job locally, it
is a complex enough system to setup. Zuul jobs being written in
Ansible, we shouldn't have to setup a Zookeeper, Nodepool and Zuul
service to run a job locally.

To that end, the Zuul Project should create a command line utility
to run a job locally using direct ansible-playbook commands execution.
The scope includes two use cases:

* Running a local build of a job that has already ran, for example to
  recreate a build that failed in the gate, through using either
  a `zuul-info/inventory.yaml` file, or using the `--change-url` command
  line argument.

* Being able to run any job from any Zuul instance, tenant, project
  or pipeline regardless if it has run or not.

Zuul Job Execution Context
--------------------------

One of the key parts of making the Zuul Runner command line utility
is to reproduce as close as possible the zuul service environment.

A Zuul job requires:

- Test resources
- Copies of the required projects
- Ansible configuration
- Decrypted copies of the secrets


Test Resources
~~~~~~~~~~~~~~

The Zuul Runner shall require the user to provide test resources
as an Ansible inventory, similarly to what Nodepool provides to the
Zuul Executor. The Runner would enrich the inventory with the zuul
vars.

For example, if a job needs two nodes, then the user provides
a resource file like this:

.. code-block:: yaml

   all:
     hosts:
       controller:
         ansible_host: ip-node-1
         ansible_user: user-node-1
       worker:
         ansible_host: ip-node-2
         ansible_user: user-node-2



Required Projects
~~~~~~~~~~~~~~~~~

The Zuul Runner shall query an existing Zuul API to get the list
of projects required to run a job. This is implemented as part of
the `topic:freeze_job` changes to expose the executor gearman parameters.

The CLI would then perform the executor service task to clone and merge
the required project locally.

Ansible Configuration
~~~~~~~~~~~~~~~~~~~~~

The CLI would also perform the executor service tasks to setup the
execution context.


Playbooks
~~~~~~~~~

In some case, running all the job playbooks is not desirable,
in this situation the CLI provides a way to select and filter
unneeded playbook.

"zuul-runner --list-playbooks" and it would print out:

.. code-block:: console

   0: opendev.org/base-jobs/playbooks/pre.yaml
   ...
   10: opendev.org/base-jobs/playbooks/post.yaml

To avoid running the playbook 10, the user would use:

* "--no-playbook 10"
* "--no-playbook -1"
* "--playbook 1..9"

Alternatively, a matcher may be implemented to express:

* "--skip 'opendev.org/base-jobs/playbooks/post.yaml'"


Secrets
~~~~~~~

The Zuul Runner shall require the user to provide copies of
any secrets required by the job.

Implementation
--------------

The process of exposing gearman parameter and refactoring the executor
code to support local/direct usage already started here:
https://review.opendev.org/#/q/topic:freeze_job+(status:open+OR+status:merged)


Zuul Runner CLI
---------------

Here is the proposed usage for the CLI:

.. code-block:: console

   usage: zuul-runner [-h] [-c CONFIG] [--version] [-v] [-e FILE] [-a API]
                      [-t TENANT] [-j JOB] [-P PIPELINE] [-p PROJECT] [-b BRANCH]
                      [-g GIT_DIR] [-D DEPENDS_ON]
                      {prepare-workspace,execute} ...

   A helper script for running zuul jobs locally.

   optional arguments:
     -h, --help            show this help message and exit
     -c CONFIG             specify the config file
     --version             show zuul version
     -v, --verbose         verbose output
     -e FILE, --extra-vars FILE
                           global extra vars file
     -a API, --api API     the zuul server api to query against
     -t TENANT, --tenant TENANT
                           the zuul tenant name
     -j JOB, --job JOB     the zuul job name
     -P PIPELINE, --pipeline PIPELINE
                           the zuul pipeline name
     -p PROJECT, --project PROJECT
                           the zuul project name
     -b BRANCH, --branch BRANCH
                           the zuul project's branch name
     -g GIT_DIR, --git-dir GIT_DIR
                           the git merger dir
     -C CHANGE_URL, --change-url CHANGE_URL
                           reproduce job with speculative change content

   commands:
     valid commands

     {prepare-workspace,execute}
       prepare-workspace   checks out all of the required playbooks and roles
                           into a given workspace and returns the order of
                           execution
       execute             prepare and execute a zuul jobs


And here is an example execution:

.. code-block:: console

   $ pip install --user zuul
   $ zuul-runner --api https://zuul.openstack.org --project openstack/nova --job tempest-full-py3 execute
   [...]
   2019-05-07 06:08:01,040 DEBUG zuul.Runner - Ansible output: b'PLAY RECAP *********************************************************************'
   2019-05-07 06:08:01,040 DEBUG zuul.Runner - Ansible output: b'instance-ip                : ok=9    changed=5    unreachable=0    failed=0'
   2019-05-07 06:08:01,040 DEBUG zuul.Runner - Ansible output: b'localhost                  : ok=12   changed=9    unreachable=0    failed=0'
   2019-05-07 06:08:01,040 DEBUG zuul.Runner - Ansible output: b''
   2019-05-07 06:08:01,218 DEBUG zuul.Runner - Ansible output terminated
   2019-05-07 06:08:01,219 DEBUG zuul.Runner - Ansible cpu times: user=0.00, system=0.00, children_user=0.00, children_system=0.00
   2019-05-07 06:08:01,219 DEBUG zuul.Runner - Ansible exit code: 0
   2019-05-07 06:08:01,219 DEBUG zuul.Runner - Stopped disk job killer
   2019-05-07 06:08:01,220 DEBUG zuul.Runner - Ansible complete, result RESULT_NORMAL code 0
   2019-05-07 06:08:01,220 DEBUG zuul.ExecutorServer - Sent SIGTERM to SSH Agent, {'SSH_AUTH_SOCK': '/tmp/ssh-SYKgxg36XMBa/agent.18274', 'SSH_AGENT_PID': '18275'}
   SUCCESS
