===========================
Tenant-scoped admin web API
===========================

https://storyboard.openstack.org/#!/story/2001771

The aim of this spec is to extend the existing web API of Zuul to
privileged actions, and to scope these actions to tenants, projects and privileged users.

Problem Description
===================

Zuul 3 introduced tenant isolation, and most privileged actions, being scoped
to a specific tenant, reflect that change. However the only way to trigger
these actions is through the Zuul CLI, which assumes either access to the
environment of a Zuul component or to Zuul's configuration itself. This is a
problem as being allowed to perform privileged actions on a tenant or for a
specific project should not entail full access to Zuul's admin capabilities.

.. Likewise, Nodepool provides actions that could be scoped to a tenant:

  * Ability to trigger an image build when the definition of an image used by
  that tenant has changed
  * Ability to delete nodesets that have been put on autohold (this is mitigated
  by the max-hold-age setting in Nodepool, if set)

  These actions can only be triggered through Nodepool's CLI, with the same
  problems as Zuul. Another important blocker is that Nodepool has no notion of
  tenancy as defined by Zuul.

Proposed Change
===============

Zuul will expose privileged actions through its web API. In order to do so, Zuul
needs to support user authentication. A JWT (JSON Web Token) will be used to carry
user information; from now on it will be called the **Authentication Token** for the
rest of this specification.

Zuul needs also to support authorization and access control. Zuul's configuration
will be modified to include access control rules.

A Zuul operator will also be able to generate an Authentication Token manually
for a user, and communicate the Authentication Token to said user. This Authentication
Token can optionally include authorization claims that override Zuul's authorization
configuration, so that an operator can provide privileges temporarily to a user.

By querying Zuul's web API with the Authentication Token set in an
"Authorization" header, the user can perform administration tasks.

Zuul will need to provide the following minimal new features:

* JWT validation
* Access control configuration
* administration web API

The manual generation of Authentication Tokens can also be used for testing
purposes or non-production environments.


JWT Validation
--------------

Expected Format
...............

Note that JWTs can be arbitrarily extended with custom claims, giving flexibility
in its contents. It also allows to extend the format as needed for future
features.

In its minimal form, the Authentication Token's contents will have the following
format:

.. code-block:: javascript

  {
   'iss': 'jwt_provider',
   'aud': 'my_zuul_deployment',
   'exp': 1234567890,
   'iat': 1234556780,
   'sub': 'alice'
  }

* **iss** is the issuer of the Authorization Token. This can be logged for
  auditing purposes, and it can be used to filter Identity Providers.
* **aud**, as the intended audience, is the client id for the Zuul deployment in the
  issuer.
* **exp** is the Authorization Token's expiry timestamp.
* **iat** is the Authorization Token's date of issuance timestamp.
* **sub** is the default, unique identifier of the user.

These are standard JWT claims and ensure that Zuul can consume JWTs issued
by external authentication systems as Authentication Tokens, assuming the claims
are set correctly.

Authentication Tokens lacking any of these claims will be rejected.

Authentication Tokens with an ``iss`` claim not matching the white list of
accepted issuers in Zuul's configuration will be rejected.

Authentication Tokens addressing a different audience than the expected one
for the specific issuer will be rejected.

Unsigned or incorrectly signed Authentication Tokens will be rejected.

Authentication Tokens with an expired timestamp will be rejected.


Extra Authentication Claims
...........................

Some JWT Providers can issue extra claims about a user, like *preferred_username*
or *email*. Zuul will allow an operator to set such an extra claim as the default,
unique user identifier in place of *sub* if it is more convenient.

If the chosen claim is missing from the Authentication Token, it will be rejected.

Authorization Claims
....................

If the Authentication Token is issued manually by a Zuul Operator, it can include
extra claims extending Zuul's authorization rules for the Authentication Token's
bearer:

