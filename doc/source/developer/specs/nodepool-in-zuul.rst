Nodepool in Zuul
================

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

The following specification describes a plan to move Nodepool's
functionality into Zuul and end development of Nodepool as a separate
application.  This will allow for more node and image related features
as well as simpler maintenance and deployment.

Introduction
------------

Nodepool exists as a distinct application from Zuul largely due to
historical circumstances: it was originally a process for launching
nodes, attaching them to Jenkins, detaching them from Jenkins and
deleting them.  Once Zuul grew its own execution engine, Nodepool
could have been adopted into Zuul at that point, but the existing
loose API meant it was easy to maintain them separately and combining
them wasn't particularly advantageous.

However, now we find ourselves with a very robust framework in Zuul
for dealing with ZooKeeper, multiple components, web services and REST
APIs.  All of these are lagging behind in Nodepool, and it is time to
address that one way or another.  We could of course upgrade
Nodepool's infrastructure to match Zuul's, or even separate out these
frameworks into third-party libraries.  However, there are other
reasons to consider tighter coupling between Zuul and Nodepool, and
these tilt the scales in favor of moving Nodepool functionality into
Zuul.

Designing Nodepool as part of Zuul would allow for more features
related to Zuul's multi-tenancy.  Zuul is quite good at
fault-tolerance as well as scaling, so designing Nodepool around that
could allow for better cooperation between node launchers.  Finally,
as part of Zuul, Nodepool's image lifecycle can be more easily
integrated with Zuul-based workflow.

There are two Nodepool components: nodepool-builder and
nodepool-launcher.  We will address the functionality of each in the
following sections on Image Management and Node Management.

This spec contemplates a new Zuul component to handle image and node
management: zuul-launcher.  Much of the Nodepool configuration will
become Zuul configuration as well.  That is detailed in its own
section, but for now, it's enough to know that the Zuul system as a
whole will know what images and node labels are present in the
configuration.

Image Management
----------------

Part of nodepool-builder's functionality is important to have as a
long-running daemon, and part of what it does would make more sense as
a Zuul job.  By moving the actual image build into a Zuul job, we can
make the activity more visible to users of the system.  It will be
easier for users to test changes to image builds (inasmuch as they can
propose a change and a check job can run on that change to see if the
image builds sucessfully).  Build history and logs will be visible in
the usual way in the Zuul web interface.

A frequently requested feature is the ability to verify images before
putting them into service.  This is not practical with the current
implementation of Nodepool because of the loose coupling with Zuul.
However, once we are able to include Zuul jobs in the workflow of
image builds, it is easier to incorporate Zuul jobs to validate those
images as well.  This spec includes a mechanism for that.

The parts of nodepool-builder that makes sense as a long-running
daemon are the parts dealing with image lifecycles.  Uploading builds
to cloud providers, keeping track of image builds and uploads,
deciding when those images should enter or leave service, and deleting
them are all better done with state management and long-running
processes (we should know -- early versions of Nodepool attempted to
do all of that with Jenkins jobs with limited success).

The sections below describe how we will implement image management in
Zuul.

First, a reminder that using custom images is optional with Zuul.
Many Zuul systems will be able to operate using only stock cloud
provider images.  One of the strengths of nodepool-builder is that it
can build an image for Zuul without relying on any particular cloud
provider images.  A Zuul system whose operator wants to use custom
images will need to bootstrap that process, and under the proposed
system where images are build in Zuul jobs, that would need to be done
using a stock cloud image.  In other words, to bootstrap a system such
as OpenDev from scratch, the operators would need to use a stock cloud
image to run the job to build the custom image.  Once a custom image
is available, further image builds could be run on either the stock
cloud image or the custom image.  That decision is left to the
operator and involves consideration of fault tolerance and disaster
recovery scenarios.

