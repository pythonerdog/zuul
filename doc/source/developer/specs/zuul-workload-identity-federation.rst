OIDC compatible Workload Identity Federation in Zuul
====================================================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

The following specification describes a way to enrich Zuul's secrets engine with
an OpenID Connect Identity Provider which will enable Zuul to provide an identity
to a job which can be trusted by federated third party services.

Introduction
------------

Currently Zuul has a powerful secrets mechanism which works by storing secrets
encrypted along the job configuration in the repositories. This works well as
long as there are only few secrets or they are valid for long periods of time.

However secrets management can become a challenge at scale. Best practice for
the sake of security is to use dynamic secrets
(see also `OWASP on Automate Secrets Management
<https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html#24-automate-secrets-management>`_
) In many companies this is enforced by governing departments for compliance.
Doing so can be a lot of work when having a lot of different secrets.

For similar reasons more and more tools and services offer the
possibility to setup a trust relationship with OIDC Identity Provider (OP)
which can give specific entities an identity with specific properties. This can
then be used to perform authorization decisions.

Examples for this mechanism are:

*  AWS EKS clusters have an OIDC issuer URL which can give their pods an identity
   which in turn can be enabled to perform specific tasks in the AWS API.

* GitHub Actions use GitHub OIDC Identity Provider to retrieve an Identity Token
  which is unique to the job where it is generated in. This makes it possible to
  perform e.g. CI/CD tasks on third party services which support OIDC and trust
  the GitHub Identity Provider through OpenID Connect Federation.


OIDC workflow
-------------

Both work in the same way where the system which manages an entity (pods, jobs,
etc.) generates an OIDC ID token which is signed by the OIDC IDP of the
system and hands this token to this workload. If a third party system
established a trust relationship with the OIDC IDP the workload then can take
this ID token and perform an OIDC token exchange in order to get an access token
which can be used to perform authenticated and authorized actions on the target
service.

ID tokens are JSON Web Tokens (JWT) where it's JSON payload is signed by the
private signing keys if the OIDC issuer. The payload of an ID token is a simple
JSON dict where the keys are called claims. A minimal JWT token contains the
following claims:

* `iss`: Identifier of the issuer, usually the root URL of the endpoints it serves
* `sub`: Subject identifier (e.g. user name, unique identifier of a workload, ...)
* `aud`: Identifier of the target service
* `exp`: Expiration timestamp of the ID token
* `iat`: Issue timestamp of the ID token

.. code-block:: json

   {
      "exp": 1631700395,
      "iat": 1631696795,
      "idp": "default",
      "iss": "https://oidc.example.org",
      "sub": "example-subject",
      "some": "thing",
      "also-lists": [
         "are",
         "possible"
      ]
   }

When a third party service needs to validate such an ID token it first queries
the `.well-known/openid-configuration` endpoint of the OIDC issuer.

This endpoint returns a JSON document which can have many details but for just
the OIDC issuer use case needed here this is what's required in there:

.. code-block:: json

  {
    "issuer": "https://zuul.example.org",
    "jwks_uri": "https://zuul.example.org/jwks/keys",
    "claims_supported": [
      "aud",
      "iat",
      "iss",
      "name",
      "sub",
      "custom"
    ],
    "response_types_supported": [
      "id_token"
    ],
    "id_token_signing_alg_values_supported": [
      "RS256"
    ],
    "subject_types_supported": [
      "public"
    ]
  }

The second endpoint required is the `jwks_uri` which publishes the public keys
of the signing keys as a JSON Web Key Store which the third party service can
download and use to validate the ID token. This will be a small set of keys for
the system overall as there is no need for per tenant keys. This document
contains a list of keys which are referred as `kid` in the JWT header part:

.. code-block:: json

  {
    "keys": [
      {
        "kty": "RSA",
        "use": "sig",
        "kid": "key-2024-03-13",
        "alg": "RS256",
        "n": "0PFnE176zgqtm56ZNjv(...)VJ4Gk4m9Cf38Ios",
        "e": "AQAB"
      }
    ]
  }


Job Configuration
-----------------

Since this ID tokens need to be kept secret as well we can use Zuul's standard
secrets handling mechanisms.

We could add an attribute `oidc` to the secret snippet and make `data` and
`oidc` mutually exclusive.

Unlike secrets preparation the ID token will be generated for each individual
Ansible playbook just before starting it. This is required such that the
required TTL can be minimized and is more predictable by the job authors as they
potentially cannot judge how long the token needs to be valid until it is really
required.

