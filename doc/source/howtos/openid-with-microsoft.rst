Configuring Microsoft Authentication
====================================

This document explains how to configure Zuul in order to enable
authentication with Microsoft Login.

Prerequisites
-------------

* The Zuul instance must be able to query Microsoft's OAUTH API servers. This
  simply generally means that the Zuul instance must be able to send and
  receive HTTPS data to and from the Internet.
* You must have an Active Directory instance in Azure and the ability
  to create an App Registration.

By convention, we will assume Zuul's Web UI's base URL is
``https://zuul.example.com/``.

Creating the App Registration
-----------------------------

Navigate to the Active Directory instance in Azure and select `App
registrations` under ``Manage``.  Select ``New registration``.  This
will open a dialog to register an application.

Enter a name of your choosing (e.g., ``Zuul``), and select which
account types should have access.  Under ``Redirect URI`` select
``Single-page application(SPA)`` and enter
``https://zuul.example.com/auth_callback`` as the redirect URI.  Press
the ``Register`` button.

You should now be at the overview of the Zuul App registration.  This
page displays several values which will be used later.  Record the
``Application (client) ID`` and ``Directory (tenant) ID``.  When we need
to construct values including these later, we will refer to them with
all caps (e.g., ``CLIENT_ID`` and ``TENANT_ID`` respectively).

Select ``Authentication`` under ``Manage``.  You should see a
``Single-page application`` section with the redirect URI previously
configured during registration; if not, correct that now.

Under ``Implicit grant and hybrid flows`` select both ``Access
tokens`` and ``ID tokens``, then Save.

Back at the Zuul App Registration menu, select ``Expose an API``, then
press ``Set`` and then press ``Save`` to accept the default
Application ID URI (it should look like ``api://CLIENT_ID``).

Press ``Add a scope`` and enter ``zuul`` as the scope name.  Enter
``Access zuul`` for both the ``Admin consent display name`` and
``Admin consent description``.  Leave ``Who can consent`` set to
``Admins only``, then press ``Add scope``.

Optional: Include Groups Claim
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to include group information in the token sent to Zuul,
select ``Token configuration`` under ``Manage`` and then ``Add groups
claim``.


Setting up Zuul
---------------

Edit the ``/etc/zuul/zuul.conf`` to add the microsoft authenticator:

.. code-block:: ini

   [auth microsoft]
   default=true
   driver=OpenIDConnect
   realm=zuul.example.com
   authority=https://login.microsoftonline.com/TENANT_ID/v2.0
   issuer_id=https://sts.windows.net/TENANT_ID/
   client_id=CLIENT_ID
   scope=openid profile api://CLIENT_ID/zuul
   audience=api://CLIENT_ID
   load_user_info=false

Restart Zuul services (scheduler, web).

Head to your tenant's status page. If all went well, you should see a
`Sign in` button in the upper right corner of the
page. Congratulations!