To build a custom image, an operator will define a fairly typical Zuul
job for each image they would like to produce.  For example, a system
may have one job to build a debian-stable image, a second job for
debian-unstable, a third job for ubuntu-focal, a fourth job for
ubuntu-jammy.  Zuul's job inheritance system could be very useful here
to deal with many variations of a similar process.

Currently nodepool-builder will build an image under three
circumstances: 1) the image (or the image in a particular format) is
missing; 2) a user has directly requested a build; 3) on an automatic
interval (typically daily).  To map this into Zuul, we will use Zuul's
existing pipeline functionality, but we will add a new trigger for
case #1.  Case #2 can be handled by a manual Zuul enqueue command, and
case #3 by a periodic pipeline trigger.

Since Zuul knows what images are configured and what their current
states are, it will be able to emit trigger events when it detects
that a new image (or image format) has been added to its
configuration.  In these cases, the `zuul` driver in Zuul will enqueue
an `image-build` trigger event on startup or reconfiguration for every
missing image.  The event will include the image name.  Pipelines will
be configured to trigger on `image-build` events as well as on a timer
trigger.

Jobs will include an extra attribute to indicate they build a
particular image.  This serves two purposes; first, in the case of an
`image-build` trigger event, it will act as a matcher so that only
jobs matching the image that needs building are run.  Second, it will
allow Zuul to determine which formats are needed for that image (based
on which providers are configured to use it) and include that
information as job data.

The job will be responsible for building the image and uploading the
result to some storage system.  The URLs for each image format built
should be returned to Zuul as artifacts.

Finally, the `zuul` driver reporter will accept parameters which will
tell it to search the result data for these artifact URLs and update
the internal image state accordingly.

An example configuration for a simple single-stage image build:

.. code-block:: yaml

   - pipeline:
       name: image
       trigger:
         zuul:
           events:
             - image-build
         timer:
           time: 0 0 * * *
       success:
         zuul:
           image-built: true
           image-validated: true

   - job:
       name: build-debian-unstable-image
       image-build-name: debian-unstable

This job would run whenever Zuul determines it needs a new
debian-unstable image or daily at midnight.  Once the job completes,
because of the ``image-built: true`` report, it will look for artifact
data like this:

.. code-block:: yaml

  artifacts:
    - name: raw image
      url: https://storage.example.com/new_image.raw
      metadata:
        type: zuul_image
        image_name: debian-unstable
        format: raw
    - name: qcow2 image
      url: https://storage.example.com/new_image.qcow2
      metadata:
        type: zuul_image
        image_name: debian-unstable
        format: qcow2

Zuul will update internal records in ZooKeeper for the image to record
the storage URLs.  The zuul-launcher process will then start
background processes to download the images from the storage system
and upload them to the configured providers (much as nodepool-builder
does now with files on disk).  As a special case, it may detect that
the image files are stored in a location that a provider can access
directly for import and may be able to import directly from the
storage location rather than downloading locally first.

To handle image validation, a flag will be stored for each image
upload indicating whether it has been validated.  The example above
specifies ``image-validated: true`` and therefore Zuul will put the
image into service as soon as all image uploads are complete.
However, if it were false, then Zuul would emit an `image-validate`
event after each upload is complete.  A second pipeline can be
configured to perform image validation.  It can run any number of
jobs, and since Zuul has complete knowledge of image states, it will
supply nodes using the new image upload (which is not yet in service
for normal jobs).  An example of this might look like:

.. code-block:: yaml

   - pipeline:
       name: image-validate
       trigger:
         zuul:
           events:
             - image-validate
       success:
         zuul:
           image-validated: true

   - job:
       name: validate-debian-unstable-image
       image-build-name: debian-unstable
       nodeset:
         nodes:
           - name: node
             label: debian

The label should specify the same image that is being validated.  Its
node request will be made with extra specifications so that it is
fulfilled with a node built from the image under test.  This process
may repeat for each of the providers using that image (normal pipeline
queue deduplication rules may need a special case to allow this).
Once the validation jobs pass, the entry in ZooKeeper will be updated
and the image will go into regular service.

