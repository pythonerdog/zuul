:title: About Zuul

.. _about-zuul:

About Zuul
==========

Zuul is a Project Gating System.  That's like a CI or CD system, but
the focus is on testing the future state of code repositories.

A gating system doesn't just test a proposed change; it tests the
proposed future state of multiple branches and repositories with any
number of in-flight changes and their dependencies.  And the same
playbooks used to test software can also be used to deploy it.

Zuul itself is a service which listens to events from various code
review systems, executes jobs based on those events, and reports the
results back to the code review system.  The primary interface for
Zuul is the code review system (or systems) so that it fits seamlessly
into developer workflows, and a web interface is available for
inspecting the current status and browsing build results.

The best way to run Zuul is with a single installation serving as many
projects or groups as possible.  It is a multi-tenant application that
is able to provide as much or as little separation between projects as
desired.

Zuul works with a wide range of code review systems, and can work with
multiple systems (including integrating projects on different systems)
simultaneously.  See :ref:`drivers` for a complete list.

Zuul uses a separate component called `Nodepool`_ to provide the
resources to run jobs.  Nodepool works with several cloud providers
as well as statically defined nodes (again, simultaneously).

Because Zuul is designed from the ground up to run jobs in a
multi-node environment (whether those nodes are bare metal machines,
VMs, Kubernetes clusters, or containers), Zuul's job definition
language needs to support orchestrating tasks on multiple nodes.  Zuul
uses Ansible for this.  Ansible is well-known and easy to learn and
use.  Some existing Ansible playbooks and roles may be able to be used
directly with Zuul (but some restrictions apply, so not all will).

However, knowledge or use of Ansible is not required for Zuul -- it is
quite simple for Zuul's embedded Ansible to run any shell script or
any other program.  Zuul's library of standard jobs even includes a
job that will run a specified shell script, so it's possible to use
Zuul without writing any Ansible at all.

Zuul is an open source project developed and maintained by a community
of users.  We welcome your `support and contribution
<https://zuul-ci.org/community.html>`__.

.. toctree::
   :hidden:

   concepts
   gating

_`Nodepool`: https://zuul-ci.org/docs/nodepool/
