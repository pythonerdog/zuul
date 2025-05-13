.. _howto-zookeeper:

ZooKeeper Administration
========================

This section will cover some basic tasks and recommendations when
setting up ZooKeeper for use with Zuul.  A complete tutorial for
ZooKeeper is out of scope for this documentation.

Configuration
-------------

The following general configuration setting in
``/etc/zookeeper/zoo.cfg`` is recommended:

.. code-block::

   autopurge.purgeInterval=6

This instructs ZooKeeper to purge old snapshots every 6 hours.  This
will avoid filling the disk.

.. _zk-encrypted-connections:

Encrypted Connections
---------------------

Zuul requires its connections to ZooKeeper are TLS encrypted.
ZooKeeper version 3.5.1 or greater is required for TLS support.
ZooKeeper performs hostname validation for all ZooKeeper servers
("quorum members"), therefore each member of the ZooKeeper cluster
should have its own certificate.  This does not apply to clients which
may share a certificate.

ZooKeeper performs certificate validation on all connections (server
and client).  If you use a private Certificate Authority (CA) (which
is generally recommended and discussed below), then these TLS
certificates not only serve to encrypt traffic, but also to
authenticate and authorize clients to the cluster.  Only clients with
certificates authorized by a CA explicitly trusted by your ZooKeeper
installation will be able to connect.

.. note:: The instructions below direct you to sign certificates with
          a CA that you create specifically for Zuul's ZooKeeper
          cluster.  If you use a CA you share with other users in your
          organization, any certificate signed by that CA will be able
          to connect to your ZooKeeper cluster.  In this case, you may
          need to take additional steps such as network isolation to
          protect your ZooKeeper cluster.  These are beyond the scope
          of this document.

The ``tools/zk-ca.sh`` script in the Zuul source code repository can
be used to quickly and easily generate self-signed certificates for
all ZooKeeper cluster members and clients.

Make a directory for it to store the certificates and CA data, and run
it once for each client:

.. code-block::

   mkdir /etc/zookeeper/ca
   tools/zk-ca.sh /etc/zookeeper/ca zookeeper1.example.com
   tools/zk-ca.sh /etc/zookeeper/ca zookeeper2.example.com
   tools/zk-ca.sh /etc/zookeeper/ca zookeeper3.example.com

Add the following to ``/etc/zookeeper/zoo.cfg``:

.. code-block::

   # Necessary for TLS support
   serverCnxnFactory=org.apache.zookeeper.server.NettyServerCnxnFactory

   # Client TLS configuration
   secureClientPort=2281
   ssl.keyStore.location=/etc/zookeeper/ca/keystores/zookeeper1.example.com.pem
   ssl.trustStore.location=/etc/zookeeper/ca/certs/cacert.pem

   # Server TLS configuration
   sslQuorum=true
   ssl.quorum.keyStore.location=/etc/zookeeper/ca/keystores/zookeeper1.example.com.pem
   ssl.quorum.trustStore.location=/etc/zookeeper/ca/certs/cacert.pem

Change the name of the certificate filenames as appropriate for the
host (e.g., ``zookeeper1.example.com.pem``).

In order to disable plaintext connections, ensure that the
``clientPort`` option does not appear in ``zoo.cfg``.  Use the new
method of specifying Zookeeper quorum servers, which looks like this:

.. code-block::

   server.1=zookeeper1.example.com:2888:3888
   server.2=zookeeper2.example.com:2888:3888
   server.3=zookeeper3.example.com:2888:3888

This format normally includes ``;2181`` at the end of each line,
signifying that the server should listen on port 2181 for plaintext
client connections (this is equivalent to the ``clientPort`` option).
Omit it to disable plaintext connections.  The earlier addition of
``secureClientPort`` to the config file instructs ZooKeeper to listen
for encrypted connections on port 2281.

Be sure to specify port 2281 rather than the standard 2181 in the
:attr:`zookeeper.hosts` setting in ``zuul.conf``.

Finally, add the :attr:`zookeeper.tls_cert`,
:attr:`zookeeper.tls_key`, and :attr:`zookeeper.tls_ca` options.  Your
``zuul.conf`` file should look like:

.. code-block::

   [zookeeper]
   hosts=zookeeper1.example.com:2281,zookeeper2.example.com:2281,zookeeper3.example.com:2281
   tls_cert=/etc/zookeeper/ca/certs/client.pem
   tls_key=/etc/zookeeper/ca/keys/clientkey.pem
   tls_ca=/etc/zookeeper/ca/certs/cacert.pem