A more specific process definition follows:

After a buildset reports with ``image-built: true``, Zuul will scan
result data and for each artifact it finds, it will create an entry in
ZooKeeper at `/zuul/images/<image_name>/<uuid>`.  Zuul will know
not to emit any more `image-build` events for that image at this
point.

For every provider using that image, Zuul will create an entry in
ZooKeeper at
`/zuul/image-uploads/<image_name>/<image_number>/provider/<provider_name>`.
It will set the remote image ID to null and the `image-validated` flag
to whatever was specified in the reporter.

Whenever zuul-launcher observes a new `image-upload` record without an
ID, it will:

* Lock the whole image
* Lock each upload it can handle
* Unlocks the image while retaining the upload locks
* Downloads artifact (if needed) and uploads images to provider
* If upload requires validation, it enqueues an `image-validate` zuul driver trigger event
* Unlocks upload

The locking sequence is so that a single launcher can perform multiple
uploads from a single artifact download if it has the opportunity.

Once more than two builds of an image are in service, the oldest is
deleted.  The image ZooKeeper record set to the `deleting` state.
Zuul-launcher will delete the uploads from the providers.  The `zuul`
driver emits an `image-delete` event with item data for the image
artifact.  This will trigger an image-delete job that can delete the
artifact from the cloud storage.

All of these pipeline definitions should typically be in a single
tenant (but need not be), but the images they build are potentially
available to each tenant that includes the image definition
configuration object (see the Configuration section below).  Any repo
in a tenant with an image build pipeline will be able to cause images
to be built and uploaded to providers.

Snapshot Images
~~~~~~~~~~~~~~~

Nodepool does not currently support snapshot images, but the spec for
the current version of Nodepool does contemplate the possibility of a
snapshot based nodepool-builder process.  Likewise, this spec does not
require us to support snapshot image builds, but in case we want to
add support in the future, we should have a plan for it.

The image build job in Zuul could, instead of running
diskimage-builder, act on the remote node to prepare it for a
snapshot.  A special job attribute could indicate that it is a
snapshot image job, and instead of having the zuul-launcher component
delete the node at the end of the job, it could snapshot the node and
record that information in ZooKeeper.  Unlike an image-build job, an
image-snapshot job would need to run in each provider (similar to how
it is proposed that an image-validate job will run in each provider).
An image-delete job would not be required.


Node Management
---------------

The techniques we have developed for cooperative processing in Zuul
can be applied to the node lifecycle.  This is a good time to make a
significant change to the nodepool protocol.  We can achieve several
long-standing goals:

* Scaling and fault-tolerance: rather than having a 1:N relationship
  of provider:nodepool-launcher, we can have multiple zuul-launcher
  processes, each of which is capable of handling any number of
  providers.

* Parallel processing without explicit coordination: a single launcher might
  not be able to fully utilize a provider due to e.g. CPU or I/O constraints;
  by having multiple launchers processing requests for a provider, we can
  better use the available cloud resources.

* More intentional request fulfillment: almost no intelligence goes
  into selecting which provider will fulfill a given node request; by
  assigning providers intentionally, we can more efficiently utilize
  providers.

* Fulfilling node requests from multiple providers: by designing
  zuul-launcher for cooperative work, we can have nodesets that
  request nodes which are fulfilled by different providers.  Generally
  we should favor the same provider for a set of nodes (since they may
  need to communicate over a LAN), but if that is not feasible,
  allowing multiple providers to fulfill a request will permit
  nodesets with diverse node types (e.g., VM + static, or VM +
  container).

Zuul-launcher will need to know about every connection in the system
so that it may have a full copy of the configuration, but operators
may wish to localize launchers to specific clouds.  To support this,
zuul-launcher will take an optional command-line argument to indicate
on which connections it should operate.

Each zuul-launcher process will execute a number of processing loops
in series; first a global request processing loop, and then a
processing loop for each configured provider.

