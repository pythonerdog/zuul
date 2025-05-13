Optional: Save Encryption Keys
==============================

The Matrix protocol supports end-to-end encryption.  We don't have
this enabled for the ``#zuul`` room (there's little point as it's a
public room), but if you start direct chats with other Matrix users,
your communication will be encrypted by default.  Since it's
*end-to-end* encryption, that means your encryption keys are stored on
your client, and the server has no way to decrypt those messages.  But
that also means that if you sign out of your client or switch
browsers, you will lose your encryption keys along with access to any
old messages that were encrypted with them.  To avoid this, you can
back up your keys to the server (in an encrypted form, of course) so
that if you log in from another session, you can restore those keys
and pick up where you left off.  To set this up, open the User Menu by
clicking on your name at the top left of the screen.

.. image:: /images/matrix/user-menu.png
   :align: center

Click the `Security & privacy` menu item in the dropdown.

.. image:: /images/matrix/user-menu-dropdown.png
   :align: center

Click the `Set up` button under `Encryption` / `Secure Backup` in the
dialog that pops up.

.. image:: /images/matrix/user-encryption.png
   :align: center

Follow the prompts to back up your encryption keys.
