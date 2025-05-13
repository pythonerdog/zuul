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

import grpc
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
    OTLPSpanExporter as GRPCExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import \
    OTLPSpanExporter as HTTPExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry import trace
from opentelemetry.sdk import trace as trace_sdk

from zuul.lib.config import get_default, any_to_bool


class ZuulSpan(Span):
    """An implementation of Span which accepts floating point
    times and converts them to the expected nanoseconds."""

    def start(self, start_time=None, parent_context=None):
        if isinstance(start_time, float):
            start_time = int(start_time * (10**9))
        return super().start(start_time, parent_context)

    def end(self, end_time=None):
        if isinstance(end_time, float):
            end_time = int(end_time * (10**9))
        return super().end(end_time)


# Patch the OpenTelemetry SDK Span class to return a ZuulSpan so that
# we can supply floating point timestamps.
trace_sdk._Span = ZuulSpan


def _formatContext(context):
    return {
        'trace_id': context.trace_id,
        'span_id': context.span_id,
    }


def _formatAttributes(attrs):
    if attrs is None:
        return None
    return attrs.copy()


def getSpanInfo(span, include_attributes=False):
    """Return a dict for use in serializing a Span."""
    links = [{'context': _formatContext(l.context),
              'is_remote': l.context.is_remote,
              'attributes': _formatAttributes(l.attributes)}
             for l in span.links]
    attrs = _formatAttributes(span.attributes)
    context = span.get_span_context()
    parent_context = None
    if span.parent:
        parent_context = {
            **_formatContext(span.parent),
            "is_remote": span.parent.is_remote,
        }
    ret = {
        'name': span.name,
        'trace_id': context.trace_id,
        'span_id': context.span_id,
        'trace_flags': context.trace_flags,
        'start_time': span.start_time,
        'parent': parent_context,
    }
    if links:
        ret['links'] = links
    if attrs:
        if not include_attributes:
            # Avoid setting attributes when we start saved spans
            # because we have to store them in ZooKeeper and we should
            # minimize what we store there (especially since it is
            # usually duplicative).  If you really need to set
            # attributes at the start of a span (because the info is
            # not available later), set include_attributes to True.
            # Otherwise, we raise an error here to remind ourselves to
            # avoid that programming pattern.
            raise RuntimeError("Attributes were set on a saved span; "
                               "either set them when ending the span, "
                               "or set include_attributes=True")
        ret['attributes'] = attrs
    return ret


def restoreSpan(span_info, is_remote=True):
    """Restore a Span from the serialized dict provided by getSpanInfo

    Return None if unable to serialize the span.
    """
    tracer = trace.get_tracer("zuul")
    if span_info is None:
        return trace.INVALID_SPAN
    required_keys = {'name', 'trace_id', 'span_id', 'trace_flags'}
    if not required_keys <= set(span_info.keys()):
        return trace.INVALID_SPAN
    span_context = trace.SpanContext(
        span_info['trace_id'],
        span_info['span_id'],
        is_remote=is_remote,
        trace_flags=trace.TraceFlags(span_info['trace_flags']),
    )
    links = []
    for link_info in span_info.get('links', []):
        link_context = trace.SpanContext(
            link_info['context']['trace_id'],
            link_info['context']['span_id'],
            is_remote=link_info['is_remote'])
        link = trace.Link(link_context, link_info['attributes'])
        links.append(link)
    attributes = span_info.get('attributes', {})
    parent_context = None
    if parent_info := span_info.get("parent"):
        parent_context = trace.SpanContext(
            parent_info['trace_id'],
            parent_info['span_id'],
            is_remote=parent_info['is_remote'],
        )

    span = ZuulSpan(
        name=span_info['name'],
        context=span_context,
        parent=parent_context,
        sampler=tracer.sampler,
        resource=tracer.resource,
        attributes=attributes,
        span_processor=tracer.span_processor,
        kind=trace.SpanKind.INTERNAL,
        links=links,
        instrumentation_info=tracer.instrumentation_info,
        record_exception=False,
        set_status_on_exception=True,
        limits=tracer._span_limits,
        instrumentation_scope=tracer._instrumentation_scope,
    )
    span.start(start_time=span_info['start_time'])

    return span


def startSavedSpan(*args, **kw):
    """Start a span and serialize it

    This is a convenience method which starts a span (either root
    or child) and immediately serializes it.

    Most spans in Zuul should use this method.
    """
    tracer = trace.get_tracer("zuul")
    include_attributes = kw.pop('include_attributes', False)
    span = tracer.start_span(*args, **kw)
    return getSpanInfo(span, include_attributes)