Requests and nodes will be considered by a launcher based on a calculated
score. For that we will use `Rendezvous/HRW (highest random weight) hashing
<https://en.wikipedia.org/wiki/Rendezvous_hashing>`_ to build a priority list of
candidate launchers. The launcher with the highest score will lock and process
a request or node.

The the hash will consist of the unique launcher indentifiers (e.g. the
hostnames from the component registry) and the UUID of the request or node. The
choosen hash function here needs to  be fast and doesn't have to be a
cryptographic hash function (e.g MurmurHash).

With this approach nodes/requests are essentially sharded between the available
launchers, making explicit coordination mostly unnecessary. By that we can also
avoid thundering herd effects and lock races that are observed in Nodepool
today.

The following edge cases need to be considered with this approach:

* When a new launcher starts up it won't process any locked nodes/requests,
  even though it might have a higher score than existing launchers.

* When a launcher is shut down the node/request is unlocked and the remaining
  launchers must decide based on the score who should continue with the
  node/request.

Currently a node request as a whole may be declined by providers.  We
will make that more granular and store information about each node in
the request (in other words, individual nodes may be declined by
providers).

All drivers for providers should implement the state machine
interface.  Any state machine information currently storen in memory
in nodepool-launcher will need to move to ZooKeeper so that other
launchers can resume state machine processing.

The individual provider loop will:

* Iterate over every matching node (highest score) assigned to that provider in
  `requested` state

  * If the node is locked by another launcher, continue with the next one
  * Lock the node (if not already locked) and set state to `building`
  * Drive the state machine
  * If success, update request
  * If failure, determine if it's a temporary or permanent failure
    and update the request accordingly
  * If quota available, unpause provider (if paused)

The global queue process will:

* Iterate over every matching node request (highest score), and every node
  within that request

  * If the request is locked by another launcher, continue with the next one
  * Lock the request (if not already locked)
  * If all providers have failed the request, clear all temp failures
  * If all providers have permanently failed the request, return error
  * Identify providers capable of fulfilling the request
  * Assign nodes to any provider with sufficient quota
  * If no providers with sufficient quota, assign it to first (highest
    priority) provider that can fulfill it later and pause that
    provider


Quota Handling & Rate Limiting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Due to additional the level of parallelization we need to consider quota
handling (provider and tenant) as well as provider rate limits.

The Nodepool launcher implementation as it is today will check whether there is
any remaining quota independently for each node request. Quota calculations are
based on cached information about existing nodes. This means that concurrently
processed requests in different provider pools (Nodepool only supports one
launcher per provider) will not consider each other's resource usage and there
might also be a small delay until new nodes show up in the cache.

The same is true for the tenant quota that considers resources used by
all providers.

With the new launcher architecture, the main difference will be that the
possibility for quota races increases when scaling up the number launcher
instances (more requests are processed in parallel).

This means that we have to relax the provider quota guarantees that we have in
Nodepool today. As a counter-measure we can calculate needed quota when
assigning a request to a provider as well as on the provider level before
actually acquiring resources. Additionally we can handled quota errors
gracefully by re-assigning the node to a different provider.

Rate limiting in Nodepool today works based on a rate-limiter with the
rate configured at the provider level. Multiple provider pools will
all respect the global provider rate limit. With multiple launchers for a
single provider we can no longer rely on a fixed provider rate limit.

Instead we need to handle rate-limits and API throttling in the respective
drivers and adjust the request rate dynamically based on e.g. API response
headers or errors.


Configuration
-------------

The configuration currently handled by Nodepool will be refactored and
added to Zuul's configuration syntax.  It will be loaded directly from
git repos like most Zuul configuration, however it will be
non-speculative (like pipelines and semaphores -- changes must merge
before they take effect).

Information about connecting to a cloud will be added to ``zuul.conf``
as a ``connection`` entry.  The rate limit setting will be moved to
the connection configuration.  Providers will then reference these
connections by name.