.. code-block:: javascript

  {
   'iss': 'zuul_operator',
   'aud': 'zuul.openstack.org',
   'exp': 1234567890,
   'iat': 1234556780,
   'sub': 'alice',
   'zuul': {
       'admin': ['tenantA', 'tenantB']
    }
  }

* **zuul** is a claim reserved for zuul-specific information about the user.
  It is a dictionary, the only currently supported key is **admin**.
* **zuul.admin** is a list of tenants on which the user is allowed privileged
  actions.

In the previous example, user **alice** can perform privileged actions
on every project of **tenantA** and **tenantB**. This is on top of alice's
default authorizations.

These are intended to be **whitelists**: if a tenant is unlisted the user is
assumed not to be allowed to perform a privileged action (unless the
authorization rules in effect for this deployment of Zuul allow it.)

Note that **iss** is set to ``zuul_operator``. This can be used to reject Authentication
Tokens with a ``zuul`` claim if they come from other issuers.


Access Control Configuration
----------------------------

The Zuul main.yaml configuration file will accept new **admin-rule** objects
describing access rules for privileged actions.

Authorization rules define conditions on the claims
in an Authentication Token; if these conditions are met the action is authorized.

In order to allow the parsing of claims with complex structures like dictionaries,
an XPath-like format will be supported.

Here is an example of how rules can be defined:

.. code-block:: yaml

  - admin-rule:
      name: affiliate_or_admin
      conditions:
        - resources_access.account.roles: "affiliate"
          iss: external_institution
        - resources_access.account.roles: "admin"
  - admin-rule:
      name: alice_or_bob
      conditions:
        - zuul_uid: alice
        - zuul_uid: bob

* **name** is how the authorization rule will be refered as in Zuul's tenants
  configuration.
* **conditions** is the list of conditions that define a rule. An Authentication
  Token must match **at least one** of the conditions for the rule to apply. A
  condition is a dictionary where keys are claims. **All** the associated values must
  match the claims in the user's Authentication Token.

Zuul's authorization engine will adapt matching tests depending on the nature of
the claim in the Authentication Token, eg:

* if the claim is a JSON list, check that the condition value is in the claim
* if the claim is a string, check that the condition value is equal to the claim's value

The special ``zuul_uid`` claim refers to the ``uid_claim`` setting in an
authenticator's configuration, as will be explained below. By default it refers
to the ``sub`` claim of an Authentication Token.

This configuration file is completely optional, if the ``zuul.admin`` claim
is set in the Authentication Token to define tenants on which privileged actions
are allowed.

Under the above example, the following Authentication Token would match rules
``affiliate_or_admin`` and ``alice_or_bob``:

.. code-block:: javascript

  {
   'iss': 'external_institution',
   'aud': 'my_zuul_deployment',
   'exp': 1234567890,
   'iat': 1234556780,
   'sub': 'alice',
   'resources_access': {
       'account': {
           'roles': ['affiliate', 'other_role']
       }
   },
  }

And this Authentication Token would only match rule ``affiliate_or_admin``:

.. code-block:: javascript

  {
   'iss': 'some_hellish_dimension',
   'aud': 'my_zuul_deployment',
   'exp': 1234567890,
   'sub': 'carol',
   'iat': 1234556780,
   'resources_access': {
       'account': {
           'roles': ['admin', 'other_role']
       }
   },
  }

Privileged actions are tenant-scoped. Therefore the access control will be set
in tenants definitions, e.g:

.. code-block:: yaml

  - tenant:
      name: tenantA
      admin_rules:
        - an_authz_rule
        - another_authz_rule
      source:
        gerrit:
          untrusted-projects:
            - org/project1:
            - org/project2
            - ...
  - tenant:
      name: tenantB
      admin_rules:
        - yet_another_authz_rule
      source:
        gerrit:
          untrusted-projects:
            - org/project1
            - org/project3
            - ...


An action on the ``tenantA`` tenant will be allowed if ``an_authz_rule`` OR
``another_authz_rule`` is matched.

An action on the ``tenantB`` tenant will be authorized if ``yet_another_authz_rule``
is matched.

