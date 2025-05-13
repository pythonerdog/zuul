Tracing
=======

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

It can be difficult for a user to understand what steps were involved
between a trigger event (such as a patchset upload or recheck comment)
and a buildset report.  If it took an unusually long time it can be
difficult to determine why.  At present, an operator would need to
examine logs to determine what steps were involved and the sources of
any potential delays.  Even experienced operators and developers can
take quite some time to first collect and then analyze logs to answer
these questions.

Sometimes these answers may point to routine system operation (such as
a delay caused by many gate resets, or preparing a large number of
repositories).  Other times they may point to deficiencies in the
system (insufficient mergers) or bugs in the code.

Being able to visualize the activities of a Zuul system can help
operators (and potentially users) triage and diagnose issues more
quickly and accurately.  Even if examining logs is ultimately required
in order to fully diagnose an issue, being able to narrow down the
scope using analsys tools can greatly simplify the process.

Proposed Solution
-----------------

Implementing distributed tracing in Zuul can help improve the
observability of the system and aid operators and potentially users in
understanding the sequence of events.

By exporting information about the processing Zuul performs using the
OpenTelemetry API, information about Zuul operations can be collected
in any of several tools for analysis.

OpenTelemetry is an Open Source protocol for exchanging observability
data, an SDK implementing that protocol, as well as an implementation
of a collector for distributing information to multiple backends.

It supports three kinds of observability data: `traces`, `metrics`,
and `logs`.  Since Zuul already has support for metrics and logs, this
specification proposes that we use only the support in OpenTelemtry
for `traces`.

Usage Scenarios
~~~~~~~~~~~~~~~

Usage of OpenTelemetry should be entirely optional and supplementary
for any Zuul deployment.  Log messages alone should continue to be
sufficient to analyze any potential problem.

Should a deployer wish to use OpenTelemetry tracing data, a very
simple deployment for smaller sites may be constructed by running only
Jaeger.  Jaeger is a service that can receive, store, and display
tracing information.  The project distributes an all-in-one container
image which can store data in local filesystem storage.

https://www.jaegertracing.io/

Larger sites may wish to run multiple collectors and feed data to
larger, distributed storage backends (such as Cassandra,
Elasticsearch, etc).

Suitability to Zuul
~~~~~~~~~~~~~~~~~~~

OpenTelemetry tracing, at a high level, is designed to record
information about events, their timing, and their relation to other
events.  At first this seems like a natural fit for Zuul, which reacts
to events, processes events, and generates more events.  However,
OpenTelemetry's bias toward small and simple web applications is
evident throughout its documentation and the SDK implementation.

  Traces give us the big picture of what happens when a request is
  made by user or an application.

Zuul is not driven by user or application requests, and a system
designed to record several millisecond-long events which make up the
internal response to a user request of a web app is not necessarily
the obvious right choice for recording sequences and combinations of
events which frequently take hours (and sometimes days) to play out
across multiple systems.

Fortunately, the concepts and protocol implementation of OpenTelemtry
are sufficiently well-designed for the general case to be able to
accomodate a system like Zuul, even if the SDK makes incompatible
assumptions that make integration difficult.  There are some
challenges to implementation, but because the concepts appear to be
well matched, we should proceed with using the OpenTelemetry protocol
and SDK.

Spans
~~~~~

The key tracing concepts in OpenTelemety are `traces` and `spans`.
From a data model perspective, the unit of data storage is a `span`.
A trace itself is really just a unique ID that is common to multiple
spans.

Spans can relate to other spans as either children or links.  A trace
is generally considered to have a single 'root' span, and within the
time period represented by that span, it may have any number of child
spans (which may further have their own child spans).

OpenTelemetry anticipates that a span on one system may spawn a child
span on another system and includes facilities for transferring enough
information about the parent span to a child system that the child
system alone can emit traces for its span and any children that it
spawns in turn.

For a concrete example in Zuul, we might have a Zuul scheduler start a
span for a buildset, and then a merger might emit a child span for
performing the initial merge, and an executor might emit a child span
for executing a build.

Spans can relate to other spans (including spans in other traces), so
sequences of events can be chained together without necessitating that
they all be part of the same span or trace.

Because Zuul processes series of events which may stretch for long
periods of time, we should specify what events and actions should
correspond to spans and traces.  Spans can have arbitrary metadat
associated with them, so we will be able to search by event or job
ids.

The following sections describe traces and their child spans.

Event Ingestion
+++++++++++++++

A trace will begin when Zuul receives an event and end when that event
has been enqueued into scheduler queues (or discarded).  A driver
completing processing of an event is a definitive point in time so it
is easy to know when to close the root span for that event's trace
(whereas if we kept the trace open to include scheduler processing, we
would need to know when the last trigger event spawned by the
connection event was complete).

This may include processing in internal queues by a given driver, and
these processing steps/queues should appear as their own child spans.
The spans should include event IDs (and potentially other information
about the event such as change or pull request numbers) as metadata.

Tenant Event Processing
+++++++++++++++++++++++

A trace will begin when a scheduler begins processing a tenant event
and ends when it has forwarded the event to all pipelines within a
tenant.  It will link to the event ingestion trace as a follow-on
span.

Queue Item
++++++++++

A trace will begin when an item is enqueued and end when it is
dequeued.  This will be quite a long trace (hours or days).  It is
expected to be the primary benefit of this telemetry effort as it will
show the entire lifetime of a queue item.  It will link to the tenant
event processing trace as a follow-on span.

Within the root span, there will be a span for each buildset (so that
if a gate reset happens and a new buildset is created, users will see
a series of buildset spans).  Within a buildset, there will be spans
for all of the major processing steps, such as merge operations,
layout calculating, freezing the job graph, and freezing jobs.  Each
build will also merit a span (retried builds will get their own spans
as well), and within a job span, there will be child spans for git
repo prep, job setup, individual playbooks, and cleanup.

