============
Testing Zuul
============
------------
A Quickstart
------------

This is designed to be enough information for you to run your first tests on
an Ubuntu 20.04 (or later) host.

*Install pip*::

  sudo apt-get install python3-pip

More information on pip here: http://www.pip-installer.org/en/latest/

*Use pip to install tox*::

  pip install tox

A running zookeeper is required to execute tests, but it also needs to be
configured for TLS and a certificate authority set up to handle socket
authentication. Because of these complexities, it's recommended to use a
helper script to set up these dependencies, as well as a database servers::

  sudo apt-get install docker-compose  # or podman-compose if preferred
  ROOTCMD=sudo tools/test-setup-docker.sh

.. note:: Installing and bulding javascript is not required, but tests that
          depend on the javascript assets having been built will be skipped
          if you don't.

*Install javascript tools*::

  tools/install-js-tools.sh

*Install javascript dependencies*::

  pushd web
  yarn install
  popd

*Build javascript assets*::

  pushd web
  yarn build
  popd

Run The Tests
-------------

*Navigate to the project's root directory and execute*::

  tox

Note: completing this command may take a long time (depends on system resources)
also, you might not see any output until tox is complete.

Information about tox can be found here: http://testrun.org/tox/latest/


Run The Tests in One Environment
--------------------------------

Tox will run your entire test suite in the environments specified in the project tox.ini::

  [tox]

  envlist = <list of available environments>

To run the test suite in just one of the environments in envlist execute::

  tox -e <env>
so for example, *run the test suite in py35*::

  tox -e py35

Run One Test
------------

To run individual tests with tox::

  tox -e <env> -- path.to.module.Class.test

For example, to *run a single Zuul test*::

  tox -e py35 -- tests.unit.test_scheduler.TestScheduler.test_jobs_executed

To *run one test in the foreground* (after previously having run tox
to set up the virtualenv)::

  .tox/py35/bin/stestr run tests.unit.test_scheduler.TestScheduler.test_jobs_executed

List Failing Tests
------------------

  .tox/py35/bin/activate
  stestr failing --list

Hanging Tests
-------------

The following will run each test in turn and print the name of the
test as it is run::

  . .tox/py35/bin/activate
  stestr run

You can compare the output of that to::

  python -m testtools.run discover --list

Need More Info?
---------------

More information about stestr: http://stestr.readthedocs.io/en/latest/
