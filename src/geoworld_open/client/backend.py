"""HTTP-only client for the official GeoWorld product backend.

This module is intentionally public. It depends only on the documented HTTP surface and
portable public response models; it never imports private GeoWorld implementation code.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import BinaryIO, Iterable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from geoworld_open.client.models import (
    AuthResponse,
    CapabilityCatalog,
    ForgotPasswordResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    PasswordResetResponse,
)


class GeoWorldClientError(RuntimeError):
    """Sanitized backend/client failure safe to show in the public UI."""


RequestBody = bytes | Iterable[bytes]
UploadSource = bytes | bytearray | memoryview | BinaryIO | Iterable[bytes]
UPLOAD_CHUNK_BYTES = 1024 * 1024


class HttpTransport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: RequestBody | None,
        timeout: float,
    ) -> tuple[int, bytes]: ...


@dataclass(frozen=True)
class UrllibTransport:
    def send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: RequestBody | None,
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

    def forgot_password(self, email: str) -> ForgotPasswordResponse:
        payload = self._json_request(
            "POST", "/auth/forgot-password", {"email": email},
        )
        return ForgotPasswordResponse.model_validate(payload)

    def reset_password(self, reset_token: str, new_password: str) -> PasswordResetResponse:
        payload = self._json_request(
            "POST",
            "/auth/reset-password",
            {"reset_token": reset_token, "new_password": new_password},
        )
        return PasswordResetResponse.model_validate(payload)

    def change_password(
        self, current_password: str, new_password: str,
    ):
        from geoworld_open.client.models import PasswordChangeResponse
        payload = self._json_request(
            "POST",
            "/auth/change-password",
            {"current_password": current_password, "new_password": new_password},
        )
        return PasswordChangeResponse.model_validate(payload)

    def get_llm_health(self) -> dict[str, object]:
        return self._json_request("GET", "/api/llm/health")

    def get_capabilities(self) -> CapabilityCatalog:
        payload = self._json_request("GET", "/capabilities")
        return CapabilityCatalog.model_validate(payload)

    def interpret_studio(self, prompt, project_id=None):
        from geoworld_open.client.studio_request import StudioRequest, StudioDecision
        request = StudioRequest(prompt=prompt, project_id=project_id)
        return StudioDecision.model_validate(self._json_request("POST", "/intent/interpret", request.model_dump(mode="json")))

    def continue_experiment(self, prompt, *, conversation_id=None, project_id=None):
        from geoworld_open.client.scientific_experiment import (
            ExperimentConversationRequest,
            ExperimentConversationResponse,
        )
        request = ExperimentConversationRequest(
            prompt=prompt,
            conversation_id=conversation_id,
            project_id=project_id,
        )
        payload = self._json_request(
            "POST", "/experiments/conversation/turn", request.model_dump(mode="json")
        )
        return ExperimentConversationResponse.model_validate(payload)

    def list_seismic_datasets(self):
        from geoworld_open.client.seismic import SeismicDatasetCatalog
        return SeismicDatasetCatalog.model_validate(
            self._json_request("GET", "/seismic/datasets")
        )

    def upload_seismic(self, filename: str, content: UploadSource):
        """Upload one SEG-Y source without exposing or accepting a server path."""
        from geoworld_open.client.seismic import SeismicUploadRecord
        status, body = self._send_binary(
            "POST", "/seismic/uploads", self._upload_body(content),
            headers={
                "Content-Type": "application/octet-stream",
                "X-GeoWorld-Filename": quote(filename, safe=""),
            },
        )
        if not 200 <= status < 300:
            raise GeoWorldClientError(self._error_message(status, body))
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GeoWorldClientError("GeoWorld backend returned invalid JSON") from exc
        return SeismicUploadRecord.model_validate(decoded)

    def get_seismic_view(self, request):
        from geoworld_open.client.seismic import SeismicViewData, SeismicViewRequest
        validated = SeismicViewRequest.model_validate(request)
        return SeismicViewData.model_validate(
            self._json_request("POST", "/seismic/view", validated.model_dump(mode="json"))
        )

    def continue_seismic_explorer(self, prompt, *, dataset_id=None, conversation_id=None):
        from geoworld_open.client.seismic import SeismicConversationRequest, SeismicExplorerResponse
        request = SeismicConversationRequest(
            prompt=prompt, dataset_id=dataset_id, conversation_id=conversation_id,
        )
        return SeismicExplorerResponse.model_validate(
            self._json_request(
                "POST", "/seismic/conversation/turn", request.model_dump(mode="json")
            )
        )

    def get_reference_compute(self):
        from geoworld_open.client.reference_experiment import ReferenceCompute
        return ReferenceCompute.model_validate(self._json_request("GET", "/references/compute"))

    def preview_marmousi(self, selection, project_id=None):
        from geoworld_open.client.marmousi import MarmousiPreview, MarmousiPreviewRequest
        request = MarmousiPreviewRequest(selection=selection, project_id=project_id)
        return MarmousiPreview.model_validate(self._json_request("POST", "/models/marmousi/preview", request.model_dump(mode="json")))

    def preview_marmousi_forward(self, experiment, *, project_id=None, preference=None):
        from geoworld_open.client.execution import ExecutionPreference
        from geoworld_open.client.marmousi_forward import (
            MarmousiForwardPreview,
            MarmousiForwardPreviewRequest,
        )
        request = MarmousiForwardPreviewRequest(
            experiment=experiment,
            project_id=project_id,
            preference=preference or ExecutionPreference(),
        )
        return MarmousiForwardPreview.model_validate(
            self._json_request(
                "POST", "/models/marmousi/forward/preview", request.model_dump(mode="json")
            )
        )

    def preview_configurable_fwi(self, experiment, *, project_id=None, preference=None, intermediate_results=None):
        from geoworld_open.client.configurable_fwi import ConfigurableFWIPreview, ConfigurableFWIPreviewRequest
        from geoworld_open.client.execution import ExecutionPreference
        from geoworld_open.client.intermediate_results import IntermediateResultPolicy
        request = ConfigurableFWIPreviewRequest(
            experiment=experiment,
            project_id=project_id,
            preference=preference or ExecutionPreference(),
            intermediate_results=intermediate_results or IntermediateResultPolicy(),
        )
        return ConfigurableFWIPreview.model_validate(
            self._json_request(
                "POST", "/fwi/configurable/preview", request.model_dump(mode="json")
            )
        )

    def interpret_marmousi(self, prompt, project_id=None):
        from geoworld_open.client.marmousi import MarmousiInterpretation, MarmousiInterpretRequest
        request = MarmousiInterpretRequest(prompt=prompt, project_id=project_id)
        return MarmousiInterpretation.model_validate(self._json_request("POST", "/models/marmousi/interpret", request.model_dump(mode="json")))

    def preview_reference(self, *, prompt=None, selection=None, project_id=None, device="auto"):
        from geoworld_open.client.reference_experiment import ReferencePreview, ReferencePreviewRequest
        request = ReferencePreviewRequest(prompt=prompt, selection=selection, project_id=project_id, device=device)
        return ReferencePreview.model_validate(self._json_request("POST", "/references/preview", request.model_dump(mode="json")))

    def preview_fwi(self, *, prompt=None, selection=None, preference=None, intermediate_results=None):
        from geoworld_open.client.fwi import FWIPreview, FWIPreviewRequest
        from geoworld_open.client.execution import ExecutionPreference
        from geoworld_open.client.intermediate_results import IntermediateResultPolicy
        request = FWIPreviewRequest(prompt=prompt, selection=selection, preference=preference or ExecutionPreference(),
            intermediate_results=intermediate_results or IntermediateResultPolicy())
        return FWIPreview.model_validate(self._json_request('POST', '/fwi/preview', request.model_dump(mode='json')))

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

    def preview_intent(self, prompt: str, *, has_csv: bool = False) -> dict[str, object]:
        return self._json_request(
            "POST",
            "/intent/preview",
            {"prompt": prompt, "has_csv": has_csv},
        )

    def submit_job(self, request: JobCreateRequest) -> JobCreateResponse:
        payload = self._json_request("POST", "/jobs", request.model_dump(mode="json"))
        return JobCreateResponse.model_validate(payload)

    def preview_rtm(self, *, prompt=None, experiment=None, device=None, operation='rtm'):
        from geoworld_open.client.rtm import RTMPreview, RTMPreviewRequest
        request = RTMPreviewRequest(prompt=prompt, experiment=experiment, device=device, operation=operation)
        return RTMPreview.model_validate(self._json_request("POST", "/rtm/preview", request.model_dump(mode="json")))

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
    def _upload_body(content: UploadSource) -> RequestBody:
        if isinstance(content, bytes):
            return content
        if isinstance(content, (bytearray, memoryview)):
            return bytes(content)
        reader = getattr(content, "read", None)
        if callable(reader):
            def read_chunks() -> Iterable[bytes]:
                while True:
                    chunk = reader(UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        return
                    if not isinstance(chunk, (bytes, bytearray, memoryview)):
                        raise GeoWorldClientError("SEG-Y upload source returned non-binary data")
                    yield bytes(chunk)
            return read_chunks()

        def validated_chunks() -> Iterable[bytes]:
            try:
                iterator = iter(content)
            except TypeError as exc:
                raise TypeError("content must be bytes, a binary file, or byte chunks") from exc
            for chunk in iterator:
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    raise GeoWorldClientError("SEG-Y upload source returned non-binary data")
                if chunk:
                    yield bytes(chunk)
        return validated_chunks()

    def _send_binary(
        self,
        method: str,
        path: str,
        body: RequestBody,
        *,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if self._token:
            request_headers["Authorization"] = f"Bearer {self._token}"
        return self._transport.send(
            method,
            f"{self._base_url}{path}",
            request_headers,
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