.. code-block:: yaml

  - secret:
      name: aws-oidc
      oidc:
        # TTL of the ID token in seconds (used to calculate exp claim)
        # Max TTL should be configurable in the tenant config.
        ttl: 300
        # Optionally specify the signing algorithm if the default is
        # not suitable.
        algorithm: RS256
        # Claims to put into ID token
        claims:
          # Audience (required, depending on the intended use of the token)
          aud: sts.amazonaws.com
          random: claim

Zuul default claims:

.. code-block:: yaml

  # Sub is important as most third party services will likely match on this
  # claim to determine the permissions. This is kind of an FQDN to uniquely
  # identify the zuul secret used.
  sub: "secret:<zuul-tenant>/<canonical-project-name>/<secret name>"

  # Some information on the job's context might be useful.  Caution
  # should be used if these are used for matching; documentation should
  # be written about the caveats (e.g., the "job-name" may change due to
  # inheritance).

  build-uuid: "<build-uuid>"
  job-name: "<job-name>"
  playbook: "<playbook>"
  pipeline: "<pipeline>"
  tenant: "<tenant>"

The ``sub`` (subject) claim begins with a prefix indicating a scheme
(``secret:``) in the example above.  The only scheme that Zuul will
support for the initial implementation is ``secret``, where the
subject will be the fully qualified name of the Zuul secret.  By
including the scheme, we will have the option to add other schemes
later (these might include project or tenant-level tokens).

Signing key handling
--------------------

The signing keys can be generated by Zuul itself during runtime
similar to the per project private keys used for secrets encryption.
They can be stored in zookeeper under `/keystorage/oidc/{algorithm}`
using the existing data structure used by the `KeyStorage` class. This
gets populated on scheduler startup.

The initial implementation should support the `Required` and
`Recommended` algorithms in `RFC 7518`_.  That is: HS256, RS256, and
ES256.  We may want to support more in the future.

The ``zuul.conf`` file will have an optional section to specify the
supported and default values for keys.  For example:

.. code-block::

   [oidc]
   supported_signing_algorithms=HS256, RS256, ES256
   default_signing_algorithm=HS256

Operators may use this to reduce the set of supported keys, and change
the default algorithm system-wide.  A secret may specify which
algorithm to use (selecting among the restricted set specified in
``supported_algos`` if that value is set) if the default algorithm is
not suitable for the service with which the secret is used.

.. code-block:: json

  {
    "schema": 1,
    "keys": [
        {
            "version": 0,
            "created": "<timestamp>",
            "private_key": "<blob>"
        },
        {
            "version": 1,
            "created": "<timestamp>",
            "private_key": "<blob>"
        },
        "..."
    ]
  }

.. _RFC 7518: https://www.rfc-editor.org/rfc/rfc7518#section-3.1

Signing key rotation should be handled automatically by the scheduler. Since all
ID tokens have a limited lifetime the signing keys can be automatically rotated
frequently (e.g. once per day or week). The process looks like this:

1. Generate a new signing key and register it as additional key under `/keystorage/oidc/...`.

2. As soon as the new key is existing the executors start using the new one when
   issuing new ID tokens

3. Wait for max-ttl over all tenants

4. Remove the old signing key

Additionally, the scheduler will accept a command over the control
socket (issued via `zuul-admin`) to start immediate rotation in case a
key is compromised.

Zuul Web
--------

Zuul web needs to add two endpoints. Both will be a global url similar to webhooks:

* `<zuul-root>/oidc/.well-known/openid-configuration`: This is a static document
  which never changes except on config changes like zuul root url

* `<zuul-root>/oidc/jwks`: The JSON Web Key Store used to publish all currently
  active public signing keys. This can be pre-cached zuul-web on startup and
  signing key rotations so we don't have to parse the keys on every request.


Security considerations
-----------------------

Since the ID tokens are sensitive data they must be handled the same way as the
existing secrets regarding config or untrusted projects, etc.

The signing keys must be special protected in the same way as the already
existing private keys using encryption at rest within zookeeper (by re-using the
KeyStorage class).

Given the signing keys get automatically rotated frequently OIDC makes it
possible to access external services without having to store any long lived
secret anywhere except the zuul master password which is used to encrypt the
signing keys in zookeeper.


Work Items
----------

* Implement signing key handling in scheduler
* Add OIDC endpoints to zuul-web
* Adapt secrets config model and add ID token generation in executor