def endSavedSpan(span_info, end_time=None, attributes=None):
    """End a saved span.

    This is a convenience method to restore a saved span and
    immediately end it.

    Most spans in Zuul should use this method.
    """
    span = restoreSpan(span_info, is_remote=False)
    if span:
        if attributes:
            span.set_attributes(attributes)
        span.end(end_time=end_time)


def getSpanContext(span):
    """Return a dict for use in serializing a Span Context.

    The span context information used here is a lightweight
    encoding of the span information so that remote child spans
    can be started without access to a fully restored parent.
    This is equivalent to (but not the same format) as the
    OpenTelemetry trace context propogator.
    """
    context = span.get_span_context()
    return {
        'trace_id': context.trace_id,
        'span_id': context.span_id,
        'trace_flags': context.trace_flags,
    }


def restoreSpanContext(span_context):
    """Return a span with remote context information from getSpanContext.

    This returns a non-recording span to use as a parent span.  It
    avoids the necessity of fully restoring the parent span.
    """
    if span_context:
        span_context = trace.SpanContext(
            trace_id=span_context['trace_id'],
            span_id=span_context['span_id'],
            is_remote=True,
            trace_flags=trace.TraceFlags(span_context['trace_flags'])
        )
    else:
        span_context = trace.INVALID_SPAN_CONTEXT
    parent = trace.NonRecordingSpan(span_context)
    return parent


def startSpanInContext(span_context, *args, **kw):
    """Start a span in a saved context.

    This restores a span from a saved context and starts a new child span.
    """
    tracer = trace.get_tracer("zuul")
    parent = restoreSpanContext(span_context)
    with trace.use_span(parent):
        return tracer.start_span(*args, **kw)


class Tracing:
    PROTOCOL_GRPC = 'grpc'
    PROTOCOL_HTTP_PROTOBUF = 'http/protobuf'
    processor_class = BatchSpanProcessor

    def __init__(self, config):
        service_name = get_default(config, "tracing", "service_name", "zuul")
        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        enabled = get_default(config, "tracing", "enabled")
        if not any_to_bool(enabled):
            self.processor = None
            return

        protocol = get_default(config, "tracing", "protocol",
                               self.PROTOCOL_GRPC)
        endpoint = get_default(config, "tracing", "endpoint")
        tls_key = get_default(config, "tracing", "tls_key")
        tls_cert = get_default(config, "tracing", "tls_cert")
        tls_ca = get_default(config, "tracing", "tls_ca")
        certificate_file = get_default(config, "tracing", "certificate_file")
        insecure = get_default(config, "tracing", "insecure")
        if insecure is not None:
            insecure = any_to_bool(insecure)
        timeout = get_default(config, "tracing", "timeout")
        if timeout is not None:
            timeout = int(timeout)
        compression = get_default(config, "tracing", "compression")

        if protocol == self.PROTOCOL_GRPC:
            if certificate_file:
                raise Exception("The certificate_file tracing option "
                                f"is not valid for {protocol} endpoints")
            if any([tls_ca, tls_key, tls_cert]):
                if tls_ca:
                    tls_ca = open(tls_ca, 'rb').read()
                if tls_key:
                    tls_key = open(tls_key, 'rb').read()
                if tls_cert:
                    tls_cert = open(tls_cert, 'rb').read()
                creds = grpc.ssl_channel_credentials(
                    root_certificates=tls_ca,
                    private_key=tls_key,
                    certificate_chain=tls_cert)
            else:
                creds = None
            exporter = GRPCExporter(
                endpoint=endpoint,
                insecure=insecure,
                credentials=creds,
                timeout=timeout,
                compression=compression)
        elif protocol == self.PROTOCOL_HTTP_PROTOBUF:
            if insecure:
                raise Exception("The insecure tracing option "
                                f"is not valid for {protocol} endpoints")
            if any([tls_ca, tls_key, tls_cert]):
                raise Exception("The tls_* tracing options "
                                f"are not valid for {protocol} endpoints")
            exporter = HTTPExporter(
                endpoint=endpoint,
                certificate_file=certificate_file,
                timeout=timeout,
                compression=compression)
        else:
            raise Exception(f"Unknown tracing protocol {protocol}")
        self.processor = self.processor_class(exporter)
        provider.add_span_processor(self.processor)

    def stop(self):
        if not self.processor:
            return
        self.processor.shutdown()
