Kubernetes Operator
===================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

While Zuul can be happily deployed in a Kubernetes environment, it is
a complex enough system that a Kubernetes Operator could provide value
to deployers. A Zuul Operator would allow a deployer to create, manage
and operate "A Zuul" in their Kubernetes and leave the details of how
that works to the Operator.

To that end, the Zuul Project should create and maintain a Kubernetes
Operator for running Zuul. Given the close ties between Zuul and Ansible,
we should use `Ansible Operator`_ to implement the Operator. Our existing
community is already running Zuul in both Kubernetes and OpenShift, so
we should ensure our Operator works in both. When we're happy with it,
we should publish it to `OperatorHub`_.

That's the easy part. The remainder of the document is for hammering out
some of the finer details.

.. _Ansible Operator: https://github.com/operator-framework/operator-sdk/blob/master/doc/ansible/user-guide.md
.. _OperatorHub: https://www.operatorhub.io/

Custom Resource Definitions
---------------------------

One of the key parts of making an Operator is to define one or more
Custom Resource Definition (CRD). These allow a user to say "hey k8s,
please give me a Thing". It is then the Operator's job to take the
appropriate actions to make sure the Thing exists.

For Zuul, there should definitely be a Zuul CRD. It should be namespaced
with ``zuul-ci.org``. There should be a section for each service for
managing service config as well as capacity:

::

  apiVersion: zuul-ci.org/v1alpha1
  kind: Zuul
  spec:
    merger:
      count: 5
    executor:
      count: 5
    web:
      count: 1
    fingergw:
      count: 1
    scheduler:
      count: 1

.. note:: Until the distributed scheduler exists in the underlying Zuul
    implementation, the ``count`` parameter for the scheduler service
    cannot be set to anything greater than 1.

Zuul requires Nodepool to operate. While there are friendly people
using Nodepool without Zuul, from the context of the Operator, the Nodepool
services should just be considered part of Zuul.

::

  apiVersion: zuul-ci.org/v1alpha1
  kind: Zuul
  spec:
    merger:
      count: 5
    executor:
      count: 5
    web:
      count: 1
    fingergw:
      count: 1
    scheduler:
      count: 1
    # Because of nodepool config sharding, count is not valid for launcher.
    launcher:
    builder:
      count: 2


Images
------

The Operator should, by default, use the ``docker.io/zuul`` images that
are published. To support locally built or overridden images, the Operator
should have optional config settings for each image.

::

  apiVersion: zuul-ci.org/v1alpha1
  kind: Zuul
  spec:
    merger:
      count: 5
      image: docker.io/example/zuul-merger
    executor:
      count: 5
    web:
      count: 1
    fingergw:
      count: 1
    scheduler:
      count: 1
    launcher:
    builder:
      count: 2

External Dependencies
---------------------

Zuul needs some services, such as a RDBMS and a Zookeeper, that themselves
are resources that should or could be managed by an Operator. It is out of
scope (and inappropriate) for Zuul to provide these itself. Instead, the Zuul
Operator should use CRDs provided by other Operators.

On Kubernetes installs that support the Operator Lifecycle Manager, external
dependencies can be declared in the Zuul Operator's OLM metadata. However,
not all Kubernetes installs can handle this, so it should also be possible
for a deployer to manually install a list of documented operators and CRD
definitions before installing the Zuul Operator.

For each external service dependency where the Zuul Operator would be relying
on another Operator to create and manage the given service, there should be
a config override setting to allow a deployer to say "I already have one of
these that's located at Location, please don't create one." The config setting
should be the location and connection information for the externally managed
version of the service, and not providing that information should be taken
to mean the Zuul Operator should create and manage the resource.

::

  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: externalDatabase
  type: Opaque
  stringData:
    dburi: mysql+pymysql://zuul:password@db.example.com/zuul
  ---
  apiVersion: zuul-ci.org/v1alpha1
  kind: Zuul
  spec:
    # If the database section is omitted, the Zuul Operator will create
    # and manage the database.
    database:
      secretName: externalDatabase
      key: dburi

While Zuul supports multiple backends for RDBMS, the Zuul Operator should not
attempt to support managing both. If the user chooses to let the Zuul Operator
create and manage RDBMS, the `Percona XtraDB Cluster Operator`_ should be
used. Deployers who wish to use a different one should use the config override
setting pointing to the DB location.

.. _Percona XtraDB Cluster Operator: https://operatorhub.io/operator/percona-xtradb-cluster-operator

Zuul Config
-----------

Zuul config files that do not contain information that the Operator needs to
do its job, or that do not contain information into which the Operator might
need to add data, should be handled by ConfigMap resources and not as
parts of the CRD. The CRD should take references to the ConfigMap objects.

Completely external files like ``clouds.yaml`` and ``kube/config``
should be in Secrets referenced in the config. Zuul files like
``nodepool.yaml`` and ``main.yaml`` that contain no information the Operator
needs should be in ConfigMaps and referenced.

