Configuring Google Authentication
=================================

This document explains how to configure Zuul in order to enable authentication
with Google.

Prerequisites
-------------

* The Zuul instance must be able to query Google's OAUTH API servers. This
  simply generally means that the Zuul instance must be able to send and
  receive HTTPS data to and from the Internet.
* You must set up a project in `Google's developers console <https://console.developers.google.com/>`_.

Setting up credentials with Google
----------------------------------

In the developers console, choose your project and click `APIs & Services`.

Choose `Credentials` in the menu on the left, then click `Create Credentials`.

Choose `Create OAuth client ID`. You might need to configure a consent screen first.

Create OAuth client ID
......................

Choose `Web application` as Application Type.

In `Authorized JavaScript Origins`, add the base URL of Zuul's Web UI. For example,
if you are running a yarn development server on your computer, it would be
`http://localhost:3000` .

In `Authorized redirect URIs`, write down the base URL of Zuul's Web UI followed
by "/t/<tenant>/auth_callback", for each tenant on which you want to enable
authentication. For example, if you are running a yarn development server on
your computer and want to set up authentication for tenant "local",
write `http://localhost:3000/t/local/auth_callback` .

Click Save. Google will generate a Client ID and a Client secret for your new
credentials; we will only need the Client ID for the rest of this How-To.

Configure Zuul
..............

Edit the ``/etc/zuul/zuul.conf`` to add the google authenticator:

.. code-block:: ini

   [auth google_auth]
   default=true
   driver=OpenIDConnect
   realm=my_realm
   issuer_id=https://accounts.google.com
   client_id=<your Google Client ID>


Restart Zuul services (scheduler, web).

Head to your tenant's status page. If all went well, you should see a "Sign in"
button in the upper right corner of the page. Congratulations!

Further Reading
---------------

This How-To is based on `Google's documentation on their implementation of OpenID Connect <https://developers.google.com/identity/protocols/oauth2/openid-connect>`_.
