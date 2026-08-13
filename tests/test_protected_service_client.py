import json

import pytest

from geoworld_open.sdk import (
    CapabilityServiceRequest,
    CapabilityUnavailableError,
    ProtectedCapabilityClient,
)


class FakeTransport:
    def __init__(self, status: int, payload: dict[str, object]) -> None:
        self.status = status
        self.payload = payload
        self.calls: list[tuple[str, str, dict[str, str], bytes, float]] = []

    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout: float,
    ) -> tuple[int, bytes]:
        self.calls.append((method, url, headers, body, timeout))
        return self.status, json.dumps(self.payload).encode()


def _request() -> CapabilityServiceRequest:
    return CapabilityServiceRequest(
        request_id="request-1",
        capability_id="protected.rock_physics",
        capability_version="1.0",
        inputs={"porosity": 0.2, "pressure_pa": 10_000_000.0},
    )


def test_protected_service_client_is_http_only_and_mockable() -> None:
    transport = FakeTransport(
        200,
        {
            "schema_version": "1.0",
            "request_id": "request-1",
            "status": "succeeded",
            "outputs": {"artifact_id": "artifact-1"},
        },
    )
    client = ProtectedCapabilityClient(
        "https://service.example.test",
        token="not-a-real-secret",
        transport=transport,
    )
    response = client.invoke(_request())
    assert response.status == "succeeded"
    method, url, headers, body, timeout = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/api/v1/capabilities/protected.rock_physics/execute")
    assert headers["Authorization"] == "Bearer not-a-real-secret"
    assert json.loads(body)["request_id"] == "request-1"
    assert timeout == 30.0


def test_protected_service_unavailable_is_clear() -> None:
    client = ProtectedCapabilityClient(
        "https://service.example.test",
        transport=FakeTransport(503, {}),
    )
    with pytest.raises(CapabilityUnavailableError, match="unavailable"):
        client.invoke(_request())


def test_client_rejects_credentials_embedded_in_url() -> None:
    with pytest.raises(ValueError, match="credentials"):
        ProtectedCapabilityClient("https://user:password@example.test")
