Jaeger Tracing Tutorial
=======================

Zuul includes support for `distributed tracing`_ as described by the
OpenTelemetry project.  This allows operators (and potentially users)
to visualize the progress of events and queue items through the
various Zuul components as an aid to debugging.

Zuul supports the OpenTelemetry Protocol (OTLP) for exporting traces.
Many observability systems support receiving traces via OTLP.  One of
these is Jaeger.  Because it can be run as a standalone service with
local storage, this tutorial describes how to set up a Jaeger server
and configure Zuul to export data to it.

For more information about tracing in Zuul, see :ref:`tracing`.

To get started, first run the :ref:`quick-start` and then follow the
steps in this tutorial to add a Jaeger server.

Restart Zuul Containers
-----------------------

After completing the initial tutorial, stop the Zuul containers so
that we can update Zuul's configuration to enable tracing.

.. code-block:: shell

   cd zuul/doc/source/examples
   podman-compose -p zuul-tutorial stop

Restart the containers with a new Zuul configuration.

.. code-block:: shell

   cd zuul/doc/source/examples
   ZUUL_TUTORIAL_CONFIG="./tracing/etc_zuul/" podman-compose -p zuul-tutorial up -d

This tells podman-compose to use these Zuul `config files
<https://opendev.org/zuul/zuul/src/branch/master/doc/source/examples/tracing>`_.
The only change compared to the quick-start is to add a
:attr:`tracing` section to ``zuul.conf``:

.. code-block:: ini

   [tracing]
   enabled=true
   endpoint=jaeger:4317
   insecure=true

This instructs Zuul to send tracing information to the Jaeger server
we will start below.

Start Jaeger
------------

A separate docker-compose file is provided to run Jaeger.  Start it
with this command:

.. code-block:: shell

   cd zuul/doc/source/examples/tracing
   podman-compose -p zuul-tutorial-tracing up -d

You can visit http://localhost:16686/search to verify it is running.

Recheck a change
----------------

Visit Gerrit at http://localhost:8080/dashboard/self and return to the
``test1`` change you uploaded earlier.  Click `Reply` then type
`recheck` into the text field and click `Send`.  This will tell Zuul
to run the test job once again.  When the job is complete, you should
have a trace available in Jaeger.

To see the trace, visit http://localhost:16686/search and select the
`zuul` service (reload the page if it doesn't show up at first).
Press `Find Traces` and you should see the trace for your build
appear.

_`distributed tracing`: https://opentelemetry.io/docs/concepts/observability-primer/#distributed-traces
