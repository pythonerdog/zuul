# Copyright 2024 BMW Group
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

from zuul.model import (
    NodesetInfo,
    NodesetRequest,
    ProviderNode,
    STATE_IN_USE,
    STATE_READY,
    STATE_USED,
)
from zuul.lib import tracing
from zuul.lib.logutil import get_annotated_logger
from zuul.zk.zkobject import ZKContext

from kazoo.exceptions import NoNodeError
from opentelemetry import trace


class LauncherClient:
    log = logging.getLogger("zuul.LauncherClient")
    tracer = trace.get_tracer("zuul")

    def __init__(self, zk_client, stop_event):
        self.zk_client = zk_client
        self.stop_event = stop_event

    def requestNodeset(self, item, job, priority, relative_priority,
                       preferred_provider):
        log = get_annotated_logger(self.log, item.event)
        labels = [n.label for n in job.nodeset.getNodes()]

        buildset = item.current_build_set
        parent_span = tracing.restoreSpan(buildset.span_info)
        request_time = time.time()
        with trace.use_span(parent_span):
            request_span = self.tracer.start_span(
                "NodesetRequest", start_time=request_time)
        span_info = tracing.getSpanInfo(request_span)

        with self.createZKContext(None, self.log) as ctx:
            request = NodesetRequest.new(
                ctx,
                state=self._getInitialRequestState(job),
                tenant_name=item.manager.tenant.name,
                pipeline_name=item.manager.pipeline.name,
                buildset_uuid=buildset.uuid,
                job_uuid=job.uuid,
                job_name=job.name,
                labels=labels,
                priority=priority,
                _relative_priority=relative_priority,
                request_time=request_time,
                zuul_event_id=item.event.zuul_event_id,
                span_info=span_info,
            )
            log.info("Submitted nodeset request %s", request)
        return request

    def reviseRequest(self, request, relative_priority):
        log = get_annotated_logger(self.log, request)
        try:
            with self.createZKContext(None, self.log) as ctx:
                request.revise(ctx, relative_priority=relative_priority)
            log.info("Revised nodeset request %s; relative_priority=%s",
                     request, relative_priority)
        except NoNodeError:
            pass

    def getRequest(self, request_id):
        try:
            with self.createZKContext(None, self.log) as ctx:
                return NodesetRequest.fromZK(ctx, path=None, uuid=request_id)
        except NoNodeError:
            return None

    def deleteRequest(self, request):
        try:
            with self.createZKContext(None, self.log) as ctx:
                request.delete(ctx)
        except NoNodeError:
            pass

    def getNodesetInfo(self, request):
        # TODO: populated other nodeset info fields
        return NodesetInfo(
            nodes=list(request.nodes),
            zone=request.executor_zones[0])

    def acceptNodeset(self, request, nodeset):
        log = get_annotated_logger(self.log, request)
        log.debug("Accepting nodeset for request %s", request)
        try:
            with self.createZKContext(None, self.log) as ctx:
                for node_id, node in zip(
                    request.nodes, nodeset.getNodes()
                ):
                    provider_node = ProviderNode.fromZK(
                        ctx, path=ProviderNode._getPath(node_id))
                    node.updateFromDict({
                        "state": STATE_READY,
                        **provider_node.getNodeData()
                    })
                    node._provider_node = provider_node
                    log.debug("Locking node %s", provider_node)
                    if not provider_node.acquireLock(ctx):
                        raise Exception(f"Failed to lock node {provider_node}")
        except Exception:
            self.returnNodeset(nodeset)
            raise
        finally:
            self.deleteRequest(request)

    def useNodeset(self, nodeset, zuul_event_id=None):
        log = get_annotated_logger(self.log, zuul_event_id)
        log.info("Setting nodeset %s in use", nodeset)
        for node in nodeset.getNodes():
            provider_node = getattr(node, "_provider_node", None)
            if not provider_node:
                raise Exception("No associated provider node for %s", node)
            if not provider_node.hasLock():
                raise Exception("Provider node %s is not locked",
                                provider_node)
            node.state = STATE_IN_USE
            with self.createZKContext(provider_node._lock, log) as ctx:
                provider_node.updateAttributes(
                    ctx, state=ProviderNode.State.IN_USE)

    def returnNodeset(self, nodeset, zuul_event_id=None):
        log = get_annotated_logger(self.log, zuul_event_id)
        log.debug("Returning nodeset %s", nodeset)
        for node in nodeset.getNodes():
            provider_node = getattr(node, "_provider_node", None)
            if not provider_node:
                continue
            with self.createZKContext(provider_node._lock, log) as ctx:
                try:
                    node.state = STATE_USED
                    provider_node.updateAttributes(
                        ctx, state=ProviderNode.State.USED)
                    log.debug("Released %s", provider_node)
                except Exception:
                    log.exception("Unable to return node %s", provider_node)
                finally:
                    try:
                        provider_node.releaseLock(ctx)
                    except Exception:
                        log.exception("Error unlocking node %s", provider_node)

    def createZKContext(self, lock, log):
        return ZKContext(self.zk_client, lock, self.stop_event, log)

    def _getInitialRequestState(self, job):
        return (NodesetRequest.State.REQUESTED if job.nodeset.nodes
                else NodesetRequest.State.FULFILLED)
