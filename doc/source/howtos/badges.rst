:title: Badges

.. We don't need no stinking badges

.. _badges:

Badges
======

You can embed a badge declaring that your project is gated and therefore by
definition always has a working build. Since there is only one status to
report, it is a simple static file:

.. image:: https://zuul-ci.org/gated.svg
   :alt: Zuul: Gated

To use it, simply put ``https://zuul-ci.org/gated.svg`` into an RST or
markdown formatted README file, or use it in an ``<img>`` tag in HTML.

For advanced usage Zuul also supports generating dynamic badges via the
REST api. This can be useful if you want to display the status of e.g. periodic
pipelines of a project. To use it use an url like
``https://zuul.opendev.org/api/tenant/zuul/badge?project=zuul/zuul-website&pipeline=post``
instead of the above mentioned url. It supports filtering by ``project``,
``pipeline`` and ``branch``.
