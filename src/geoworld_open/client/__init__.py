"""Public client for the official GeoWorld product backend.

The client uses only documented HTTP endpoints and never imports private GeoWorld source.
"""

from geoworld_open.client.backend import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import (
    ArtifactInfo,
    AuthResponse,
    CapabilityCatalog,
    CapabilityDescription,
    JobCreateRequest,
    JobCreateResponse,
    JobResult,
    JobStatusResponse,
    LASQuicklookSettings,
    QACitation,
    UploadedLASFile,
    UserProfile,
)
from geoworld_open.client.scientific_experiment import (
    AcquisitionRequest,
    ConversationState,
    InversionRequest,
    ModelSelection,
    RequestedOutputs,
    ScientificExperimentDraft,
)
from geoworld_open.client.marmousi_forward import (
    MarmousiAcquisitionRequest,
    MarmousiForwardExperiment,
    MarmousiForwardPreview,
    MarmousiForwardPreviewRequest,
    MarmousiForwardResult,
    MarmousiForwardSettings,
    ResolvedMarmousiAcquisition,
)

__all__ = [
    "AcquisitionRequest",
    "ArtifactInfo",
    "AuthResponse",
    "CapabilityCatalog",
    "CapabilityDescription",
    "ConversationState",
    "GeoWorldBackendClient",
    "GeoWorldClientError",
    "InversionRequest",
    "JobCreateRequest",
    "JobCreateResponse",
    "JobResult",
    "JobStatusResponse",
    "LASQuicklookSettings",
    "MarmousiAcquisitionRequest",
    "MarmousiForwardExperiment",
    "MarmousiForwardPreview",
    "MarmousiForwardPreviewRequest",
    "MarmousiForwardResult",
    "MarmousiForwardSettings",
    "ModelSelection",
    "QACitation",
    "ResolvedMarmousiAcquisition",
    "RequestedOutputs",
    "ScientificExperimentDraft",
    "UploadedLASFile",
    "UserProfile",
]
