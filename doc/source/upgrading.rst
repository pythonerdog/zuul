Upgrading
=========

Rolling Upgrades
----------------

If more than one of each Zuul component is present in a system, then
Zuul may be upgrading without downtime by performing a rolling
upgrade.  During a rolling upgrade, components are stopped and started
one at a time until all components are upgraded.  If there is a
behavior change during an upgrade, Zuul will typically wait until all
components are upgraded before changing behavior, but in some cases
when it is deemed safe, new behaviors may start to appear as soon as
the first component is upgraded.  Be sure not to begin using or rely
on new behaviors until all components are upgraded.

Unless specified in the release notes, there is no specific order for
which components should be upgraded first, but the following order is
likely to produce the least disruption and delay the use of new
behaviors until closer to the end of the process:

* Gracefully restart executors (one at a time, or as many as a
  system's over-allocation of resources will allow).
* Gracefully restart mergers.
* Restart schedulers.
* Restart web and finger gateways.

Skipping Versions
-----------------

Zuul versions are specified as `major.minor.micro`.  In general,
skipping minor or micro versions during upgrades is considered safe.
Skipping major versions is not recommended, as backwards compatibility
code for older systems may be removed during a major upgrade.  This
means that, for example, an upgrade from 5.x.y to 7.0.0 should include
at least an upgrade to 6.4.0 (the latest 6.x release) before
proceeding to 7.0.0.

If skipping major versions is required, then a rolling upgrade is not
possible, and Zuul should be completely stopped, and the ``zuul-admin
delete-state`` command should be run before restarting on the new
version.

Some versions may have unique upgrade requirements.  See release notes
for additional information about specific version upgrades.
