Configure a swap partition

This role has been copied from openstack/openstack-zuul-jobs. The role
doesn't make much sense in zuul/zuul-jobs because it makes assumptions
about the runtime environments (like rax's epehemeral disk drives). Since
openstack-zuul-jobs is in another Zuul tenant we port it over to zuul where
we want to make use of it.

Creates a swap partition on the ephemeral block device (the rest of which
will be mounted on /opt).

**Role Variables**

.. zuul:rolevar:: configure_swap_size
   :default: 1024

   The size of the swap partition, in MiB.
