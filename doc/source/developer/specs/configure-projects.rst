Untrusted Multi-Project Configuration
=====================================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

Introduction
------------

There are many ways of combining repositories into larger projects.
Some examples are by using libraries or other individual project
deliverables and combining them at build time; using network services
for multiple running binaries at runtime; or by combining repositories
at the source level using git submodules or repo manifest files.

Zuul does not have native support for any of these systems, but it
does provide facilities like cross-project dependencies and
required-projects settings that facilitate users implementing these
combination methods within Zuul jobs.

One aspect that is currently difficult is the configuration of
multiple projects in the same manner.  Zuul does provide a
`project-template` stanza so that a group of jobs can be applied to
multiple projects with a single definition.  However, applying a
project-template stanza to a project still needs to happen either
within the project itself, or a config-project.  This means that
adding a project to (or removing a project from) a set of projects
that make up a super-project can involve multiple changes.

This can be simplified if we (conditionally) relax the restriction on
untrusted-projects configuring other projects.

Example
-------

Before we examine the proposed change, let's consider an example as
things stand today: A superproject (which contains a .gitmodules file,
or a repo-tool manifest.xml file) which references multiple
subprojects.  Within the superproject, a Zuul `project-template` is
defined which lists the jobs that should run on every project in the
group.  Each subproject contains a simple `project` stanza that
references that `project-template`

To add a new project to that set requires the following changes:

* Add the subproject to the tenant config file
* Add the subproject to the project-template in the superproject repo
* Add a project stanza to the new subproject repo

An alternative approach would be to use a config-project to define
the project stanzas for each subproject.  With this approach, changes
to the set of projects are not self-testing, so it is not quite as
attractive.

If the subprojects happen to be named in such a way that they can be
exclusively identified using a regular expression, then it would be
simple to add a project stanza in a config-project that includes all
current and future subprojects.  But it would be difficult to remove a
project from that set, and moreover, this approach requires some
foresight in naming repositories that we can not assume will always
happen.

Proposed Change
---------------

If we allow certain untrusted-projects to specify project stanzas on
certain other untrusted-projects, then we can reduce the above to two
changes:

* Add the subproject to the tenant config file
* Add the subproject to the project-template in the superproject repo
  and also add it to the list of projects that use that template

The second step can happen in one change.

The syntax for configuring the tenant configuration file is proposed
as:

.. code-block:: yaml

   - tenant:
       name: example
       source:
         gerrit:
           config-projects:
             - project-config
           untrusted-projects:
             - superproject:
                 configure-projects:
                   - submodule1
                   - othermodule
                   - ^submodules/.*$
             - submodule1
             - othermodule
             - submodules/foo

The syntax includes a list of project names for which the superproject
is allowed to include `project` stanzas.  This list may be literal
project names or regular expressions which are matched against project
names.  If the list includes ``^.*$`` as a single regular expression,
then the superproject has permission to write project stanzas for any
project.

The syntax for configuring other projects within the superproject will
be the same as it is today when the same is done within a
config-project.  For example:

.. code-block:: yaml

   - project:
       name: submodule1
       templates: [submodule-jobs]
   - project:
       name: othermodule
       templates: [submodule-jobs]
   - project:
       name: ^submodules/.*$
       templates: [submodule-jobs]


The `project` stanzas themselves currently have the ability to specify
a regular expression as a project name (as in the third example
above).  This will still apply in this case.  When applying the regex
in the `project` stanza to gather the list of repositories to which it
should apply, we will verify that each of those projects is within the
set of projects allowed by the tenant configuration.

All regular expressions will be re2-style regular expressions.

Any config-projects listed under ``configure-projects`` on an
untrusted-project will be ignored.  An untrusted-project is not
permitted to declare a project stanza that matches a config-project.
If an untrusted-project includes a project stanza that matches a
config-project, that will manifest a tenant configuration error and
the stanza will be disregarded.

Branches
--------

The current behavior of `project` stanzas is that if the project that
contains the definition has a single branch, it is considered a
branchless project and the `project` stanza will apply to all branches
of its project.  If the project containing the `project` stanza is
branched, then the `project` stanza will acquire an implied branch
matcher based on the branch of the project containing the definition.

Since the only configuration of external projects today is in a
config-project which is always considered branchless, this means that
all external project configurations are branchless.

By allowing `project` stanzas in untrusted-projects we will be
permitting the creation of `project` stanzas with implied branch
matchers based on the branch of the superproject where they are
defined.  This will likely be an acceptable and expected behavior most
of the time (the ``dev`` branch of a superproject will define
`project` stanzas for the ``dev`` branch of its subprojects).

However, to facilitate the case where more control is needed (such as
a superproject configuring a subproject where development is on
``main`` instead of ``dev``), we will do two things:

* Allow `project` stanzas for external projects (i.e., not the current
  project) to acquire implied branch matchers from pragmas.  That way
  if a user configures a file with the `implied-branches` set up
  correctly for a system (e.g, ``implied-branches: [dev, main]``) then
  the external projects will automatically follow that system.

* Add a ``branches`` attribute to `project` stanzas.  This will allow
  any project stanza (whether its configuring the current project or
  an external project) to specify an explicit branch matcher, just
  like jobs.

Example:

.. code-block:: yaml

   - project:
       name: submodule1
       branches: dev
       templates: [submodule-jobs]

Alternatives
------------

This proposal deals with supporting use cases related to superprojects
and subprojects, but does not include any functionality to explicitly
support that behavior.  The ability to configure other projects is
potentially useful outside of that use case (including, but not
limited to, the examples in the introduction).  If, in the future,
native support for superprojects is added to Zuul, this work may be
forward-compatible with that inasmuch as it will support part of the
configuration needed for such a system.  But it is not intended to
implement native superproject support either on its own, nor should it
be seen as a first step.

Work Items
----------

This should be a single change to implement the new behavior, along
with tests and documentation.
