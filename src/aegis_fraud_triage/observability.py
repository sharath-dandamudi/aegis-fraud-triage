"""Optional OpenTelemetry and LangSmith integration without hard-coded credentials."""
from __future__ import annotations

import os
from typing import Any, Callable


class TelemetryBridge:
    def __init__(self):
        try:
            from opentelemetry import trace
            self._configure_otlp_if_requested(trace)
            self.tracer = trace.get_tracer("aegis_fraud_triage")
        except ImportError:
            self.tracer = None

    @staticmethod
    def _configure_otlp_if_requested(trace) -> None:
        """Configure a bounded, redacted OTLP trace pipeline when requested."""
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            return
        try:
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            resource = Resource.create({
                SERVICE_NAME: "aegis-fraud-triage",
                SERVICE_VERSION: os.getenv("AEGIS_AGENT_VERSION", "v1"),
                "deployment.environment.name": os.getenv("ENVIRONMENT", "local"),
            })
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=3)))
            trace.set_tracer_provider(provider)
        except ImportError:
            # The local JSONL trace remains the reliable fallback when optional exporter extras are absent.
            return

    def emit_trace(self, trace_id: str, case_id: str | None, events: list[dict[str, Any]], result: dict[str, Any]) -> None:
        """Emits one OTel span with bounded, redacted metadata when an exporter is configured."""
        if self.tracer is None:
            return
        with self.tracer.start_as_current_span("aegis_fraud_triage.run") as span:
            span.set_attribute("triage.trace_id", trace_id)
            span.set_attribute("triage.case_id", case_id or "")
            span.set_attribute("triage.route", result["route"])
            span.set_attribute("triage.escalated", result["escalation_required"])
            span.set_attribute("triage.latency_ms", result["latency_ms"])
            span.set_attribute("triage.cost_aud", result["estimated_cost_aud"])
            for event in events:
                # Explicitly allow only bounded execution metadata. Customer text,
                # raw tool payloads and model prompts never enter the telemetry path.
                attributes = {
                    key: value for key, value in event["attributes"].items()
                    if key in {"passed", "reasons", "route", "risk", "escalate", "confidence", "source_ids", "skipped", "reason", "names", "success", "review_required", "severities", "codes", "count", "model", "input_tokens", "output_tokens", "fallback"}
                }
                span.add_event(event["name"], attributes)


def traceable_if_configured(name: str) -> Callable:
    """Use LangSmith's native wrapper only when tracing credentials were supplied before startup."""
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true" and os.getenv("LANGSMITH_API_KEY"):
        try:
            from langsmith import traceable
            return traceable(name=name, run_type="chain")
        except ImportError:
            pass
    return lambda func: func
