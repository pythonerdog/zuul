# Copyright 2016 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import time
from uuid import uuid4

from opentelemetry import trace

from zuul.driver import Driver, TriggerInterface, ReporterInterface
from zuul.driver.zuul.zuulmodel import ZuulTriggerEvent
from zuul.driver.zuul import (
    zuulmodel,
    zuultrigger,
    zuulreporter,
)
from zuul.lib.logutil import get_annotated_logger
from zuul.model import Change

PARENT_CHANGE_ENQUEUED = 'parent-change-enqueued'
PROJECT_CHANGE_MERGED = 'project-change-merged'
IMAGE_BUILD = 'image-build'
IMAGE_VALIDATE = 'image-validate'
IMAGE_DELETE = 'image-delete'


class ZuulDriver(Driver, TriggerInterface, ReporterInterface):
    name = 'zuul'
    log = logging.getLogger("zuul.ZuulTrigger")
    tracer = trace.get_tracer("zuul")

    def __init__(self):
        self.parent_change_enqueued_events = {}
        self.project_change_merged_events = {}

    def registerScheduler(self, scheduler):
        self.sched = scheduler

    def reconfigure(self, tenant):
        for manager in tenant.layout.pipeline_managers.values():
            for ef in manager.pipeline.event_filters:
                if not isinstance(ef.trigger, zuultrigger.ZuulTrigger):
                    continue
                if PARENT_CHANGE_ENQUEUED in ef._types:
                    # parent-change-enqueued events need to be filtered by
                    # pipeline
                    for pipeline_name in ef._pipelines:
                        key = (tenant.name, pipeline_name)
                        self.parent_change_enqueued_events[key] = True
                elif PROJECT_CHANGE_MERGED in ef._types:
                    self.project_change_merged_events[tenant.name] = True

    def onChangeMerged(self, tenant, change, source):
        # Called each time zuul merges a change
        if self.project_change_merged_events.get(tenant.name):
            span = trace.get_current_span()
            link_attributes = {"rel": "ChangeMerged"}
            link = trace.Link(span.get_span_context(),
                              attributes=link_attributes)
            attributes = {"event_type": PROJECT_CHANGE_MERGED}
            with self.tracer.start_as_current_span(
                    "ZuulEvent", links=[link], attributes=attributes):
                try:
                    self._createProjectChangeMergedEvents(change, source)
                except Exception:
                    self.log.exception(
                        "Unable to create project-change-merged events for "
                        "%s" % (change,))

    def onChangeEnqueued(self, tenant, change, manager, event):
        log = get_annotated_logger(self.log, event)

        # Called each time a change is enqueued in a pipeline
        tenant_events = self.parent_change_enqueued_events.get(
            (tenant.name, manager.pipeline.name))
        log.debug("onChangeEnqueued %s", tenant_events)
        if tenant_events:
            span = trace.get_current_span()
            link_attributes = {"rel": "ChangeEnqueued"}
            link = trace.Link(span.get_span_context(),
                              attributes=link_attributes)
            attributes = {"event_type": PARENT_CHANGE_ENQUEUED}
            with self.tracer.start_as_current_span(
                    "ZuulEvent", links=[link], attributes=attributes):
                try:
                    self._createParentChangeEnqueuedEvents(
                        change, manager, tenant, event)
                except Exception:
                    log.exception(
                        "Unable to create parent-change-enqueued events for "
                        "%s in %s" % (change, manager.pipeline))

    def _createProjectChangeMergedEvents(self, change, source):
        changes = source.getProjectOpenChanges(
            change.project)
        for open_change in changes:
            self._createProjectChangeMergedEvent(open_change)

    def _createProjectChangeMergedEvent(self, change):
        event = ZuulTriggerEvent()
        event.type = PROJECT_CHANGE_MERGED
        event.trigger_name = self.name
        event.connection_name = "zuul"
        event.project_hostname = change.project.canonical_hostname
        event.project_name = change.project.name
        event.change_number = change.number
        event.branch = change.branch
        event.change_url = change.url
        event.patch_number = change.patchset
        event.ref = change.ref
        event.zuul_event_id = str(uuid4().hex)
        event.timestamp = time.time()
        self.sched.addTriggerEvent(self.name, event)

    def _createParentChangeEnqueuedEvents(self, change, manager, tenant,
                                          event):
        log = get_annotated_logger(self.log, event)

        log.debug("Checking for changes needing %s:" % change)
        if not isinstance(change, Change):
            log.debug("  %s does not support dependencies" % type(change))
            return

        # This is very inefficient, especially on systems with large
        # numbers of github installations.  This can be improved later
        # with persistent storage of dependency information.
        needed_by_changes = set(
            manager.resolveChangeReferences(change.getNeededByChanges()))
        for source in self.sched.connections.getSources():
            log.debug("  Checking source: %s",
                      source.connection.connection_name)
            new_changes = source.getChangesDependingOn(change, None, tenant)
            log.debug("  Source %s found %s changes",
                      source.connection.connection_name,
                      len(new_changes))
            needed_by_changes.update(new_changes)
        log.debug("  Following changes: %s", needed_by_changes)

        for needs in needed_by_changes:
            self._createParentChangeEnqueuedEvent(needs, manager)

    def _createParentChangeEnqueuedEvent(self, change, manager):
        event = ZuulTriggerEvent()
        event.type = PARENT_CHANGE_ENQUEUED
        event.connection_name = "zuul"
        event.trigger_name = self.name
        event.pipeline_name = manager.pipeline.name
        event.project_hostname = change.project.canonical_hostname
        event.project_name = change.project.name
        event.change_number = change.number
        event.branch = change.branch
        event.change_url = change.url
        event.patch_number = change.patchset
        event.ref = change.ref
        event.zuul_event_id = str(uuid4().hex)
        event.timestamp = time.time()
        self.sched.addTriggerEvent(self.name, event)

    def getImageBuildEvent(self, image_names, project_hostname, project_name,
                           project_branch):
        event = ZuulTriggerEvent()
        event.type = IMAGE_BUILD
        event.connection_name = "zuul"
        event.trigger_name = self.name
        event.image_names = image_names
        event.project_hostname = project_hostname
        event.project_name = project_name
        event.branch = project_branch
        event.ref = f'refs/heads/{project_branch}'
        event.zuul_event_id = str(uuid4().hex)
        event.timestamp = time.time()
        event.arrived_at_scheduler_timestamp = event.timestamp
        return event

    def getImageValidateEvent(self, image_names, project_hostname,
                              project_name, project_branch,
                              image_upload_uuid):
        event = ZuulTriggerEvent()
        event.type = IMAGE_VALIDATE
        event.connection_name = "zuul"
        event.trigger_name = self.name
        event.image_names = image_names
        event.image_upload_uuid = image_upload_uuid
        event.project_hostname = project_hostname
        event.project_name = project_name
        event.branch = project_branch
        event.ref = f'refs/heads/{project_branch}'
        event.zuul_event_id = str(uuid4().hex)
        event.timestamp = time.time()
        event.arrived_at_scheduler_timestamp = event.timestamp
        return event

    def getImageDeleteEvent(self, image_names, project_hostname, project_name,
                            project_branch, image_build_uuid):
        event = ZuulTriggerEvent()
        event.type = IMAGE_DELETE
        event.connection_name = "zuul"
        event.trigger_name = self.name
        event.image_names = image_names
        event.image_build_uuid = image_build_uuid
        event.project_hostname = project_hostname
        event.project_name = project_name
        event.branch = project_branch
        event.ref = f'refs/heads/{project_branch}'
        event.zuul_event_id = str(uuid4().hex)
        event.timestamp = time.time()
        event.arrived_at_scheduler_timestamp = event.timestamp
        return event

    def getTrigger(self, connection, config=None):
        return zuultrigger.ZuulTrigger(self, config)

    def getTriggerSchema(self):
        return zuultrigger.getSchema()

    def getTriggerEventClass(self):
        return zuulmodel.ZuulTriggerEvent

    def getReporter(self, connection, pipeline, config=None,
                    parse_context=None):
        return zuulreporter.ZuulReporter(self, connection, pipeline, config)

    def getReporterSchema(self):
        return zuulreporter.getSchema()