Because providers and images reference global (i.e., outside tenant
scope) concepts, ZooKeeper paths for data related to those should
include the canonical name of the repo where these objects are
defined.  For example, a `debian-unstable` image in the
`opendev/images` repo should be stored at
``/zuul/zuul-images/opendev.org%2fopendev%2fimages/``.  This avoids
collisions if different tenants contain different image objects with
the same name.

The actual Zuul config objects will be tenant scoped.  Image
definitions which should be available to a tenant should be included
in that tenant's config.  Again using the OpenDev example, the
hypothetical `opendev/images` repository should be included in every
OpenDev tenant so all of those images are available.

Within a tenant, image names must be unique (otherwise it is a tenant
configuration error, similar to a job name collision).

The diskimage-builder related configuration items will no longer be
necessary since they will be encoded in Zuul jobs.  This will reduce
the complexity of the configuration significantly.

The provider configuration will change as we take the opportunity to
make it more "Zuul-like".  Instead of a top-level dictionary, we will
use lists.  We will standardize on attributes used across drivers
where possible, as well as attributes which may be located at
different levels of the configuration.

The goals of this reorganization are:

* Allow projects to manage their own image lifecycle (if permitted by
  site administrators).
* Manage access control to labels, images and flavors via standard
  Zuul mechanisms (whether an item appears within a tenant).
* Reduce repetition and boilerplate for systems with many clouds,
  labels, or images.

The new configuration objects are:

Image
  This represents any kind of image (A Zuul image built by a job
  described above, or a cloud image).  By using one object to
  represent both, we open the possibility of having a label in one
  provider use a cloud image and in another provider use a Zuul image
  (because the label will reference the image by short-name which may
  resolve to a different image object in different tenants).  A given
  image object will specify what type it is, and any relevant
  information about it (such as the username to use, etc).

Flavor
  This is a new abstraction layer to reference instance types across
  different cloud providers.  Much like labels today, these probably
  won't have much information associated with them other than to
  reserve a name for other objects to reference.  For example, a site
  could define a `small` and a `large` flavor.  These would later be
  mapped to specific instance types on clouds.

Label
  Unlike the current Nodepool ``label`` definitions, these labels will
  also specify the image and flavor to use.  These reference the two
  objects above, which means that labels themselves contain the
  high-level definition of what will be provided (e.g., a `large
  ubuntu` node) while the specific mapping of what `large` and
  `ubuntu` mean are left to the more specific configuration levels.

Section
  This looks a lot like the current ``provider`` configuration in
  Nodepool (but also a little bit like a ``pool``).  Several parts of
  the Nodepool configuration (such as separating out availability
  zones from providers into pools) were added as an afterthought, and
  we can take the opportunity to address that here.

  A ``section`` is part of a cloud.  It might be a region (if a cloud
  has regions).  It might be one or more availability zones within a
  region.  A lot of the specifics about images, flavors, subnets,
  etc., will be specified here.  Because a cloud may have many
  sections, we will implement inheritance among sections.

Provider
  This is mostly a mapping of labels to sections and is similar to a
  provider pool in the current Nodepool configuration.  It exists as a
  separate object so that site administrators can restrict ``section``
  definitions to central repos and allow tenant administrators to
  control their own image and labels by allowing certain projects to
  define providers.

  It mostly consists of a list of labels, but may also include images.

When launching a node, relevant attributes may come from several
sources (the pool, image, flavor, or provider).  Not all attributes
make sense in all locations, but where we can support them in multiple
locations, the order of application (later items override earlier
ones) will be:

* ``image`` stanza
* ``flavor`` stanza
* ``label`` stanza
* ``section`` stanza (top level)
* ``image`` within ``section``
* ``flavor`` within ``section``
* ``provider`` stanza (top level)
* ``label`` within ``provider``

This reflects that the configuration is built upwards from general and
simple objects toward more specific objects image, flavor, label,
section, provider.  Generally speaking, inherited scalar values will
override, dicts will merge, lists will concatenate.

