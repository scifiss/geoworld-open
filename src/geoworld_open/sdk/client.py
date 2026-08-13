"""HTTP-only client for optional protected GeoWorld capabilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from pydantic import Field, JsonValue, model_validator

from geoworld_open.standard.capabilities import ContractModel
from geoworld_open.standard.version import CAPABILITY_API_VERSION, STANDARD_VERSION
from geoworld_open.world.models import Identifier, NonEmptyStr


class CapabilityServiceStatus(str):
    SUCCEEDED = "succeeded"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class CapabilityServiceRequest(ContractModel):
    schema_version: str = STANDARD_VERSION
    request_id: Identifier
    capability_id: Identifier
    capability_version: Identifier
    inputs: dict[str, JsonValue]
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class CapabilityServiceResponse(ContractModel):
    schema_version: str = STANDARD_VERSION
    request_id: Identifier
    status: str
    outputs: dict[str, JsonValue] = Field(default_factory=dict)
    artifact_manifest_url: NonEmptyStr | None = None
    error_category: Identifier | None = None
    message: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "CapabilityServiceResponse":
        allowed = {
            CapabilityServiceStatus.SUCCEEDED,
            CapabilityServiceStatus.UNAVAILABLE,
            CapabilityServiceStatus.FAILED,
        }
        if self.status not in allowed:
            raise ValueError(f"unsupported capability-service status: {self.status!r}")
        if self.status == CapabilityServiceStatus.SUCCEEDED and self.error_category:
            raise ValueError("successful responses cannot contain error_category")
        if self.status != CapabilityServiceStatus.SUCCEEDED and self.outputs:
            raise ValueError("unsuccessful responses cannot claim outputs")
        return self


class ProtectedServiceError(RuntimeError):
    """Sanitized protected-service transport or response failure."""


class CapabilityUnavailableError(ProtectedServiceError):
    """The protected capability is absent or temporarily unavailable."""


class HttpTransport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout: float,
    ) -> tuple[int, bytes]: ...


@dataclass(frozen=True)
class UrllibTransport:
    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout: float,
    ) -> tuple[int, bytes]:
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - validated URL
                return int(response.status), response.read()
        except HTTPError as exc:
            return int(exc.code), exc.read()
        except (URLError, TimeoutError, OSError) as exc:
            raise CapabilityUnavailableError("protected capability service is unavailable") from exc


class ProtectedCapabilityClient:
    """Call the documented service contract without importing private source."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = 30.0,
        transport: HttpTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url must not contain credentials, query, or fragment")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._transport = transport or UrllibTransport()

    def invoke(self, request: CapabilityServiceRequest) -> CapabilityServiceResponse:
        path_id = quote(request.capability_id, safe="")
        url = f"{self._base_url}/api/{CAPABILITY_API_VERSION}/capabilities/{path_id}/execute"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        status, body = self._transport.send(
            "POST",
            url,
            headers,
            request.model_dump_json().encode("utf-8"),
            self._timeout,
        )
        if status in {404, 408, 429, 501, 502, 503, 504}:
            raise CapabilityUnavailableError(f"protected capability unavailable (HTTP {status})")
        if status < 200 or status >= 300:
            raise ProtectedServiceError(f"protected capability request failed (HTTP {status})")
        try:
            response = CapabilityServiceResponse.model_validate_json(body)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ProtectedServiceError("protected capability returned an invalid response") from exc
        if response.request_id != request.request_id:
            raise ProtectedServiceError("protected capability response request_id mismatch")
        return response
