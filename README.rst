Zuul
====

Zuul is a project gating system.

The latest documentation for the current version of Zuul is published at:
https://zuul-ci.org/docs/zuul/

If you are looking for the Edge routing service named Zuul that is
related to Netflix, it can be found here:
https://github.com/Netflix/zuul

If you are looking for the Javascript testing tool named Zuul, its
archive can be found here:
https://github.com/defunctzombie/zuul

Getting Help
------------

There are two Zuul-related mailing lists:

`zuul-announce <http://lists.zuul-ci.org/cgi-bin/mailman/listinfo/zuul-announce>`_
  A low-traffic announcement-only list to which every Zuul operator or
  power-user should subscribe.

`zuul-discuss <http://lists.zuul-ci.org/cgi-bin/mailman/listinfo/zuul-discuss>`_
  General discussion about Zuul, including questions about how to use
  it, and future development.

You will also find Zuul developers on
`Matrix <https://matrix.to/#/#zuul:opendev.org>`.

Contributing
------------

To browse the latest code, see: https://opendev.org/zuul/zuul
To clone the latest code, use `git clone https://opendev.org/zuul/zuul`

Bugs are handled at: https://storyboard.openstack.org/#!/project/zuul/zuul

Suspected security vulnerabilities are most appreciated if first
reported privately following any of the supported mechanisms
described at https://zuul-ci.org/docs/zuul/latest/vulnerabilities.html

Code reviews are handled by gerrit at https://review.opendev.org

After creating a Gerrit account, use `git review` to submit patches.
Example::

    # Do your commits
    $ git review
    # Enter your username if prompted

`Join us on Matrix <https://matrix.to/#/#zuul:opendev.org>`_ to discuss
development or usage.

License
-------

Zuul is free software.  Most of Zuul is licensed under the Apache
License, version 2.0.  Some parts of Zuul are licensed under the
General Public License, version 3.0.  Please see the license headers
at the tops of individual source files.

Python Version Support
----------------------

Zuul requires Python 3. It does not support Python 2.

Since Zuul uses Ansible to drive CI jobs, Zuul can run tests anywhere
Ansible can, including Python 2 environments.

