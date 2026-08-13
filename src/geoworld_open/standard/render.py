"""Renderer-independent 2D, 3D, and 4D request/result contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from geoworld_open.standard.capabilities import ContractModel
from geoworld_open.standard.version import STANDARD_VERSION
from geoworld_open.world.models import Identifier, NonEmptyStr, SubjectKind, SubjectRef, TemporalValue


class RenderDimension(str, Enum):
    TWO_D = "2d"
    THREE_D = "3d"
    FOUR_D = "4d"


class ColorScaleKind(str, Enum):
    SEQUENTIAL = "sequential"
    DIVERGING = "diverging"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"


class RenderFormat(str, Enum):
    PNG = "png"
    SVG = "svg"
    HTML = "html"
    GLTF = "gltf"
    MP4 = "mp4"
    GIF = "gif"


class CategoryColor(ContractModel):
    value: str | int | bool
    label: NonEmptyStr
    color: NonEmptyStr


class ColorScale(ContractModel):
    kind: ColorScaleKind
    palette: NonEmptyStr
    minimum: float | None = None
    maximum: float | None = None
    center: float | None = None
    categories: tuple[CategoryColor, ...] = ()
    missing_color: NonEmptyStr = "#d1d5db"

    @model_validator(mode="after")
    def validate_semantics(self) -> "ColorScale":
        if self.minimum is not None and self.maximum is not None and self.maximum <= self.minimum:
            raise ValueError("color-scale maximum must exceed minimum")
        categorical = self.kind in {ColorScaleKind.CATEGORICAL, ColorScaleKind.BOOLEAN}
        if categorical != bool(self.categories):
            raise ValueError("categorical and boolean scales require category definitions")
        if self.kind == ColorScaleKind.DIVERGING and self.center is None:
            raise ValueError("diverging scales require an explicit center")
        return self


class FieldLayer(ContractModel):
    layer_id: Identifier
    field_id: Identifier
    representation: SubjectRef
    support_id: Identifier | None = None
    unit: NonEmptyStr | None = None
    color_scale: ColorScale
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    visible: bool = True

    @model_validator(mode="after")
    def validate_representation(self) -> "FieldLayer":
        if self.representation.kind != SubjectKind.REPRESENTATION:
            raise ValueError("render layers require an exact Representation reference")
        return self


class OverlaySpec(ContractModel):
    overlay_id: Identifier
    kind: Identifier
    representation: SubjectRef | None = None
    label: NonEmptyStr | None = None
    color: NonEmptyStr = "#111827"

    @model_validator(mode="after")
    def validate_representation(self) -> "OverlaySpec":
        if self.representation and self.representation.kind != SubjectKind.REPRESENTATION:
            raise ValueError("overlay representation must identify an exact version")
        return self


class View2D(ContractModel):
    x_axis: Identifier
    y_axis: Identifier
    vertical_exaggeration: float = Field(default=1.0, gt=0.0)


class Camera3D(ContractModel):
    position: tuple[float, float, float]
    target: tuple[float, float, float]
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    field_of_view_deg: float = Field(default=45.0, gt=0.0, lt=180.0)


class TimeSequence(ContractModel):
    times: tuple[TemporalValue, ...] = Field(min_length=2)
    frames_per_second: float = Field(default=12.0, gt=0.0)
    loop: bool = False


class RenderOutputSpec(ContractModel):
    format: RenderFormat
    width_px: int = Field(default=1600, ge=64, le=16384)
    height_px: int = Field(default=900, ge=64, le=16384)
    dpi: int = Field(default=150, ge=36, le=1200)
    transparent_background: bool = False


class RenderSpec(ContractModel):
    schema_version: str = STANDARD_VERSION
    render_id: Identifier
    dimension: RenderDimension
    layers: tuple[FieldLayer, ...] = Field(min_length=1)
    overlays: tuple[OverlaySpec, ...] = ()
    view_2d: View2D | None = None
    camera_3d: Camera3D | None = None
    time_sequence: TimeSequence | None = None
    output: RenderOutputSpec

    @model_validator(mode="after")
    def validate_dimension_contract(self) -> "RenderSpec":
        if self.dimension == RenderDimension.TWO_D:
            if self.view_2d is None or self.camera_3d is not None or self.time_sequence is not None:
                raise ValueError("2D rendering requires view_2d and forbids 3D/time controls")
        elif self.dimension == RenderDimension.THREE_D:
            if self.camera_3d is None or self.view_2d is not None or self.time_sequence is not None:
                raise ValueError("3D rendering requires camera_3d and forbids 2D/time controls")
        else:
            if self.camera_3d is None or self.time_sequence is None or self.view_2d is not None:
                raise ValueError("4D rendering requires camera_3d and time_sequence")
            if self.output.format not in {RenderFormat.MP4, RenderFormat.GIF, RenderFormat.HTML}:
                raise ValueError("4D output must be mp4, gif, or html")
        layer_ids = [item.layer_id for item in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("render layer IDs must be unique")
        return self


class RenderRequest(ContractModel):
    request_id: Identifier
    world_id: Identifier
    state_id: Identifier
    spec: RenderSpec


class RenderArtifact(ContractModel):
    path: NonEmptyStr
    media_type: NonEmptyStr
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)


class RenderStatus(str, Enum):
    SUCCEEDED = "succeeded"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class RenderResult(ContractModel):
    request_id: Identifier
    status: RenderStatus
    artifacts: tuple[RenderArtifact, ...] = ()
    renderer_id: Identifier | None = None
    renderer_version: Identifier | None = None
    error_category: Identifier | None = None
    message: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "RenderResult":
        if self.status == RenderStatus.SUCCEEDED:
            if not self.artifacts or not self.renderer_id or not self.renderer_version:
                raise ValueError("successful render results require artifacts and renderer identity")
            if self.error_category is not None:
                raise ValueError("successful render results cannot contain an error category")
        elif self.artifacts:
            raise ValueError("unavailable or failed render results cannot claim artifacts")
        return self
