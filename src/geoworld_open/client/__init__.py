"""Public client for the official GeoWorld product backend.

The client uses only documented HTTP endpoints and never imports private GeoWorld source.
"""

from geoworld_open.client.backend import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import (
    ArtifactInfo,
    AuthResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobResult,
    JobStatusResponse,
    UserProfile,
)

__all__ = [
    "ArtifactInfo",
    "AuthResponse",
    "GeoWorldBackendClient",
    "GeoWorldClientError",
    "JobCreateRequest",
    "JobCreateResponse",
    "JobResult",
    "JobStatusResponse",
    "UserProfile",
]
