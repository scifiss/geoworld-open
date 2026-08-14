"""HTTP-only client for the official GeoWorld product backend.

This module is intentionally public. It depends only on the documented HTTP surface and
portable public response models; it never imports private GeoWorld implementation code.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from geoworld_open.client.models import (
    AuthResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
)


class GeoWorldClientError(RuntimeError):
    """Sanitized backend/client failure safe to show in the public UI."""


class HttpTransport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, bytes]: ...


@dataclass(frozen=True)
class UrllibTransport:
    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, bytes]:
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL validated by client
                return int(response.status), response.read()
        except HTTPError as exc:
            return int(exc.code), exc.read()
        except (URLError, TimeoutError, OSError) as exc:
            raise GeoWorldClientError("GeoWorld backend is unavailable") from exc


def backend_url_from_environment(environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    value = str(env.get("GEOWORLD_BACKEND_URL", "")).strip()
    return value.rstrip("/") or None


class GeoWorldBackendClient:
    """Thin client for authentication, Ask/Build jobs, artifacts, and health."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = 120.0,
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

    def register(self, email: str, password: str) -> AuthResponse:
        payload = self._json_request(
            "POST",
            "/auth/register",
            {"email": email, "password": password},
            retry_on_429=True,
        )
        return AuthResponse.model_validate(payload)

    def login(self, email: str, password: str) -> AuthResponse:
        payload = self._json_request(
            "POST",
            "/auth/login",
            {"email": email, "password": password},
            retry_on_429=True,
        )
        return AuthResponse.model_validate(payload)

    def get_llm_health(self) -> dict[str, object]:
        return self._json_request("GET", "/api/llm/health")

    def preview_geospec(
        self,
        *,
        prompt: str | None = None,
        geospec: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return self._json_request(
            "POST",
            "/geospec/preview",
            {"prompt": prompt, "geospec": geospec},
        )

    def submit_job(self, request: JobCreateRequest) -> JobCreateResponse:
        payload = self._json_request("POST", "/jobs", request.model_dump(mode="json"))
        return JobCreateResponse.model_validate(payload)

    def get_job(self, job_id: str) -> JobStatusResponse:
        payload = self._json_request("GET", f"/jobs/{job_id}")
        return JobStatusResponse.model_validate(payload)

    def get_artifact(self, job_id: str, artifact_name: str) -> bytes:
        status, body = self._send("GET", f"/jobs/{job_id}/artifacts/{artifact_name}")
        if 200 <= status < 300:
            return body
        raise GeoWorldClientError(self._error_message(status, body))

    def get_export(self, job_id: str) -> bytes:
        status, body = self._send("GET", f"/jobs/{job_id}/export")
        if 200 <= status < 300:
            return body
        raise GeoWorldClientError(self._error_message(status, body))

    def _json_request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        retry_on_429: bool = False,
    ) -> dict[str, object]:
        attempts = 7 if retry_on_429 else 1
        for attempt in range(attempts):
            status, body = self._send(method, path, payload)
            if status != 429 or attempt == attempts - 1:
                break
            time.sleep(10)
        if not 200 <= status < 300:
            if retry_on_429 and status == 429:
                raise GeoWorldClientError(
                    "GeoWorld backend is still starting. Please try again in a moment."
                )
            raise GeoWorldClientError(self._error_message(status, body))
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GeoWorldClientError("GeoWorld backend returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise GeoWorldClientError("GeoWorld backend returned an unexpected response")
        return decoded

    def _send(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, bytes]:
        headers = {"Accept": "application/json"}
        body: bytes | None = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return self._transport.send(
            method,
            f"{self._base_url}{path}",
            headers,
            body,
            self._timeout,
        )

    @staticmethod
    def _error_message(status: int, body: bytes) -> str:
        detail = ""
        try:
            decoded = json.loads(body.decode("utf-8"))
            if isinstance(decoded, dict) and isinstance(decoded.get("detail"), str):
                detail = str(decoded["detail"]).strip()
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = ""
        suffix = f": {detail}" if detail else ""
        return f"GeoWorld backend returned HTTP {status}{suffix}"
