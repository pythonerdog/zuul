:title: Elasticsearch Driver

Elasticsearch
=============

The Elasticsearch driver supports reporters only. The purpose of the driver is
to export build and buildset results to an Elasticsearch index.

If the index does not exist in Elasticsearch then the driver will create it
with an appropriate mapping for static fields.

The driver can add job's variables and any data returned to Zuul
via zuul_return respectively into the `job_vars` and `job_returned_vars` fields
of the exported build doc. Elasticsearch will apply a dynamic data type
detection for those fields.

Elasticsearch supports a number of different datatypes for the fields in a
document. Please refer to its `documentation`_.

The Elasticsearch reporter uses new ES client, that is only supporting
`current version`_ of Elastisearch. In that case the
reporter  has been tested on ES cluster version 7. Lower version may
be working, but we can not give tu any guarantee of that.


.. _documentation: https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-types.html
.. _current version: https://www.elastic.co/support/eol

Connection Configuration
------------------------

The connection options for the Elasticsearch driver are:

.. attr:: <Elasticsearch connection>

   .. attr:: driver
      :required:

      .. value:: elasticsearch

         The connection must set ``driver=elasticsearch``.

   .. attr:: uri
      :required:

      Database connection information in the form of a comma separated
      list of ``host:port``. The information can also include protocol (http/https)
      or username and password required to authenticate to the Elasticsearch.

      Example:

        uri=elasticsearch1.domain:9200,elasticsearch2.domain:9200

      or

        uri=https://user:password@elasticsearch:9200

      where user and password is optional.

   .. attr:: use_ssl
      :default: true

      Turn on SSL. This option is not required, if you set ``https`` in
      uri param.

   .. attr:: verify_certs
      :default: true

      Make sure we verify SSL certificates.

   .. attr:: ca_certs
      :default: ''

      Path to CA certs on disk.

   .. attr:: client_cert
      :default: ''

      Path to the PEM formatted SSL client certificate.

   .. attr:: client_key
      :default: ''

      Path to the PEM formatted SSL client key.


Example of driver configuration:

.. code-block:: text

    [connection elasticsearch]
    driver=elasticsearch
    uri=https://managesf.sftests.com:9200


Additional parameters to authenticate to the Elasticsearch server you
can find in `client`_ class.


.. _client: https://github.com/elastic/elasticsearch-py/blob/master/elasticsearch/client/__init__.py

Reporter Configuration
----------------------

This reporter is used to store build results in an Elasticsearch index.

The Elasticsearch reporter does nothing on :attr:`pipeline.start` or
:attr:`pipeline.merge-conflict`; it only acts on
:attr:`pipeline.success` or :attr:`pipeline.failure` reporting stages.

.. attr:: pipeline.<reporter>.<elasticsearch source>

   The reporter supports the following attributes:

   .. attr:: index
      :default: zuul

      The Elasticsearch index to be used to index the data. To prevent
      any name collisions between Zuul tenants, the tenant name is used as index
      name prefix. The real index name will be:

      .. code-block::

         <index-name>.<tenant-name>-<YYYY>.<MM>.<DD>

      The index will be created if it does not exist.

   .. attr:: index-vars
      :default: false

      Boolean value that determines if the reporter should add job's vars
      to the exported build doc.
      NOTE: The index-vars is not including the secrets.

   .. attr:: index-returned-vars
      :default: false

      Boolean value that determines if the reporter should add zuul_returned
      vars to the exported build doc.


For example:

.. code-block:: yaml

   - pipeline:
       name: check
       success:
         elasticsearch:
           index: 'zuul-index'