An example configuration follows.  First, some configuration which may
appear in a central project and shared among multiple tenants:

.. code-block:: yaml

   # Images, flavors, and labels are the building blocks of the
   # configuration.

   - image:
       name: centos-7
       type: zuul
       # Any other image-related info such as:
       # username: ...
       # python-path: ...
       # shell-type: ...
       # A default that can be overridden by a provider:
       # config-drive: true

   - image:
       name: ubuntu
       type: cloud

   - flavor:
       name: large

   - label:
       name: centos-7
       min-ready: 1
       flavor: large
       image: centos-7

   - label:
       name: ubuntu
       flavor: small
       image: ubuntu

   # A section for each cloud+region+az

   - section:
       name: rax-base
       abstract: true
       connection: rackspace
       boot-timeout: 120
       launch-timeout: 600
       key-name: infra-root-keys-2020-05-13
       # The launcher will apply the minimum of the quota reported by the
       # driver (if available) or the values here.
       quota:
         instances: 2000
       subnet: some-subnet
       tags:
         section-info: foo
       # We attach both kinds of images to providers in order to provide
       # image-specific info (like config-drive) or username.
       images:
         - name: centos-7
           config-drive: true
           # This is a Zuul image
         - name: ubuntu
           # This is a cloud image, so the specific cloud image name is required
           image-name: ibm-ubuntu-20-04-3-minimal-amd64-1
           # Other information may be provided
           # username ...
           # python-path: ...
           # shell-type: ...
       flavors:
         - name: small
           cloud-flavor: "Performance 8G"
         - name: large
           cloud-flavor: "Performance 16G"

   - section:
       name: rax-dfw
       parent: rax-base
       region: 'DFW'
       availability-zones: ["a", "b"]

   # A provider to indicate what labels are available to a tenant from
   # a section.

   - provider:
       name: rax-dfw-main
       section: rax-dfw
       labels:
         - name: centos-7
         - name: ubuntu
           key-name: infra-root-keys-2020-05-13
           tags:
             provider-info: bar

The following configuration might appear in a repo that is only used
in a single tenant:

.. code-block:: yaml

   - image:
       name: devstack
       type: zuul

   - label:
       name: devstack

   - provider:
       name: rax-dfw-devstack
       section: rax-dfw
       # The images can be attached to the provider just as a section.
       image:
         - name: devstack
           config-drive: true
       labels:
         - name: devstack

Here is a potential static node configuration:

.. code-block:: yaml

   - label:
       name: big-static-node

   - section:
       name: static-nodes
       connection: null
       nodes:
         - name: static.example.com
           labels:
             - big-static-node
           host-key: ...
           username: zuul

   - provider:
       name: static-provider
       section: static-nodes
       labels:
         - big-static-node

Each of the the above stanzas may only appear once in a tenant for a
given name (like pipelines or semaphores, they are singleton objects).
If they appear in more than one branch of a project, the definitions
must be identical; otherwise, or if they appear in more than one repo,
the second definition is an error.  These are meant to be used in
unbranched repos.  Whatever tenants they appear in will be permitted
to access those respective resources.

The purpose of the ``provider`` stanza is to associate labels, images,
and sections.  Much of the configuration related to launching an
instance (including the availability of zuul or cloud images) may be
supplied in the ``provider`` stanza and will apply to any labels
within.  The ``section`` stanza also allows configuration of the same
information except for the labels themselves.  The ``section``
supplies default values and the ``provider`` can override them or add
any missing values.  Images are additive -- any images that appear in
a ``provider`` will augment those that appear in a ``section``.

The result is a modular scheme for configuration, where a single
``section`` instance can be used to set as much information as
possible that applies globally to a provider.  A simple configuration
may then have a single ``provider`` instance to attach labels to that
section.  A more complex installation may define a "standard" pool
that is present in every tenant, and then tenant-specific pools as
well.  These pools will all attach to the same section.

