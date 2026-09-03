from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from geoworld_open.client import (
    GeoWorldBackendClient,
    GeoWorldClientError,
    JobCreateRequest,
    LASQuicklookSettings,
    UploadedLASFile,
)


class FakeTransport:
    def __init__(self, responses: list[tuple[int, object]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, str], bytes | None, float]] = []

    def send(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        status, payload = self.responses.pop(0)
        if isinstance(payload, bytes):
            return status, payload
        return status, json.dumps(payload).encode("utf-8")


def test_login_uses_public_http_contract_only() -> None:
    transport = FakeTransport(
        [
            (
                200,
                {
                    "access_token": "token-1",
                    "token_type": "bearer",
                    "user": {"id": 7, "email": "user@example.com"},
                },
            )
        ]
    )
    client = GeoWorldBackendClient("https://example.test", transport=transport)

    auth = client.login("user@example.com", "password123")

    assert auth.user.email == "user@example.com"
    method, url, headers, body, _ = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/auth/login")
    assert "Authorization" not in headers
    assert json.loads(body.decode("utf-8"))["email"] == "user@example.com"


def test_authenticated_build_job_round_trip() -> None:
    transport = FakeTransport(
        [
            (200, {"job_id": "job-1", "status": "queued", "progress": "queued"}),
            (
                200,
                {
                    "job_id": "job-1",
                    "status": "succeeded",
                    "progress": "complete",
                    "result": {
                        "intent": "scenario_generation",
                        "reason": "manual build",
                        "answer": "done",
                        "assumptions": ["synthetic"],
                        "interpretation_mode": "llm_semantic_parser",
                        "requested_outputs": ["vp", "impedance"],
                        "produced_outputs": ["vp", "impedance"],
                        "output_coverage": {"vp": True, "impedance": True},
                        "provenance_summary": {
                            "trace_id": "trace-1",
                            "capabilities": ["semantic_model_parser", "synthetic_avo_runner"],
                        },
                        "artifacts": [
                            {
                                "name": "summary.png",
                                "kind": "image",
                                "media_type": "image/png",
                                "size_bytes": 10,
                            }
                        ],
                    },
                    "error": None,
                },
            ),
        ]
    )
    client = GeoWorldBackendClient(
        "https://example.test",
        token="secret-token",
        transport=transport,
    )

    created = client.submit_job(
        JobCreateRequest(
            prompt="build model",
            mode_hint="build_model",
            geospec={"schema_version": "2.0"},
            interpretation_mode="deterministic_fallback",
            interpretation_degraded=True,
            degraded_fallback_confirmed=True,
        )
    )
    completed = client.get_job(created.job_id)

    assert completed.status == "succeeded"
    assert completed.result is not None
    assert completed.result.artifacts[0].name == "summary.png"
    assert completed.result.interpretation_mode == "llm_semantic_parser"
    assert completed.result.output_coverage == {"vp": True, "impedance": True}
    assert transport.calls[0][2]["Authorization"] == "Bearer secret-token"
    submitted = json.loads(transport.calls[0][3].decode("utf-8"))
    assert submitted["interpretation_mode"] == "deterministic_fallback"
    assert submitted["interpretation_degraded"] is True
    assert submitted["degraded_fallback_confirmed"] is True


def test_intent_preview_uses_public_http_contract() -> None:
    transport = FakeTransport(
        [
            (
                200,
                {
                    "intent": "build_model",
                    "label": "Build model",
                    "reason": "The request asks for a model.",
                    "confidence": "high",
                    "needs_confirmation": False,
                },
            )
        ]
    )
    client = GeoWorldBackendClient(
        "https://example.test",
        token="token",
        transport=transport,
    )

    preview = client.preview_intent("Build shale and sand.")

    assert preview["intent"] == "build_model"
    assert transport.calls[0][0] == "POST"
    assert transport.calls[0][1].endswith("/intent/preview")
    assert json.loads(transport.calls[0][3].decode("utf-8"))["prompt"] == "Build shale and sand."


def test_las_quicklook_job_uses_portable_contract_and_keeps_correlation_id() -> None:
    transport = FakeTransport(
        [
            (
                200,
                {
                    "job_id": "job-las-1",
                    "correlation_id": "request-0123456789abcdef0123456789abcdef",
                    "status": "queued",
                    "progress": "queued",
                },
            )
        ]
    )
    client = GeoWorldBackendClient(
        "https://example.test",
        token="token",
        transport=transport,
    )

    created = client.submit_job(
        JobCreateRequest(
            prompt="LAS Quicklook v1 measured-depth job",
            mode_hint="las_quicklook",
            las_files=[
                UploadedLASFile(
                    filename="well.las",
                    content_base64="fkFCQw==",
                    size_bytes=4,
                )
            ],
            las_quicklook=LASQuicklookSettings(
                selected_curves=["GR", "RHOB"],
                depth_range_mode="union",
                target_depth_unit="m",
            ),
        )
    )

    assert created.correlation_id == "request-0123456789abcdef0123456789abcdef"
    submitted = json.loads(transport.calls[0][3].decode("utf-8"))
    assert submitted["mode_hint"] == "las_quicklook"
    assert submitted["las_files"][0]["filename"] == "well.las"
    assert submitted["las_quicklook"]["selected_curves"] == ["GR", "RHOB"]
    assert submitted["las_quicklook"]["target_depth_unit"] == "m"


def test_authenticated_capability_catalog_is_typed() -> None:
    transport = FakeTransport(
        [
            (
                200,
                {
                    "schema_version": "1.0",
                    "catalog_version": "sha256:catalog",
                    "capabilities": [
                        {
                            "name": "acoustic_impedance",
                            "version": "1.0",
                            "category": "scientific_function",
                            "availability": "active",
                            "input_schema": {"type": "object"},
                            "output_schema": {"type": "object"},
                            "required_variables": ["vp", "density"],
                            "produced_variables": ["impedance"],
                            "supported_dimensions": ["1d"],
                            "assumptions": ["co-located samples"],
                            "limitations": ["no unit conversion"],
                        }
                    ],
                },
            )
        ]
    )
    client = GeoWorldBackendClient(
        "https://example.test",
        token="token",
        transport=transport,
    )

    catalog = client.get_capabilities()

    assert catalog.catalog_version == "sha256:catalog"
    assert catalog.capabilities[0].name == "acoustic_impedance"
    assert catalog.capabilities[0].produced_variables == ["impedance"]
    method, url, headers, _, _ = transport.calls[0]
    assert method == "GET"
    assert url.endswith("/capabilities")
    assert headers["Authorization"] == "Bearer token"


def test_job_response_rejects_non_opaque_correlation_content() -> None:
    transport = FakeTransport(
        [
            (
                200,
                {
                    "job_id": "job-1",
                    "correlation_id": "request-user@example.com",
                    "status": "queued",
                    "progress": "queued",
                },
            )
        ]
    )
    client = GeoWorldBackendClient("https://example.test", transport=transport)

    with pytest.raises(ValidationError, match="correlation_id"):
        client.submit_job(JobCreateRequest(prompt="build model"))


def test_backend_errors_are_sanitized() -> None:
    transport = FakeTransport([(503, {"detail": "starting"})])
    client = GeoWorldBackendClient("https://example.test", transport=transport)

    with pytest.raises(GeoWorldClientError, match="HTTP 503"):
        client.get_llm_health()


def test_invalid_backend_url_is_rejected() -> None:
    with pytest.raises(ValueError):
        GeoWorldBackendClient("file:///tmp/private")
