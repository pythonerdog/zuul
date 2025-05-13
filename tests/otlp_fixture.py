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
from concurrent import futures

import fixtures
import grpc
from opentelemetry import trace
from opentelemetry.proto.collector.trace.v1.trace_service_pb2_grpc import (
    TraceServiceServicer,
    add_TraceServiceServicer_to_server
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceResponse,
)


class TraceServer(TraceServiceServicer):
    def __init__(self, fixture):
        super().__init__()
        self.fixture = fixture

    def Export(self, request, context):
        self.fixture.requests.append(request)
        return ExportTraceServiceResponse()


class OTLPFixture(fixtures.Fixture):
    def __init__(self):
        super().__init__()
        self.requests = []
        self.executor = futures.ThreadPoolExecutor(
            thread_name_prefix='OTLPFixture',
            max_workers=10)
        self.server = grpc.server(self.executor)
        add_TraceServiceServicer_to_server(TraceServer(self), self.server)
        self.port = self.server.add_insecure_port('[::]:0')
        # Reset global tracer provider
        trace._TRACER_PROVIDER_SET_ONCE = trace.Once()
        trace._TRACER_PROVIDER = None

    def _setUp(self):
        self.server.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        self.server.stop(None)
        self.server.wait_for_termination()
        self.executor.shutdown()
        # Reset global tracer provider
        trace._TRACER_PROVIDER_SET_ONCE = trace.Once()
        trace._TRACER_PROVIDER = None