Administration Web API
----------------------

Unless specified, all the following endpoints require the presence of the ``Authorization``
header in the HTTP query.

Unless specified, all calls to the endpoints return with HTTP status code 201 if
successful, 401 if unauthenticated, 403 if the user is not allowed to perform the
action, and 400 with a JSON error description otherwise.
In case of a 401 code, an additional ``WWW-Authenticate`` header is emitted, for example::

  WWW-Authenticate: Bearer realm="zuul.openstack.org"
                            error="invalid_token"
                            error_description="Token expired"

Zuul's web API will be extended to provide the following endpoints:

POST /api/tenant/{tenant}/project/{project}/enqueue
...................................................

This call allows a user to re-enqueue a buildset, like the *enqueue* or
*enqueue-ref* subcommands of Zuul's CLI.

To trigger the re-enqueue of a change, the following JSON body must be sent in
the query:

.. code-block:: javascript

    {"trigger": <Zuul trigger>,
     "change": <changeID>,
     "pipeline": <pipeline>}

To trigger the re-enqueue of a ref, the following JSON body must be sent in
the query:

.. code-block:: javascript

    {"trigger": <Zuul trigger>,
     "ref": <ref>,
     "oldrev": <oldrev>,
     "newrev": <newrev>,
     "pipeline": <pipeline>}


POST /api/tenant/{tenant}/project/{project}/dequeue
...................................................

This call allows a user to dequeue a buildset, like the *dequeue* subcommand of
Zuul's CLI.

To dequeue a change, the following JSON body must be sent in the query:

.. code-block:: javascript

    {"change": <changeID>,
     "pipeline": <pipeline>}

To dequeue a ref, the following JSON body must be sent in
the query:

.. code-block:: javascript

    {"ref": <ref>,
     "pipeline": <pipeline>}


POST /api/tenant/{tenant}/project/{project}/autohold
..............................................................

This call allows a user to automatically put a node set on hold in case of
a build failure on the chosen job, like the *autohold* subcommand of Zuul's
CLI.

Any of the following JSON bodies must be sent in the query:

.. code-block:: javascript

    {"change": <changeID>,
     "reason": <reason>,
     "count": <count>,
     "node_hold_expiration": <expiry>,
     "job": <job>}

or

.. code-block:: javascript

    {"ref": <ref>,
     "reason": <reason>,
     "count": <count>,
     "node_hold_expiration": <expiry>,
     "job": <job>}


GET /api/user/authorizations
.........................................

This call returns the list of tenant the authenticated user can perform privileged
actions on.

This endpoint can be consumed by web clients in order to know which actions to display
according to the user's authorizations, either from Zuul's configuration or
from the valid Authentication Token's ``zuul.admin`` claim if present.

The return value is similar in form to the `zuul.admin` claim:

.. code-block:: javascript

  {
   'zuul': {
       'admin': ['tenantA', 'tenantB']
       }
  }

The call needs authentication and returns with HTTP code 200, or 401 if no valid
Authentication Token is passed in the request's headers. If no rule applies to
the user, the return value is

.. code-block:: javascript

  {
    'zuul': {
        'admin': []
    }
  }

Logging
.......

Zuul will log an event when a user presents an Authentication Token with a
``zuul.admin`` claim, and if the authorization override is granted or denied:

.. code-block:: bash

  Issuer %{iss}s attempt to override user %{sub}s admin rules granted|denied

At DEBUG level the log entry will also contain the ``zuul.admin`` claim.

Zuul will log an event when a user presents a valid Authentication Token to
perform a privileged action:

.. code-block:: bash

  User %{sub}s authenticated from %{iss}s requesting %{action}s on %{tenant}s/%{project}s

At DEBUG level the log entry will also contain the JSON body passed to the query.

The events will be logged at zuul.web's level but a new handler focused on auditing
could also be created.

Zuul Client CLI and Admin Web API
.................................

