Use Matrix for Chat
===================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

We just switched IRC networks from Freenode to OFTC.  This was
done quickly because remaining on Freenode was untenable due to recent
changes, and the OpenDev community had an existing plan prepared to
move to OFTC should such a situation arise.

Now that the immediate issue is addressed, we can take a considered
approach to evaluating whether an alternative to IRC such as Matrix
would be more suited.

Requirements
------------

Here are some concerns that affect us as a community:

* Some users like to stay connected all the time so they can read
  messages from when they are away.

* Others are only interested in connecting when they have something to
  say.

* On Freenode, nick registration was required to join #zuul in order
  to mitigate spam.  It is unclear whether the same will be true for
  OFTC.

* Some users prefer simple text-based clients.

* Others prefer rich messaging and browser or mobile clients.

* We rely heavily on gerritbot.

* We use the logs recorded by eavesdrop from time to time.

* We benefit from the OpenDev statusbot.

* We collaborate with a large number of people in the OpenDev
  community in various OFTC channels.  We also collaborate with folks
  in Ansible and other communities in libera.chat channels.

* Users must be able to access our chat using Free and Open-Source
  Software.

* The software running the chat system itself should be Free and
  Open-Source as well if possible.  Both of these are natural
  extensions of the Open Infrastructure community's Four Opens, as
  well as OpenDev's mantra that Free Software needs Free Tools.

Benefits Offered by Matrix
--------------------------

* The Matrix architecture associates a user with a "homeserver", and
  that homeserver is responsible for storing messages in all of the
  rooms the user is present.  This means that every Matrix user has
  the ability to access messages received while their client is
  disconnected.  Users don't need to set up separate "bouncers".

* Authentication happens with the Matrix client and homeserver, rather
  than through a separate nickserv registration system.  This process
  is familiar to all users of web services, so should reduce barriers
  to access for new users.

* Matrix has a wide variety of clients available, including the
  Element web/desktop/mobile clients, as well as the weechat-matrix
  plugin.  This addresses users of simple text clients and rich media.

* Bots are relatively simple to implement with Matrix.

* The Matrix community is dedicated to interoperability.  That drives
  their commitment to open standards, open source software, federation
  using Matrix itself, and bridging to other communities which
  themselves operate under open standards.  That aligns very well with
  our four-opens philosophy, and leads directly to the next point:

* Bridges exist to OFTC, libera.chat, and, at least for the moment,
  Freenode.  That means that any of our users who have invested in
  establishing a presence in Matrix can relatively easily interact
  with communities who call those other networks home.

* End-to-end encrypted channels for private chats.  While clearly the
  #zuul channel is our main concern, and it will be public and
  unencrypted, the ability for our community members to have ad-hoc
  chats about sensitive matters (such as questions which may relate to
  security) is a benefit.  If Matrix becomes more widely used such
  that employees of companies feel secure having private chats in the
  same platform as our public community interactions, we all benefit
  from the increased availability and accessibility of people who no
  longer need to split their attention between multiple platforms.

Reasons to Move
---------------

We could continue to call the #zuul channel on OFTC home, and
individual users could still use Matrix on their own to obtain most of
those benefits by joining the portal room on the OFTC matrix.org
bridge.  The reasons to move to a native Matrix room are:

* Eliminate a potential failure point.  If many/most of us are
  connected via Matrix and the bridge, then either a Matrix or an OFTC
  outage would affect us.

* Eliminate a source of spam.  Spammers find IRC networks very easy to
  attack.  Matrix is not immune to this, but it is more difficult.

* Isolate ourselves from OFTC-related technology or policy changes.
  For example, if we find we need to require registration to speak in
  channel, that would take us back to the state where we have to teach
  new users about nick registration.

* Elevating the baseline level of functionality expected from our chat
  platform.  By saying that our home is Matrix, we communicate to
  users that the additional functionality offered by the platform is
  an expected norm.  Rather than tailoring our interactions to the
  lowest-common-denominator of IRC, we indicate that the additional
  features available in Matrix are welcomed.

* Provide a consistent and unconfusing message for new users.  Rather
  than saying "we're on OFTC, use Matrix to talk to us for a better
  experience", we can say simply "use Matrix".

* Lead by example.  Because of the recent fragmentation in the Free
  and Open-Source software communities, Matrix is a natural way to
  frictionlessly participate in a multitude of communities.  Let's
  show people how that can work.

Reasons to Stay
---------------

All of the work to move to OFTC has been done, and for the moment at
least, the OFTC matrix.org bridge is functioning well.  Moving to a
native room will require some work.

Implementation Plan
-------------------

To move to a native Matrix room, we would do the following:

* Create a homeserver to host our room and bots.  Technically, this is
  not necessary, but having a homeserver allows us more control over
  the branding, policy, and technology of our room.  It means we are
  isolated from policy decisions by the admins of matrix.org, and it
  fully utilizes the federated nature of the technology.

  We should ask the OpenDev collaboratory to host a homeserver for
  this purpose.  That could either be accomplished by running a
  synapse server on a VM in OpenDev's infrastructure, or the
  Foundation could subscribe to a hosted server run by Element.

  At this stage, we would not necessarily host any user accounts on
  the homeserver; it would only be used for hosting rooms and bot
  accounts.

  The homeserver would likely be for opendev.org; so our room would be
  #zuul:opendev.org, and we might expect bot accounts like
  @gerrit:opendev.org.

  The specifics of this step are out of scope for this document.  To
  accomplish this, we will start an OpenDev spec to come to agreement
  on the homeserver.

* Ensure that the OpenDev service bots upon which we rely (gerrit, and
  status) support matrix.  This is also under the domain of OpenDev;
  but it is a pre-requisite for us to move.

  We also rely somewhat on eavesdrop.  Matrix does support searching,
  but that doesn't cause it to be indexed by search engines, and
  searching a decade worth of history may not work as well, so we
  should also include eavesdrop in that list.

  OpenDev also runs a meeting bot, but we haven't used it in years.

* Create the #zuul room.

* Create instructions to tell users how to join it.  We will recommend
  that if they do not already have a Matrix homeserver, they register
  with matrix.org.

* Announce the move, and retire the OFTC channel.

Potential Future Enhancements
-----------------------------

Most of this is out of scope for the Zuul community, and instead
relates to OpenDev, but we should consider these possibilities when
weighing our decision.

It would be possible for OpenDev and/or the Foundation to host user
accounts on the homeserver.  This might be more comfortable for new
users who are joining Matrix at the behest of our community.

If that happens, user accounts on the homeserver could be tied to a
future OpenDev single-sign-on system, meaning that registration could
become much simpler and be shared with all OpenDev services.

It's also possible for OpenDev and/or the Foundation to run multiple
homeservers in multiple locations in order to aid users who may live
in jurisdictions with policy or technical requirements that prohibit
their accessing the matrix.org homeserver.

All of these, if they come to pass, would be very far down the road,
but they do illustrate some of the additional flexibility our
communities could obtain by using Matrix.
