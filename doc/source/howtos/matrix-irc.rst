Optional: Join an IRC Room
==========================

The Matrix community maintains bridges to most major IRC networks.
You can use the same Matrix account and client to join IRC channels as
well as Zuul's Matrix Room.  You will benefit from the persistent
connection and history features as well.  Follow the instructions
below to join an IRC channel.  The example below is for the
``#opendev`` channel on OFTC, but the process is similar for other
channels or networks.

Click the plus icon next to the `Home` space on the left of the
screen, then click `Join public room` in the dropdown that appears.

.. image:: /images/matrix/account-rooms-dropdown.png
   :align: center

A popup dialog will appear where you can enter the name of the room to
join.  IRC channels are bridged to matrix with a special room name.
OFTC channels are prefixed with ``#_oftc_`` and suffixed with
``:matrix.org``.  To join the ``#opendev`` IRC channel, enter
``#_oftc_#opendev:matrix.org`` into the text field.

.. image:: /images/matrix/account-rooms-opendev.png
   :align: center

There will be no search results; an unfortunate consequence of one of
the anti-spam measures necessary on IRC.  Disregard that and hit
`enter` or click `Join #oftc_#opendev:matrix.org`, and you will join
the room.

If this is your first time joining an OFTC channel, you will also
receive an invitation to join the `OFTC IRC Bridge status` room.

.. image:: /images/matrix/account-rooms-invite.png
   :align: center

Accept the invitation.

.. image:: /images/matrix/account-rooms-accept.png
   :align: center

This is a private control channel between you and the system that
operates the OFTC bridge.  Here you can perform some IRC commands such
as changing your nickname and setting up nick registration.  That is
out of scope for this HOWTO, but advanced IRC users may be interested
in doing so.

You may repeat this procedure for any other IRC channels on the OFTC,
Freenode, or libera.chat networks.
