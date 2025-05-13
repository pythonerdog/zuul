================================================
Enhanced regional distribution of zuul-executors
================================================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

Problem description
===================

When running large distributed deployments it can be desirable to keep traffic
as local as possible. To facilitate this zuul supports zoning of zuul-executors.
Using zones executors only process jobs on nodes that are running in the same
zone. This works well in many cases. However there is currently a limitation
around live log streaming that makes it impossible to use this feature in
certain environments.

Live log streaming via zuul-web or zuul-fingergw requires that each executor
is directly addressable from zuul-web or zuul-fingergw. This is not the case
if

* zuul-executors are behind a NAT. In this case one would need to create a NAT
  rule per executor on different ports which can become a maintenance nightmare.

* zuul-executors run in a different Kubernetes or OpenShift. In this case one
  would need a Ingress/Route or NodePort per executor which also makes
  maintenance really hard.

Proposed change
---------------

In both use cases it would be desirable to have one service in each zone that
can further dispatch log streams within its own zone. Addressing a single
service is much more feasable by e.g. a single NAT rule or a Route or NodePort
service in Kubernetes.

.. graphviz::
   :align: center

    graph {
        graph [fontsize=10 fontname="Verdana"];
        node [fontsize=10 fontname="Verdana"];

        user [ label="User" ];

        subgraph cluster_1 {
            node [style=filled];
            label = "Zone 1";
            web [ label="Web" ];
            executor_1 [ label="Executor 1" ];
        }

        subgraph cluster_2 {
            node [style=filled];
            label = "Zone 2";
            route [ label="Route/Ingress/NAT" ]
            fingergw_zone2 [ label="Fingergw Zone 2"];
            executor_2 [ label="Executor 2" ];
            executor_3 [ label="Executor 3" ];
        }

      user -- web [ constraint=false ];

      web -- executor_1

      web -- route [ constraint=false ]
      route -- fingergw_zone2
      fingergw_zone2 -- executor_2
      fingergw_zone2 -- executor_3

    }

Current log streaming is essentially the same for zuul-web and zuul-fingergw and
works like this:

* Fingergw gets stream request by user
* Fingergw resolves stream address by calling get_job_log_stream_address and
  supplying a build uuid
* Scheduler responds with the executor hostname and port on which the build
  is running.
* Fingergw connects to the stream address, supplies the build uuid and connects
  the streams.

The proposed process is almost the same:

* Fingergw gets stream request by user
* Fingergw resolves stream address by calling get_job_log_stream_address and
  supplying the build uuid *and the zone of the fingergw (optional)*
* Scheduler responds:

   * Address of executor if the zone provided with the request matches the zone
     of the executor running the build, or the executor is un-zoned.
   * Address of fingergw in the target zone otherwise.

* Fingergw connects to the stream address, supplies the build uuid and connects
  the streams.

In case the build runs in a different zone the fingergw in the target zone will
follow the exact same process and get the executor stream process as this will
be in the same zone.


In order to facilitate this the following changes need to be made:

* The fingergw registers itself in the zk component registry and offers its
  hostname, port and optionally zone. The hostname further needs to be
  configurable like it is for the executors.

* Zuul-web and fingergw need a new optional config parameter containing their
  zone.

While zuul-web and zuul-fingergw will be aware of what zone they are running in,
end-users will not need this information; the user-facing instances of those
services will continue to serve the entirely of the Zuul system regardless of
which zone they reside in, all from a single public URL or address.


Gearman
-------

The easiest and most standard way of getting non-http traffic into a
Kubernetes/Openshift cluster is using Ingres/Routes in combination with TLS and
SNI (server name indication). SNI is used in this case for dispatching the
connection to the correct service. Gearman currently doesn't support SNI which
makes it harder to route it into an Kubernetes/Openshift cluster from outside.


Security considerations
-----------------------

Live log streams can potentially contain sensitive data. Especially when
transferring them between different datacenters encryption would be useful.
So we should support optionally encrypting the finger streams using TLS with
optional client auth like we do with gearman. The mechanism should also support
SNI (Server name indication).

