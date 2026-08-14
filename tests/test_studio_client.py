from __future__ import annotations

import json

import pytest

from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError, JobCreateRequest


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

    created = client.submit_job(JobCreateRequest(prompt="build model", mode_hint="build_model"))
    completed = client.get_job(created.job_id)

    assert completed.status == "succeeded"
    assert completed.result is not None
    assert completed.result.artifacts[0].name == "summary.png"
    assert transport.calls[0][2]["Authorization"] == "Bearer secret-token"


def test_backend_errors_are_sanitized() -> None:
    transport = FakeTransport([(503, {"detail": "starting"})])
    client = GeoWorldBackendClient("https://example.test", transport=transport)

    with pytest.raises(GeoWorldClientError, match="HTTP 503"):
        client.get_llm_health()


def test_invalid_backend_url_is_rejected() -> None:
    with pytest.raises(ValueError):
        GeoWorldBackendClient("file:///tmp/private")