SDK Challenges
~~~~~~~~~~~~~~

As a high-level concept, the idea of spans for each of these
operations makes sense.  In practice, the SDK makes implementation
challenging.

The OpenTelemtry SDK makes no provision for beginning a span on one
system and ending it on another, so the fact that one Zuul scheduler
might start a buildset span while another ends it is problematic.

Fortunately, the OpenTelemetry API only reports spans when they end,
not when they start.  This means that we don't need to coordinate a
"start" API call on one scheduler with an "end" API call on another.
We can simply emit the trace with its root span at the end.  However,
any child spans emitted during that time need to know the trace ID
they should use, which means that we at least need to store a trace ID
and start timestamp on our starting scheduler for use by any child
spans as well as the "end span" API call.

The SDK does not support creating a span with a specific trace ID or
start timestamp (most timestamps are automatic), but it has
well-defined interfaces for spans and we can subclass the
implementation to allow us to specify trace IDs and timestamps.  With
this approach, we can "virtually" start a span on one host, store its
information in ZooKeeper with whatever long-lived object it is
associated with (such as a QueueItem) and then make it concrete on
another host when we end it.

Alternatives
++++++++++++

This section describes some alternative ideas for dealing with the
SDK's mismatch with Zuul concepts as well as why they weren't
selected.

* Multiple root spans with the same trace ID

  Jaeger handles this relatively well, and the timeline view appears
  as expected (multiple events with whitespace between them).  The
  graph view in Jaeger may have some trouble displaying this.

  It is not clear that OpenTelemetry anticipates having multiple
  "root" spans, so it may be best to avoid this in order to avoid
  potential problems with other tools.

* Child spans without a parent

  If we emit spans that specify a parent which does not exist, Jaeger
  will display these traces but show a warning that the parent is
  invalid.  This may occur naturally while the system is operating
  (builds complete while a buildset is running), but should be
  eventually corrected once an item is dequeued.  In case of a serious
  error, we may never close a parent span, which would cause this to
  persist.  We should accept that this may happen, but try to avoid it
  happening intentionally.

Links
~~~~~

Links between spans are fairly primitive in Jaeger.  While the
OpenTelemetry API includes attributes for links (so that when we link
a queue item to an event, we could specify that it was a forwarded
event), Jaeger does not store or render them.  Instead, we are only
left with a reference to a ``< span in another trace >`` with a
reference type of ``FOLLOWS_FROM``.  Clicking on that link will
immediately navigate to the other trace where metadata about the trace
will be visible, but before clicking on it, users will have little
idea of what awaits on the other side.

For this reason, we should use span links sparingly so that when they
are encountered, users are likely to intuit what they are for and are
not overwhelmed by multiple indistinguishable links.

Events and Exceptions
~~~~~~~~~~~~~~~~~~~~~

OpenTelemetry allows events to be added to spans.  Events have their
own timestamp and attributes.  These can be used to add additional
context to spans (representing single points in time rather than
events with duration that should be child spans).  Examples might
include receiving a request to cancel a job or dequeue an item.

Events should not be used as an alternative to logs, nor should all
log messages be copied as events.  Events should be used sparingly to
avoid overwhelming the tracing storage with data and the user with
information.

Exceptions may also be included in spans.  This happens automatically
and by default when using the context managers supplied by the SDK.
Because many spans in Zuul will be unable to use the SDK context
managers and any exception information would need to be explicitly
handled and stored in ZooKeeper, we will disable inclusion of
exception information in spans.  This will provide a more consistent
experience (so that users don't see the absence of an exception in
tracing information to indicate the absence of an error in logs) and
reduce the cost of supporting traces (extra storage in ZooKeeper and
in the telemetry storage).

If we decide that exception information is worth including in the
future, this decision will be easy to revisit and reverse.

Sensitive Information
~~~~~~~~~~~~~~~~~~~~~

No sensitive information (secrets, passwords, job variables, etc)
should be included in tracing output.  All output should be suitable
for an audience of Zuul users (that is, if someone has access to the
Zuul dashboard, then tracing data should not have any more sensitive
information than they already have access to).  For public-facing Zuul
systems (such as OpenDev), the information should be suitable for
public use.

Protobuf and gRPC
~~~~~~~~~~~~~~~~~

The most efficient and straightforward method of transmitting data
from Zuul to a collector (including Jaeger) is using OTLP with gRPC
(OpenTelemetry Protocol + gRPC Remote Procedure Calls).  Because
Protobuf applications include automatically generated code, we may
encounter the occasional version inconsistency.  We may need to
navigate package requirements more than normal due to this (especially
if we have multiple packages that depend on protobuf).

For a contemporary example, the OpenTelemetry project is in the
process of pinning to an older version of protobuf:

https://github.com/open-telemetry/opentelemetry-python/issues/2717

There is an HTTP+JSON exporter as well, so in the case that something
goes very wrong with protobuf+gRPC, that may be available as a fallback.

Work Items
----------

* Add OpenTelemetry SDK and support for configuring an exporter to
  zuul.conf
* Implement SDK subclasses to support opening and closing spans on
  different hosts
* Instrument event processing in each driver
* Instrument event processing in scheduler
* Instrument queue items and related spans
* Document a simple Jaeger setup as a quickstart add-on (similar to
  authz)
* Optional: work with OpenDev to run a public Jaeger server for
  OpenDev

The last item is not required for this specification (and not our
choice as Zuul developers to make) but it would be nice if there were
one available so that all Zuul users and developers have a reference
implementation available for community collaboration.
