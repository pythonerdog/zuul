.. _pragma:

Pragma
======

The `pragma` item does not behave like the others.  It can not be
included or excluded from configuration loading by the administrator,
and does not form part of the final configuration itself.  It is used
to alter how the configuration is processed while loading.

A pragma item only affects the current file.  The same file in another
branch of the same project will not be affected, nor any other files
or any other projects.  The effect is global within that file --
pragma directives may not be set and then unset within the same file.

.. code-block:: yaml

   - pragma:
       implied-branch-matchers: False

.. attr:: pragma

   The pragma item currently supports the following attributes:

   .. attr:: implied-branch-matchers

      This is a boolean, which, if set, may be used to enable
      (``true``) or disable (``false``) the addition of implied branch
      matchers to job and project-template definitions.  Normally Zuul
      decides whether to add these based on heuristics described in
      :attr:`job.branches`.  This attribute overrides that behavior.

      This can be useful if a project has multiple branches, yet the
      jobs defined in the default branch should apply to all branches.

      The behavior may also be configured by a Zuul administrator
      using
      :attr:`tenant.untrusted-projects.<project>.implied-branch-matchers`.
      This pragma overrides that setting if both are present.

      Note that if a job contains an explicit branch matcher, it will
      be used regardless of the value supplied here.

   .. attr:: implied-branches

      This is a list of :ref:`regular expressions <regex>`, just as
      :attr:`job.branches`, which may be used to supply the value of
      the implied branch matcher for all jobs and project-templates in
      a file.

      This may be useful if two projects share jobs but have
      dissimilar branch names.  If, for example, two projects have
      stable maintenance branches with dissimilar names, but both
      should use the same job variants, this directive may be used to
      indicate that all of the jobs defined in the stable branch of
      the first project may also be used for the stable branch of the
      other.  For example:

      .. code-block:: yaml

         - pragma:
             implied-branches:
               - stable/foo
               - stable/bar

      The above code, when added to the ``stable/foo`` branch of a
      project would indicate that the job variants described in that
      file should not only be used for changes to ``stable/foo``, but
      also on changes to ``stable/bar``, which may be in another
      project.

      Note that if a job contains an explicit branch matcher, it will
      be used regardless of the value supplied here.

      If this is used in a branch, it should include that branch name
      or changes on that branch may be ignored.

      Note also that the presence of `implied-branches` does not
      automatically set `implied-branch-matchers`.  Zuul will still
      decide if implied branch matchers are warranted at all, using
      the heuristics described in :attr:`job.branches`, and only use
      the value supplied here if that is the case.  If you want to
      declare specific implied branches on, for example, a
      :term:`config-project` project (which normally would not use
      implied branches), you must set `implied-branch-matchers` as
      well.

