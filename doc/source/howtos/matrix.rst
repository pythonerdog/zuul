Chatting with Matrix
====================

The Zuul community uses mailing lists for long-form communication and
Matrix for real-time (or near real-time) chat.

This guide will walk you through getting started with Matrix and how
to use it to join communities like Zuul on IRC.

Familiar with Matrix already and want to jump straight to the room?
Follow this link: `https://matrix.to/#/#zuul:opendev.org <https://matrix.to/#/#zuul:opendev.org>`_

Why Use Matrix?
---------------

Matrix has a number of clients available including feature-rich web,
desktop and mobile clients, as well as integration with the popular
text-based weechat client.  This provides plenty of choices based on
your own preference.  This guide will focus on using the Element web
client.

Matrix supports persistent presence in "rooms".  Once you join a room,
your homeserver will keep you connected to that room and save all of
the messages sent to it, so that if you close your client and return
later, you won't miss anything.  You don't need to run your own server
to use Matrix; you are welcome to use the public server at matrix.org.
But if you are a member of an organization that already runs a
homeserver, or you would like to run one yourself, you may do so and
federate with the larger Matrix network.  This guide will walk you
through setting up an account on the matrix.org homeserver.

Matrix is an open (in every sense of the word) federated communication
system.  Because of this it's possible to bridge the Matrix network to
other networks (including IRC, slack, etc).  That makes it the perfect
system to use to communicate with various communities using a single
interface.

Create An Account
-----------------

If you don't already have an account on a Matrix homeserver, go to
https://app.element.io/ to create one, then click `Create Account`.

.. image:: /images/matrix/account-welcome.png
   :align: center

You can create an account with an email address or one of the
supported authentication providers.

.. image:: /images/matrix/account-create.png
   :align: center

You'll be asked to accept the terms and conditions of the service.

.. image:: /images/matrix/account-accept.png
   :align: center

If you are registering an account via email, you will be prompted to
verify your email address.

.. image:: /images/matrix/account-verify.png
   :align: center

You will receive an email like this:

.. image:: /images/matrix/account-verify-email.png
   :align: center

Once you click the link in the email, your account will be created.

.. image:: /images/matrix/account-success.png
   :align: center

You can follow the link to sign in.

.. image:: /images/matrix/account-signin.png
   :align: center

Join the #zuul Room
-------------------

Click the plus icon next to `Rooms` on the left of the screen, then
click `Explore public rooms` in the dropdown that appears.

.. image:: /images/matrix/account-rooms-dropdown.png
   :align: center

A popup dialog will appear; enter ``#zuul:opendev.org`` into the
search box.

.. image:: /images/matrix/account-rooms-zuul.png
   :align: center

It will display `No results for "#zuul:opendev.org"` since the room is
hosted on a federated homeserver, but it's really there.  Disregard
that and hit `enter` or click `Join`, and you will join the room.

Go ahead and say hi, introduce yourself, and let us know what you're
working on or any questions you have.  Keep in mind that the Zuul
community is world-wide and we may be away from our desks when you
join.  Because Matrix keeps a message history, we'll see your message
and you'll see any responses, even if you close your browser and log
in later.

Optional Next Steps
-------------------

The following steps are optional.  You don't need to do these just to
hop in with a quick question, but if you plan on spending more than a
brief amount of time interacting with communities in Matrix, they will
improve your experience.

.. toctree::
   :maxdepth: 1

   matrix-encryption
   matrix-id
   matrix-irc
