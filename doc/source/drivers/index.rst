.. _drivers:

Drivers
=======

Drivers may support any of the following functions:

* Sources -- hosts git repositories for projects.  Zuul can clone git
  repos for projects and fetch refs.
* Triggers -- emits events to which Zuul may respond.  Triggers are
  configured in pipelines to cause changes or other refs to be
  enqueued.
* Reporters -- outputs information when a pipeline is finished
  processing an item.

Zuul includes the following drivers:

.. toctree::
   :maxdepth: 2

   gerrit
   github
   pagure
   gitlab
   git
   mqtt
   elasticsearch
   smtp
   timer
   zuul
