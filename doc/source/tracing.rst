:title: Tracing

.. _tracing:

Tracing
=======

Zuul includes support for `distributed tracing`_ as described by the
OpenTelemetry project.  This allows operators (and potentially users)
to visualize the progress of events and queue items through the
various Zuul components as an aid to debugging.

OpenTelemetry defines several observability signals such as traces,
metrics, and logs.  Zuul uses other systems for metrics and logs; only
traces are exported via OpenTelemetry.

Zuul supports the OpenTelemetry Protocol (OTLP) for exporting traces.
Many observability systems support receiving traces via OTLP
(including Jaeger tracing).

Configuration
-------------

Related configuration is in the :attr:`tracing` section of ``zuul.conf``.

Tutorial
--------

Here is a tutorial that shows how to enable tracing with Zuul and Jaeger.

.. toctree::
   :maxdepth: 1

   tutorials/tracing

_`distributed tracing`: https://opentelemetry.io/docs/concepts/observability-primer/#distributed-traces