The CLI will be modified to call the REST API instead of using a Gearman server
if the CLI's configuration file is lacking a ``[gearman]`` section but has a
``[web]`` section.

In that case the CLI will take the --auth-token argument on
the ``autohold``, ``enqueue``, ``enqueue-ref`` and ``dequeue`` commands. The
Authentication Token will be used to query the web API to execute these
commands; allowing non-privileged users to use the CLI remotely.

.. code-block:: bash

  $ zuul  --auth-token AaAa.... autohold --tenant openstack --project example_project --job example_job --reason "reason text" --count 1
  Connecting to https://zuul.openstack.org...
  <usual autohold output>


JWT Generation by Zuul
-----------------------

Client CLI
..........

A new command will be added to the Zuul Client CLI to allow an operator to generate
an Authorization Token for a third party. It will return the contents of the
``Authorization`` header as it should be set when querying the admin web API.

.. code-block:: bash

    $ zuul create-auth-token --auth-config zuul-operator --user alice --tenant tenantA --expires-in 1800
    bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vbWFuYWdlc2Yuc2ZyZG90ZXN0aW5zdGFuY2Uub3JnIiwienV1bC50ZW5hbnRzIjp7ImxvY2FsIjoiKiJ9LCJleHAiOjE1Mzc0MTcxOTguMzc3NTQ0fQ.DLbKx1J84wV4Vm7sv3zw9Bw9-WuIka7WkPQxGDAHz7s

The ``auth-config`` argument refers to the authenticator configuration to use
(see configuration changes below). The configuration must mention the secret
to use to sign the Token.

This way of generating Authorization Tokens is meant for testing
purposes only and should not be used in production, where the use of an
external Identity Provider is preferred.

Configuration Changes
.....................

JWT creation and validation require a secret and an algorithm. While several algorithms are
supported by the pyJWT library, using ``RS256`` offers asymmetrical encryption,
which allows the public key to be used in untrusted contexts like javascript
code living browser side. Therefore this should be the preferred algorithm for
issuers. Zuul will also support ``HS256`` as the most widely used algorithm.

Some identity providers use key sets (also known as **JWKS**), therefore the key to
use when verifying the Authentication Token's signatures cannot be known in advance.
Zuul must support the ``RS256`` algorithm with JWKS as well.

Here is an example defining the three supported types of authenticators:

.. code-block:: ini

    [web]
    listen_address=127.0.0.1
    port=9000
    static_cache_expiry=0
    status_url=https://zuul.example.com/status

    # symmetrical encryption
    [auth "zuul_operator"]
    driver=HS256
    # symmetrical encryption only needs a shared secret
    secret=exampleSecret
    # accept "zuul.actions" claim in Authentication Token
    allow_authz_override=true
    # what the "aud" claim must be in Authentication Token
    client_id=zuul.openstack.org
    # what the "iss" claim must be in Authentication Token
    issuer_id=zuul_operator
    # the claim to use as the unique user identifier, defaults to "sub"
    uid_claim=sub
    # Auth realm, used in 401 error messages
    realm=openstack
    # (optional) Ensure a Token cannot be valid for longer than this amount of time, in seconds
    max_validity_time = 1800000
    # (optional) Account for skew between clocks, in seconds
    skew = 3

    # asymmetrical encryption
    [auth "my_oidc_idp"]
    driver=RS256
    public_key=/path/to/key.pub
    # optional, needed only if Authentication Token must be generated manually as well
    private_key=/path/to/key
    # if not explicitly set, allow_authz_override defaults to False
    # what the "aud" claim must be in Authentication Token
    client_id=my_zuul_deployment_id
    # what the "iss" claim must be in Authentication Token
    issuer_id=my_oidc_idp_id
    # Auth realm, used in 401 error messages
    realm=openstack
    # (optional) Ensure a Token cannot be valid for longer than this amount of time, in seconds
    max_validity_time = 1800000
    # (optional) Account for skew between clocks, in seconds
    skew = 3

    # asymmetrical encryption using JWKS for validation
    # The signing secret being known to the Identity Provider only, this
    # authenticator cannot be used to manually issue Tokens with the CLI
    [auth google_oauth_playground]
    driver=RS256withJWKS
    # URL of the JWKS; usually found in the .well-known config of the Identity Provider
    keys_url=https://www.googleapis.com/oauth2/v3/certs
    # what the "aud" claim must be in Authentication Token
    client_id=XXX.apps.googleusercontent.com
    # what the "iss" claim must be in Authentication Token
    issuer_id=https://accounts.google.com
    uid_claim=name
    # Auth realm, used in 401 error messages
    realm=openstack
    # (optional) Account for skew between clocks, in seconds
    skew = 3

