:title: Authenticated Actions

.. _authentication:

Authenticated Access
====================

Access to Zuul's REST API and web interface can optionally be
restricted.  By default, anonymous read access to any tenant is
permitted.  Optionally, some administrative actions may also be
enabled and restricted to authorized users.  Additionally, individual
tenants or the entire system may have read-level access restricted
to authorized users.

The supported administrative actions are **autohold**,
**enqueue/enqueue-ref**, **dequeue/dequeue-ref** and
**promote**. These are similar to the ones available through
Zuul's CLI.

The protected endpoints require a bearer token, passed to Zuul Web
Server as the **Authorization** header of the request. The token and
this workflow follow the JWT standard as established in this `RFC
<https://tools.ietf.org/html/rfc7519>`_.

Important Security Considerations
---------------------------------

Anybody with a valid administrative token can perform privileged
actions exposed through the REST API. Furthermore revoking tokens,
especially when manually issued, is not trivial.

As a mitigation, tokens should be generated with a short time to
live, like 10 minutes or less. If the token contains authorization Information
(see the ``zuul.admin`` claim below), it should be generated with as little a scope
as possible (one tenant only) to reduce the surface of attack should the
token be compromised.

Exposing administration tasks can impact build results (dequeue-ing buildsets),
and pose potential resources problems with Nodepool if the ``autohold`` feature
is abused, leading to a significant number of nodes remaining in "hold" state for
extended periods of time. As always, "with great power comes great responsibility"
and tokens should be handed over with discernment.

Configuration
-------------

.. important:: In order to use restricted commands in the zuul command
               line interface, at least one HS256 authenticator should
               be configured.

To enable tenant-scoped access to privileged actions or restrict
read-level access, see the Zuul Web Server component's section.

To set access rules for a tenant, see :ref:`the documentation about tenant
definition <authz_rule_definition>`.

Most of the time, only one authenticator will be needed in Zuul's configuration;
namely the configuration matching a third party identity provider service like
dex, auth0, keycloak or others. It can be useful however to add another
authenticator similar to this one:

.. code-block:: ini

    [auth zuul_operator]
    driver=HS256
    allow_authz_override=true
    realm=zuul.example.com
    client_id=zuul.example.com
    issuer_id=zuul_operator
    secret=exampleSecret

With such an authenticator, a Zuul operator can use Zuul's CLI to
issue tokens overriding a tenant's access rules if need
be. A user can then use these tokens with Zuul's CLI to perform protected actions
on a tenant temporarily, without having to modify a tenant's access rules.

.. _jwt-format:

JWT Format
----------

Zuul can consume JWTs with the following minimal set of claims:

.. code-block:: javascript

  {
   'iss': 'jwt_provider',
   'aud': 'my_zuul_deployment',
   'exp': 1234567890,
   'iat': 1234556780,
   'sub': 'alice'
  }

* **iss** is the issuer of the token. It can be used to filter
  Identity Providers.
* **aud**, as the intended audience, is usually the client id as registered on
  the Identity Provider.
* **exp** is the token's expiry timestamp.
* **iat** is the token's date of issuance timestamp.
* **sub** is the default, unique identifier of the user.

JWTs can be extended arbitrarily with other claims. Zuul however can look for a
specific **zuul** claim, if the ``allow_authz_override`` option was set to True
in the authenticator's configuration. This claim has the following format:

.. code-block:: javascript

  {
   'zuul': {
      'admin': ['tenant-one', 'tenant-two']
    }
  }

The **admin** field is a list of tenants on which the token's bearer is granted
the right to perform privileged actions.

Manually Generating a JWT
-------------------------

An operator can generate a JWT by using the settings of a configured authenticator
in ``zuul.conf``.

For example, in Python, and for an authenticator using the ``HS256`` algorithm:

.. code-block:: python

   >>> import jwt
   >>> import time
   >>> jwt.encode({'sub': 'user1',
                   'iss': <issuer_id>,
                   'aud': <client_id>,
                   'iat': int(time.time()),
                   'exp': int(time.time()) + 300,
                   'zuul': {
                            'admin': ['tenant-one']
                           }
                  }, <secret>, algorithm='HS256')
   'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ6dXVsIjp7ImFkbWluIjpbInRlbmFudC1vbmUiXX0sInN1YiI6InZlbmttYW4iLCJpc3MiOiJtYW51YWwiLCJleHAiOjE1NjAzNTQxOTcuMTg5NzIyLCJpYXQiOjE1NjAzNTM4OTcuMTg5NzIxLCJhdWQiOiJ6dXVsIn0.Qqb-ANmYv8slNUVSqjCJDL8HlH9L7nnLtLU2HBGzQJk'

Online resources like https://jwt.io are also available to generate, decode and
debug JWTs.

Debugging
---------

If problems appear:

* Make sure your configuration is correct, especially callback URIs.
* More information can be found in Zuul's web service logs.
* From the user's side, activating the web console in the browser can be helpful
  to debug API calls.

Interfacing with Other Systems
------------------------------

Here are some how-tos to help administrators enable OpenID Connect
authentication in Zuul and Zuul's Web UI.

.. toctree::
   :maxdepth: 1

   howtos/openid-with-google
   howtos/openid-with-keycloak
   howtos/openid-with-microsoft
   tutorials/keycloak