::

  apiVersion: zuul-ci.org/v1alpha1
  kind: Zuul
  spec:
    merger:
      count: 5
    executor:
      count: 5
    web:
      count: 1
    fingergw:
      count: 1
    scheduler:
      count: 1
      config: zuulYamlConfig
    launcher:
      config: nodepoolYamlConfig
    builder:
      config: nodepoolYamlConfig
    externalConfig:
      openstack:
        secretName: cloudsYaml
      kubernetes:
        secretName: kubeConfig
      amazon:
        secretName: botoConfig

Zuul files like ``/etc/nodepool/secure.conf`` and ``/etc/zuul/zuul.conf``
should be managed by the Operator and their options should be represented in
the CRD.

The Operator will shard the Nodepool config by provider-region using a utility
pod and create a new ConfigMap for each provider-region with only the subset of
config needed for that provider-region. It will then create a pod for each
provider-region.

Because the Operator needs to make decisions based on what's going on with
the ``zuul.conf``, or needs to directly manage some of it on behalf of the
deployer (such as RDBMS and Zookeeper connection info), the ``zuul.conf``
file should be managed by and expressed in the CRD.

Connections should each have a stanza that is mostly a passthrough
representation of what would go in the corresponding section of ``zuul.conf``.

Due to the nature of secrets in kubernetes, fields that would normally contain
either a secret string or a path to a file containing secret information
should instead take the name of a kubernetes secret and the key name of the
data in that secret that the deployer will have previously defined. The
Operator will use this information to mount the appropriate secrets into a
utility container, construct appropriate config files for each service,
reupload those into kubernetes as additional secrets, and then mount the
config secrets and the needed secrets containing file content only in the
pods that need them.

::

  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: gerritSecrets
  type: Opaque
  data:
    sshkey: YWRtaW4=
    http_password: c2VjcmV0Cg==
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: githubSecrets
  type: Opaque
  data:
    app_key: aRnwpen=
    webhook_token: an5PnoMrlw==
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: pagureSecrets
  type: Opaque
  data:
    api_token: Tmf9fic=
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: smtpSecrets
  type: Opaque
  data:
    password: orRn3V0Gwm==
  ---
  apiVersion: v1
  kind: Secret
  metadata:
    name: mqttSecrets
  type: Opaque
  data:
    password: YWQ4QTlPO2FpCg==
    ca_certs: PVdweTgzT3l5Cg==
    certfile: M21hWF95eTRXCg==
    keyfile: JnhlMElpNFVsCg==
  ---
  apiVersion: zuul-ci.org/v1alpha1
  kind: Zuul
  spec:
    merger:
      count: 5
      git_user_email: zuul@example.org
      git_user_name: Example Zuul
    executor:
      count: 5
      manage_ansible: false
    web:
      count: 1
      status_url: https://zuul.example.org
    fingergw:
      count: 1
    scheduler:
      count: 1
    connections:
      gerrit:
        driver: gerrit
        server: gerrit.example.com
        sshkey:
          # If the key name in the secret matches the connection key name,
          # it can be omitted.
          secretName: gerritSecrets
        password:
          secretName: gerritSecrets
          # If they do not match, the key must be specified.
          key: http_password
        user: zuul
        baseurl: http://gerrit.example.com:8080
        auth_type: basic
      github:
        driver: github
        app_key:
          secretName: githubSecrets
          key: app_key
        webhook_token:
          secretName: githubSecrets
          key: webhook_token
        rate_limit_logging: false
        app_id: 1234
      pagure:
        driver: pagure
        api_token:
          secretName: pagureSecrets
          key: api_token
      smtp:
        driver: smtp
        server: smtp.example.com
        port: 25
        default_from: zuul@example.com
        default_to: zuul.reports@example.com
        user: zuul
        password:
          secretName: smtpSecrets
      mqtt:
        driver: mqtt
        server: mqtt.example.com
        user: zuul
        password:
          secretName: mqttSecrets
        ca_certs:
          secretName: mqttSecrets
        certfile:
          secretName: mqttSecrets
        keyfile:
          secretName: mqttSecrets

Executor job volume
-------------------

To manage the executor job volumes, the CR also accepts a list of volumes
to be bind mounted in the job bubblewrap contexts:

::

  name: Text
  context: <trusted | untrusted>
  access: <ro | rw>
  path: /path
  volume: Kubernetes.Volume


For example, to expose a GCP authdaemon token, the Zuul CR can be defined as

::

  apiVersion: zuul-ci.org/v1alpha1
  kind: Zuul
  spec:
    ...
    jobVolumes:
      - context: trusted
        access: ro
        path: /authdaemon/token
        volume:
          name: gcp-auth
          hostPath:
            path: /var/authdaemon/executor
            type: DirectoryOrCreate

Which would result in a new executor mountpath along with this zuul.conf change:

::

   trusted_ro_paths=/authdaemon/token


Logging
-------

By default, the Zuul Operator should perform no logging config which should
result in Zuul using its default of logging to ``INFO``. There should be a
simple config option to switch that to enable ``DEBUG`` logging. There should
also be an option to allow specifying a named ``ConfigMap`` with a logging
config. If a logging config ``ConfigMap`` is given, it should override the
``DEBUG`` flag.
