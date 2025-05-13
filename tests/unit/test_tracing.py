# Copyright 2022 Acme Gating, LLC
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

import time

from tests.base import iterate_timeout, ZuulTestCase

import zuul.lib.tracing as tracing
from opentelemetry import trace


def attributes_to_dict(attrlist):
    ret = {}
    for attr in attrlist:
        if attr.value.string_value:
            ret[attr.key] = attr.value.string_value
        else:
            ret[attr.key] = [v.string_value
                             for v in attr.value.array_value.values]
    return ret


class TestTracing(ZuulTestCase):
    config_file = 'zuul-tracing.conf'
    tenant_config_file = "config/single-tenant/main.yaml"

    def _waitForSpans(self, *span_names, timeout=60,):
        for _ in iterate_timeout(timeout, "requests to arrive"):
            test_requests = [
                r for r in self.otlp.requests
                if r.resource_spans[0].scope_spans[0].spans[0].name
                in span_names
            ]
            if len(test_requests) == len(span_names):
                return test_requests

    def getSpan(self, name):
        for req in self.otlp.requests:
            span = req.resource_spans[0].scope_spans[0].spans[0]
            if span.name == name:
                return span

    def test_tracing_api(self):
        tracer = trace.get_tracer("zuul")

        # We have a lot of timestamps stored as floats, so make sure
        # our root span is a ZuulSpan that can handle that input.
        span_info = tracing.startSavedSpan('parent-trace',
                                           start_time=time.time(),
                                           attributes={'startattr': 'bar'},
                                           include_attributes=True)

        # Simulate a reconstructed root span
        span = tracing.restoreSpan(span_info)

        # Within the root span, use the more typical OpenTelemetry
        # context manager api.
        with trace.use_span(span):
            with tracer.start_span('child1-trace') as child1_span:
                link = trace.Link(child1_span.context,
                                  attributes={'relationship': 'prev'})

        # Make sure that we can manually start and stop a child span,
        # and that it is a ZuulSpan as well.
        with trace.use_span(span):
            child = tracer.start_span('child2-trace', start_time=time.time(),
                                      links=[link])
            child.end(end_time=time.time())

        # Make sure that we can start a child span from a span
        # context and not a full span:
        span_context = tracing.getSpanContext(span)
        with tracing.startSpanInContext(span_context, 'child3-trace') as child:
            child.end(end_time=time.time())

        # End our root span manually.
        tracing.endSavedSpan(span_info, end_time=time.time(),
                             attributes={'endattr': 'baz'})

        test_requests = self._waitForSpans(
            "parent-trace", "child1-trace", "child2-trace", "child3-trace")

        req1 = test_requests[0]
        self.log.debug("Received:\n%s", req1)
        attrs = attributes_to_dict(req1.resource_spans[0].resource.attributes)
        self.assertEqual({"service.name": "zuultest"}, attrs)
        self.assertEqual("zuul",
                         req1.resource_spans[0].scope_spans[0].scope.name)
        span1 = req1.resource_spans[0].scope_spans[0].spans[0]
        self.assertEqual("child1-trace", span1.name)

        req2 = test_requests[1]
        self.log.debug("Received:\n%s", req2)
        span2 = req2.resource_spans[0].scope_spans[0].spans[0]
        self.assertEqual("child2-trace", span2.name)
        self.assertEqual(span2.links[0].span_id, span1.span_id)
        attrs = attributes_to_dict(span2.links[0].attributes)
        self.assertEqual({"relationship": "prev"}, attrs)

        req3 = test_requests[2]
        self.log.debug("Received:\n%s", req3)
        span3 = req3.resource_spans[0].scope_spans[0].spans[0]
        self.assertEqual("child3-trace", span3.name)

        req4 = test_requests[3]
        self.log.debug("Received:\n%s", req4)
        span4 = req4.resource_spans[0].scope_spans[0].spans[0]
        self.assertEqual("parent-trace", span4.name)
        attrs = attributes_to_dict(span4.attributes)
        self.assertEqual({"startattr": "bar",
                          "endattr": "baz"}, attrs)

        self.assertEqual(span1.trace_id, span4.trace_id)
        self.assertEqual(span2.trace_id, span4.trace_id)
        self.assertEqual(span3.trace_id, span4.trace_id)

    def test_tracing_api_null(self):
        tracer = trace.get_tracer("zuul")

        # Test that restoring spans and span contexts works with
        # null values.

        span_info = None
        # Simulate a reconstructed root span from a null value
        span = tracing.restoreSpan(span_info)

        # Within the root span, use the more typical OpenTelemetry
        # context manager api.
        with trace.use_span(span):
            with tracer.start_span('child1-trace') as child1_span:
                link = trace.Link(child1_span.context,
                                  attributes={'relationship': 'prev'})

        # Make sure that we can manually start and stop a child span,
        # and that it is a ZuulSpan as well.
        with trace.use_span(span):
            child = tracer.start_span('child2-trace', start_time=time.time(),
                                      links=[link])
            child.end(end_time=time.time())

        # Make sure that we can start a child span from a null span
        # context:
        span_context = None
        with tracing.startSpanInContext(span_context, 'child3-trace') as child:
            child.end(end_time=time.time())

        # End our root span manually.
        span.end(end_time=time.time())

        test_requests = self._waitForSpans(
            "child1-trace", "child2-trace", "child3-trace")

        req1 = test_requests[0]
        self.log.debug("Received:\n%s", req1)
        attrs = attributes_to_dict(req1.resource_spans[0].resource.attributes)
        self.assertEqual({"service.name": "zuultest"}, attrs)
        self.assertEqual("zuul",
                         req1.resource_spans[0].scope_spans[0].scope.name)
        span1 = req1.resource_spans[0].scope_spans[0].spans[0]
        self.assertEqual("child1-trace", span1.name)

        req2 = test_requests[1]
        self.log.debug("Received:\n%s", req2)
        span2 = req2.resource_spans[0].scope_spans[0].spans[0]
        self.assertEqual("child2-trace", span2.name)
        self.assertEqual(span2.links[0].span_id, span1.span_id)
        attrs = attributes_to_dict(span2.links[0].attributes)
        self.assertEqual({"relationship": "prev"}, attrs)

        req3 = test_requests[2]
        self.log.debug("Received:\n%s", req3)
        span3 = req3.resource_spans[0].scope_spans[0].spans[0]
        self.assertEqual("child3-trace", span3.name)

        self.assertNotEqual(span1.trace_id, span2.trace_id)
        self.assertNotEqual(span2.trace_id, span3.trace_id)
        self.assertNotEqual(span1.trace_id, span3.trace_id)

    def test_tracing(self):
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        for _ in iterate_timeout(60, "request to arrive"):
            if len(self.otlp.requests) >= 2:
                break

        buildset = self.getSpan('BuildSet')
        self.log.debug("Received:\n%s", buildset)
        item = self.getSpan('QueueItem')
        self.log.debug("Received:\n%s", item)
        merge_job = self.getSpan('Merge')
        self.log.debug("Received:\n%s", merge_job)
        node_request = self.getSpan('RequestNodes')
        self.log.debug("Received:\n%s", node_request)
        build = self.getSpan('Build')
        self.log.debug("Received:\n%s", build)
        jobexec = self.getSpan('JobExecution')
        self.log.debug("Received:\n%s", jobexec)

        build_update_lock = self.getSpan('BuildRepoUpdateLock')
        self.log.debug("Received:\n%s", build_update_lock)
        build_update = self.getSpan('BuildRepoUpdate')
        self.log.debug("Received:\n%s", build_update)
        build_clone = self.getSpan('BuildCloneRepo')
        self.log.debug("Received:\n%s", build_clone)
        build_merge = self.getSpan('BuildMergeChanges')
        self.log.debug("Received:\n%s", build_merge)
        # BuildSetRepoState not exercised in this test
        build_checkout = self.getSpan('BuildCheckout')
        self.log.debug("Received:\n%s", build_checkout)

        self.assertEqual(item.trace_id, buildset.trace_id)
        self.assertEqual(item.trace_id, node_request.trace_id)
        self.assertEqual(item.trace_id, build.trace_id)
        self.assertNotEqual(item.span_id, jobexec.span_id)
        self.assertTrue(buildset.start_time_unix_nano >=
                        item.start_time_unix_nano)
        self.assertTrue(buildset.end_time_unix_nano <=
                        item.end_time_unix_nano)
        self.assertTrue(merge_job.start_time_unix_nano >=
                        buildset.start_time_unix_nano)
        self.assertTrue(merge_job.end_time_unix_nano <=
                        buildset.end_time_unix_nano)
        self.assertEqual(jobexec.parent_span_id,
                         build.span_id)
        self.assertEqual(node_request.parent_span_id,
                         buildset.span_id)
        self.assertEqual(build.parent_span_id,
                         buildset.span_id)
        self.assertEqual(merge_job.parent_span_id,
                         buildset.span_id)
        self.assertEqual(buildset.parent_span_id,
                         item.span_id)

        self.assertEqual(build_update_lock.parent_span_id,
                         jobexec.span_id)
        self.assertEqual(build_update.parent_span_id,
                         jobexec.span_id)
        self.assertEqual(build_clone.parent_span_id,
                         jobexec.span_id)
        self.assertEqual(build_merge.parent_span_id,
                         jobexec.span_id)
        self.assertEqual(build_checkout.parent_span_id,
                         jobexec.span_id)

        item_attrs = attributes_to_dict(item.attributes)
        self.assertTrue(item_attrs['ref_number'] == ["1"])
        self.assertTrue(item_attrs['ref_patchset'] == ["1"])
        self.assertTrue('zuul_event_id' in item_attrs)

    def test_post(self):
        "Test that post jobs run"
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.setMerged()
        self.fake_gerrit.addEvent(A.getRefUpdatedEvent())
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='project-post', result='SUCCESS',
                 ref='refs/heads/master'),
        ], ordered=False)

        job_names = [x.name for x in self.history]
        self.assertEqual(len(self.history), 1)
        self.assertIn('project-post', job_names)

    def test_timer(self):
        self.executor_server.hold_jobs_in_build = True
        self.commitConfigUpdate('common-config', 'layouts/timer.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()

        for _ in iterate_timeout(30, 'Wait for a build on hold'):
            if len(self.builds) > 0:
                break
        self.waitUntilSettled()

        self.commitConfigUpdate('common-config',
                                'layouts/no-timer.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()
        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='project-bitrot', result='SUCCESS',
                 ref='refs/heads/master'),
        ], ordered=False)
