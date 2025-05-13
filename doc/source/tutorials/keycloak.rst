Keycloak Tutorial
=================

Zuul supports an authenticated API accessible via its web app which
can be used to perform some administrative actions.  To see this in
action, first run the :ref:`quick-start` and then follow the steps in
this tutorial to add a Keycloak server.

Zuul supports any identity provider that can supply a JWT using OpenID
Connect.  Keycloak is used here because it is entirely self-contained.
Google authentication is one additional option described elsewhere in
the documentation.

Gerrit can be updated to use the same authentication system as Zuul,
but this tutorial does not address that.

Update /etc/hosts
-----------------

The Zuul containers will use the internal container network to connect to
keycloak, but you will use a mapped port to access it in your web
browser.  There is no way to have Zuul use the internal hostname when
it validates the token yet redirect your browser to `localhost` to
obtain the token, therefore you will need to add a matching host entry
to `/etc/hosts`.  Make sure you have a line that looks like this:

.. code-block::

   127.0.0.1 localhost keycloak

If you are using podman, you need to add the following option in $HOME/.config/containers/containers.conf:

.. code-block::

   [containers]
   no_hosts=true

This way your /etc/hosts settings will not interfere with podman's networking.

Restart Zuul Containers
-----------------------

After completing the initial tutorial, stop the Zuul containers so
that we can update Zuul's configuration to add authentication.

.. code-block:: shell

   cd zuul/doc/source/examples
   podman-compose -p zuul-tutorial stop

Restart the containers with a new Zuul configuration.

.. code-block:: shell

   cd zuul/doc/source/examples
   ZUUL_TUTORIAL_CONFIG="./keycloak/etc_zuul/" podman-compose -p zuul-tutorial up -d

This tells podman-compose to use these Zuul `config files
<https://opendev.org/zuul/zuul/src/branch/master/doc/source/examples/keycloak>`_.

Start Keycloak
--------------

A separate docker-compose file is supplied to run Keycloak.  Start it
with this command:

.. code-block:: shell

   cd zuul/doc/source/examples/keycloak
   podman-compose -p zuul-tutorial-keycloak up -d

Once Keycloak is running, you can visit the web interface at
http://localhost:8082/

The Keycloak administrative user is `admin` with a password of
`kcadmin`.

Log Into Zuul
-------------

Visit http://localhost:9000/t/example-tenant/autoholds and click the
login icon on the top right.  You will be directed to Keycloak, where
you can log into the Zuul realm with the user `admin` and password
`admin`.

Once you return to Zuul, you should see the option to create an
autohold -- an admin-only option.
