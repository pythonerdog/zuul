=========================
Resource Quota per Tenant
=========================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.


Problem Description
===================

Zuul is inherently built to be tenant scoped and can be operated as a shared CI
system for a large number of more or less independent projects. As such, one of
its goals is to provide each tenant a fair amount of resources.

If Zuul, and more specifically Nodepool, are pooling build nodes from shared
providers (e.g. a limited number of OpenStack clouds) the principle of a fair
resource share across tenants can hardly be met by the Nodepool side. In large
Zuul installations, it is not uncommon that some tenants request far more
resources and at a higher rate from the Nodepool providers than other tenants.
While Zuuls "fair scheduling" mechanism makes sure each queue item gets treated
justly, there is no mechanism to limit allocated resources on a per-tenant
level. This, however, would be useful in different ways.

For one, in a shared pool of computing resources, it can be necessary to
enforce resource budgets allocated to tenants. That is, a tenant shall only be
able to allocate resources within a defined and payed limit. This is not easily
possible at the moment as Nodepool is not inherently tenant-aware. While it can
limit the number of servers, CPU cores, and RAM allocated on a per-pool level,
this does not directly translate to Zuul tenants. Configuring a separate pool
per tenant would not only lead to much more complex Nodepool configurations,
but also induce performance penalties as each pool runs in its own Python
thread.

Also, in scenarios where Zuul and auxiliary services (e.g. GitHub or
Artifactory) are operated near or at their limits, the system can become
unstable. In such a situation, a common measure is to lower Nodepools resource
quota to limit the number of concurrent builds and thereby reduce the load on
Zuul and other involved services. However, this can currently be done only on
a per-provider or per-pool level, most probably affecting all tenants. This
would contradict the principle of fair resource pooling as there might be less
eager tenants that do not, or rather insignificantly, contribute to the overall
high load. It would therefore be more advisable to limit only those tenants'
resources that induce the most load.

Therefore, it is suggested to implement a mechanism in Nodepool that allows to
define and enforce limits of currently allocated resources on a per-tenant
level. This specification describes how resource quota can be enforced in
Nodepool with minimal additional configuration and execution overhead and with
little to no impact on existing Zuul installations. A per-tenant resource limit
is then applied additionally to already existing pool-level limits and treated
globally across all providers.


Proposed Change
===============

The proposed change consists of several parts in both, Zuul and Nodepool. As
Zuul is the only source of truth for tenants, it must pass the name of the
tenant with each NodeRequest to Nodepool. The Nodepool side must consider this
information and adhere to any resource limits configured for the corresponding
tenant. However, this shall be backwards compatible, i.e., if no tenant name is
passed with a NodeRequest, tenant quotas shall be ignored for this request.
Vice versa, if no resource limit is configured for a tenant, the tenant on the
NodeRequest does not add any additional behaviour.

To keep record of currently consumed resources globally, i.e., across all
providers, the number of CPU cores and main memory (RAM) of a Node shall be
stored with its representation in ZooKeeper by Nodepool. This allows for
a cheap and provider agnostic aggregation of the currently consumed resources
per tenant from any provider. The OpenStack driver already stores the resources
in terms of cores, ram, and instances per ``zk.Node`` in a separate property in
ZooKeeper. This is to be expanded to other drivers where applicable (cf.
"Implementation Caveats" below).

Make Nodepool Tenant Aware
--------------------------

1. Add ``tenant`` attribute to ``zk.NodeRequest`` (applies to Zuul and
   Nodepool)
2. Add ``tenant`` attribute to ``zk.Node`` (applies to Nodepool)

Introduce Tenant Quotas in Nodepool
-----------------------------------

1. introduce new top-level config item ``tenant-resource-limits`` for Nodepool
   config

   .. code-block:: yaml

      tenant-resource-limits:
        - tenant-name: tenant1
          max-servers: 10
          max-cores: 200
          max-ram: 800
        - tenant-name: tenant2
          max-servers: 100
          max-cores: 1500
          max-ram: 6000

2. for each node request that has the tenant attribute set and a corresponding
   ``tenant-resource-limits`` config exists

   - get quota information from current active and planned nodes of same tenant
   - if quota for current tenant would be exceeded

     - defer node request
     - do not pause the pool (as opposed to exceeded pool quota)
     - leave the node request unfulfilled (REQUESTED state)
     - return from handler for another iteration to fulfill request when tenant
       quota allows eventually

   - if quota for current tenant would not be exceeded

     - proceed with normal process

3. for each node request that does not have the tenant attribute or a tenant
   for which no ``tenant-resource-limits`` config exists

   - do not calculate the per-tenant quota and proceed with normal process

Implementation Caveats
----------------------

This implementation is ought to be driver agnostic and therefore not to be
implemented separately for each Nodepool driver. For the Kubernetes, OpenShift,
and Static drivers, however, it is not easily possible to find the current
allocated resources. The proposed change therefore does not currently apply to
these. The Kubernetes and OpenShift(Pods) drivers would need to enforce
resource request attributes on their labels which are optional at the moment
(cf. `Kubernetes Driver Doc`_). Another option would be to enforce resource
limits on a per Kubernetes namespace level. How such limits can be implemented
in this case needs to be addressed separately. Similarly, the AWS, Azure, and
GCE drivers do not fully implement quota information for their nodes. E.g. the
AWS driver only considers the number of servers, not the number of cores or
RAM. Therefore, nodes from these providers also cannot be fully taken into
account when calculating a global resource limit besides of number of servers.
Implementing full quota support in those drivers is not within the scope of
this change. However, following this spec, implementing quota support there to
support a per-tenant limit would be straight forward. It just requires them to
set the corresponding ``zk.Node.resources`` attributes. As for now, only the
OpenStack driver exports resource information about its nodes to ZooKeeper, but
as other drivers get enhanced with this feature, they will inherently be
considered for such global limits as well.

In the `QuotaSupport`_ mixin class, we already query ZooKeeper for the used and
planned resources. Ideally, we can extend this method to also return the
resources currently allocated by each tenant without additional costs and
account for this additional quota information as we already do for provider and
pool quotas (cf. `SimpleTaskManagerHandler`_). However, calculation of
currently consumed resources by a provider is done only for nodes of the same
provider. This does not easily work for global limits as intended for tenant
quotas. Therefore, this information (``cores``, ``ram``, ``instances``) will be
stored in a generic way on ``zk.Node.resources`` objects for any provider to
evaluate these quotas upon an incoming node request.


.. _`Kubernetes Driver Doc`: https://zuul-ci.org/docs/nodepool/kubernetes.html#attr-providers.[kubernetes].pools.labels.cpu
.. _`QuotaSupport`: https://opendev.org/zuul/nodepool/src/branch/master/nodepool/driver/utils.py#L180
.. _`SimpleTaskManagerHandler`: https://opendev.org/zuul/nodepool/src/branch/master/nodepool/driver/simple.py#L218