Implementation
==============

Assignee(s)
-----------

Primary assignee:
  mhu

.. feel free to add yourself as an assignee, the more eyes/help the better

Gerrit Topic
------------

Use Gerrit topic "zuul_admin_web" for all patches related to this spec.

.. code-block:: bash

    git-review -t zuul_admin_web

Work Items
----------

Due to its complexity the spec should be implemented in smaller "chunks":

* https://review.openstack.org/576907 - Add admin endpoints, support for JWT
  providers declaration in the configuration, JWT validation mechanism
* https://review.openstack.org/636197 - Allow Auth Token generation from
  Zuul's CLI
* https://review.openstack.org/636315 - Allow users to use the REST API from
  the CLI (instead of Gearman), with a bearer token
* https://review.openstack.org/#/c/639855 - Authorization configuration objects declaration and validation
* https://review.openstack.org/640884 - Authorization engine
* https://review.openstack.org/641099 - REST API: add /api/user/authorizations route

Documentation
-------------

* The changes in the configuration will need to be documented:

  * configuring authenticators in zuul.conf, supported algorithms and their
    specific configuration options
  * creating authorization rules

* The additions to the web API need to be documented.
* The additions to the Zuul Client CLI need to be documented.
* The potential impacts of exposing administration tasks in terms of build results
  or resources management need to be clearly documented for operators (see below).

Security
--------

Anybody with a valid Authentication Token can perform administration tasks exposed
through the Web API. Revoking JWT is not trivial, and not in the scope of this spec.

As a mitigation, Authentication Tokens should be generated with a short time to
live, like 30 minutes or less. This is especially important if the Authentication
Token overrides predefined authorizations with a ``zuul.admin`` claim. This
could be the default value for generating Tokens with the CLI; this will depend on the configuration of
other external issuers otherwise. If using the ``zuul.admin`` claims, the
Authentication Token should also be generated with as little a scope as possible
(one tenant only) to reduce the surface of attack should the
Authentication Token be compromised.

Exposing administration tasks can impact build results (dequeue-ing buildsets),
and pose potential resources problems with Nodepool if the ``autohold`` feature
is abused, leading to a significant number of nodes remaining in "hold" state for
extended periods of time. Such power should be handed over responsibly.

These security considerations concern operators and the way they handle this
feature, and do not impact development. They however need to be clearly documented,
as operators need to be aware of the potential side effects of delegating privileges
to other users.

Testing
-------

* Unit testing of the new web endpoints will be needed.
* Validation of the new configuration parameters will be needed.

Follow-up work
--------------

The following items fall outside of the scope of this spec but are logical features
to implement once the tenant-scoped admin REST API gets finalized:

* Web UI: log-in, log-out and token refresh support with an external Identity Provider
* Web UI: dequeue button near a job's status on the status page, if the authenticated
  user has sufficient authorization
* autohold button near a job's build result on the builds page, if the authenticated
  user has sufficient authorization
* reenqueue button near a buildset on a buildsets page, if the authenticated user
  has sufficient authorization

Dependencies
============

* This implementation will use an existing dependency to **pyJWT** in Zuul.
* A new dependency to **jsonpath-rw** will be added to support XPath-like parsing
  of complex claims.