References to sections, images and labels will be internally converted
to canonical repo names to avoid ambiguity.  Under the current
Nodepool system, labels are truly a global object, but under this
proposal, a label short name in one tenant may be different than one
in another.  Therefore the node request will internally specify the
canonical label name instead of the short name.  Users will never use
canonical names, only short names.

For static nodes, there is some repitition to labels: first labels
must be associated with the individual nodes defined on the section,
then the labels must appear again on a provider.  This allows an
operator to define a collection of static nodes centrally on a
section, then include tenant-specific sets of labels in a provider.
For the simple case where all static node labels in a section should
be available in a provider, we could consider adding a flag to the
provider to allow that (e.g., ``include-all-node-labels: true``).
Static nodes themselves are configured on a section with a ``null``
connection (since there is no cloud provider associated with static
nodes).  In this case, the additional ``nodes`` section attribute
becomes available.

Upgrade Process
---------------

Most users of diskimages will need to create new jobs to build these
images.  This proposal also includes significant changes to the node
allocation system which come with operational risks.

To make the transition as minimally disruptive as possible, we will
support both systems in Zuul, and allow for selection of one system or
the other on a per-label and per-tenant basis.

By default, if a nodeset specifies a label that is not defined by a
``label`` object in the tenant, Zuul will use the old system and place
a ZooKeeper request in ``/nodepool``.  If a matching ``label`` is
available in the tenant, The request will use the new system and be
sent to ``/zuul/node-requests``.  Once a tenant has completely
converted, a configuration flag may be set in the tenant configuration
and that will allow Zuul to treat nodesets that reference unknown
labels as configuration errors.  A later version of Zuul will remove
the backwards compatability and make this the standard behavior.

Because each of the systems will have unique metadata, they will not
recognize each others nodes, and it will appear to each that another
system is using part of their quota.  Nodepool is already designed to
handle this case (at least, handle it as well as possible).

Library Requirements
--------------------

The new zuul-launcher component will need most of Nodepool's current
dependencies, which will entail adding many third-party cloud provider
interfaces.  As of writing, this uses another 420M of disk space.
Since our primary method of distribution at this point is container
images, if the additional space is a concern, we could restrict the
installation of these dependencies to only the zuul-launcher image.

Diskimage-Builder Testing
-------------------------

The diskimage-builder project team has come to rely on Nodepool in its
testing process.  It uses Nodepool to upload images to a devstack
cloud, launch nodes from those instances, and verify that they
function.  To aid in continuity of testing in the diskimage-builder
project, we will extract the OpenStack image upload and node launching
code into a simple Python script that can be used in diskimage-builder
test jobs in place of Nodepool.

Work Items
----------

* In existing Nodepool convert the following drivers to statemachine:
  gce, kubernetes, openshift, openshift, openstack (openstack is the
  only one likely to require substantial effort, the others should be
  trivial)
* Replace Nodepool with an image upload script in diskimage-builder
  test jobs
* Add roles to zuul-jobs to build images using diskimage-builder
* Implement node-related config items in Zuul config and Layout
* Create zuul-launcher executable/component
* Add image-name item data
* Add image-build-name attribute to jobs
  * Including job matcher based on item image-name
  * Include image format information based on global config
* Add zuul driver pipeline trigger/reporter
* Add image lifecycle manager to zuul-launcher
  * Emit image-build events
  * Emit image-validate events
  * Emit image-delete events
* Add Nodepool driver code to Zuul
* Update zuul-launcher to perform image uploads and deletion
* Implement node launch global request handler
* Implement node launch provider handlers
* Update Zuul nodepool interface to handle both Nodepool and
  zuul-launcher node request queues
* Add tenant feature flag to switch between them
* Release a minor version of Zuul with support for both
* Remove Nodepool support from Zuul
* Release a major version of Zuul with only zuul-launcher support
* Retire Nodepool
