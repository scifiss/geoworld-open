"""PUBLIC_STANDARD contracts for bounded seismic data exploration.

The contracts describe views and analysis requests. They never carry host file
paths, authorize numerical solvers, or add a World Kernel concept.
"""
from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import Field, model_validator

from .execution import ExecutionContract


SeismicFormat = Literal["segy", "rsf"]
SeismicDimension = Literal["2d", "3d"]
VerticalDomain = Literal["time", "depth"]
ViewKind = Literal["auto", "section", "inline", "crossline", "vertical_slice", "trace", "subvolume"]
AnalysisKind = Literal["statistics", "histogram", "spectrum", "trace_comparison"]
ExplorerStatus = Literal["ready", "clarification_required", "unsupported"]


class SeismicAxis(ExecutionContract):
    name: str = Field(min_length=1, max_length=40)
    count: int = Field(ge=1)
    unit: str = Field(min_length=1, max_length=20)
    start: float
    step: float | None = None
    stop: float
    coordinates: list[float] = Field(default_factory=list, max_length=20_000)


class SeismicDatasetSummary(ExecutionContract):
    dataset_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    display_name: str = Field(min_length=1, max_length=255)
    format: SeismicFormat
    dimensionality: SeismicDimension
    vertical_domain: VerticalDomain
    sample_interval: float = Field(gt=0)
    sample_unit: Literal["s", "m"]
    shape: list[int] = Field(min_length=2, max_length=3)
    axes: list[SeismicAxis] = Field(min_length=2, max_length=3)
    geometry_status: Literal["established", "declared_2d"]
    amplitude_min: float
    amplitude_max: float
    amplitude_scope: str = Field(min_length=1, max_length=160)
    source: str = Field(min_length=1, max_length=300)
    provenance: dict[str, Any] = Field(default_factory=dict)


class SeismicWindow(ExecutionContract):
    vertical_start: float | None = None
    vertical_stop: float | None = None
    trace_start: int | None = Field(default=None, ge=0)
    trace_stop: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def ordered(self):
        if self.vertical_start is not None and self.vertical_stop is not None:
            if self.vertical_start >= self.vertical_stop:
                raise ValueError("Vertical window stop must exceed start")
        if self.trace_start is not None and self.trace_stop is not None:
            if self.trace_start >= self.trace_stop:
                raise ValueError("Trace window stop must exceed start")
        return self


class SeismicViewRequest(ExecutionContract):
    dataset_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    view_kind: ViewKind = "auto"
    inline: int | None = None
    crossline: int | None = None
    vertical_coordinate: float | None = None
    trace_index: int | None = Field(default=None, ge=0)
    window: SeismicWindow = Field(default_factory=SeismicWindow)
    max_output_samples: int = Field(default=500_000, ge=100, le=1_000_000)


class SeismicViewData(ExecutionContract):
    dataset: SeismicDatasetSummary
    request: SeismicViewRequest
    title: str = Field(min_length=1, max_length=300)
    shape: list[int] = Field(min_length=1, max_length=3)
    horizontal_label: str = Field(min_length=1, max_length=80)
    horizontal_unit: str = Field(min_length=1, max_length=20)
    horizontal_coordinates: list[float] = Field(default_factory=list, max_length=20_000)
    vertical_label: str = Field(min_length=1, max_length=80)
    vertical_unit: str = Field(min_length=1, max_length=20)
    vertical_coordinates: list[float] = Field(default_factory=list, max_length=20_000)
    values: list[Any]
    amplitude_min: float
    amplitude_max: float
    selection_summary: str = Field(min_length=1, max_length=500)
    display_note: str = "Display clipping and normalization do not alter source samples."
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_payload(self):
        if math.prod(self.shape) > 1_000_000:
            raise ValueError("Seismic view payload exceeds one million samples")
        return self


class SeismicAnalysisRequest(ExecutionContract):
    kind: AnalysisKind
    trace_index: int | None = Field(default=None, ge=0)
    compare_trace_index: int | None = Field(default=None, ge=0)
    histogram_bins: int = Field(default=40, ge=5, le=200)


class SeismicAnalysisResult(ExecutionContract):
    kind: AnalysisKind
    summary: str = Field(min_length=1, max_length=1000)
    statistics: dict[str, float] = Field(default_factory=dict)
    x: list[float] = Field(default_factory=list, max_length=20_000)
    y: list[float] = Field(default_factory=list, max_length=20_000)
    secondary_y: list[float] = Field(default_factory=list, max_length=20_000)
    dominant_frequency_hz: float | None = Field(default=None, ge=0)


class SeismicConversationTurn(ExecutionContract):
    user_text: str = Field(min_length=1, max_length=8000)
    assistant_summary: str = Field(min_length=1, max_length=1000)
    patched_fields: list[str] = Field(default_factory=list, max_length=20)
    status: ExplorerStatus


class SeismicExplorerState(ExecutionContract):
    conversation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    active_dataset_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    current_view: SeismicViewRequest
    selected_trace: int | None = Field(default=None, ge=0)
    selected_region: SeismicWindow | None = None
    requested_analysis: SeismicAnalysisRequest | None = None
    visible_history: list[SeismicConversationTurn] = Field(default_factory=list, max_length=200)
    recent_context: list[SeismicConversationTurn] = Field(default_factory=list, max_length=6)
    status: ExplorerStatus = "ready"
    issues: list[str] = Field(default_factory=list, max_length=20)


class SeismicConversationRequest(ExecutionContract):
    prompt: str = Field(min_length=1, max_length=8000)
    dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{24}$")
    conversation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class SeismicExplorerResponse(ExecutionContract):
    state: SeismicExplorerState
    view: SeismicViewData | None = None
    analysis: SeismicAnalysisResult | None = None


class SeismicDatasetCatalog(ExecutionContract):
    datasets: list[SeismicDatasetSummary] = Field(default_factory=list, max_length=1000)
    warnings: list[str] = Field(default_factory=list, max_length=1000)
