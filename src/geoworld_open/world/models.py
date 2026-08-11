"""Immutable contracts for the minimal GeoWorld Open world kernel."""

from __future__ import annotations

import math
import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field as PydanticField,
    StringConstraints,
    field_validator,
    model_validator,
)


Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
MetadataValue = str | int | float | bool | None
MetadataItems = tuple[tuple[Identifier, MetadataValue], ...]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _require_unique_metadata(items: MetadataItems, *, owner: str) -> MetadataItems:
    keys = [key for key, _ in items]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{owner} metadata keys must be unique")
    return items


class FrozenModel(BaseModel):
    """Strict, immutable, JSON-serializable contract base."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        validate_default=True,
    )


class TemporalValue(FrozenModel):
    """One explicit absolute timestamp or finite relative/model time."""

    absolute_time: datetime | None = None
    relative_value: float | None = None
    relative_unit: NonEmptyStr | None = None

    @field_validator("absolute_time")
    @classmethod
    def validate_absolute_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("absolute_time must be timezone-aware")
        return value

    @field_validator("relative_value")
    @classmethod
    def validate_relative_value(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("relative_value must be finite")
        return value

    @model_validator(mode="after")
    def validate_mode(self) -> "TemporalValue":
        has_absolute = self.absolute_time is not None
        has_relative_value = self.relative_value is not None
        has_relative_unit = self.relative_unit is not None
        if has_relative_value != has_relative_unit:
            raise ValueError("relative_value and relative_unit must be provided together")
        if has_absolute == has_relative_value:
            raise ValueError("provide exactly one absolute or relative time mode")
        return self


def _validate_temporal_interval(
    valid_from: TemporalValue | None,
    valid_to: TemporalValue | None,
) -> None:
    if valid_from is None or valid_to is None:
        return
    if (valid_from.absolute_time is None) != (valid_to.absolute_time is None):
        raise ValueError("valid_from and valid_to must use the same temporal mode")
    if valid_from.absolute_time is not None:
        end = valid_to.absolute_time
        if end is None:
            raise AssertionError("temporal mode validation failed")
        if end < valid_from.absolute_time:
            raise ValueError("valid_to must not precede valid_from")
        return
    if valid_from.relative_unit != valid_to.relative_unit:
        raise ValueError("relative validity bounds must use the same unit")
    start_value = valid_from.relative_value
    end_value = valid_to.relative_value
    if start_value is None or end_value is None:
        raise AssertionError("relative time validation failed")
    if end_value < start_value:
        raise ValueError("valid_to must not precede valid_from")


class SubjectKind(str, Enum):
    ENTITY = "entity"
    RELATION = "relation"
    FIELD_DEFINITION = "field_definition"
    FIELD_BINDING = "field_binding"
    WORLD_STATE = "world_state"
    SUPPORT = "support"
    REPRESENTATION = "representation"
    OBSERVATION = "observation"


class SubjectRef(FrozenModel):
    """Typed reference to a justified semantic subject."""

    kind: SubjectKind
    subject_id: Identifier
    representation_version: Identifier | None = None

    @model_validator(mode="after")
    def validate_representation_version(self) -> "SubjectRef":
        is_representation = self.kind == SubjectKind.REPRESENTATION
        if is_representation != (self.representation_version is not None):
            raise ValueError(
                "representation_version is required only for representation references"
            )
        return self


class Entity(FrozenModel):
    """Persistent semantic identity independent of state and representation."""

    entity_id: Identifier
    entity_type: Identifier
    label: NonEmptyStr | None = None
    provenance_ids: tuple[Identifier, ...] = ()


class Directionality(str, Enum):
    DIRECTED = "directed"
    UNDIRECTED = "undirected"


class Relation(FrozenModel):
    """Typed relationship mechanics without domain-specific validity rules."""

    relation_id: Identifier
    source_entity_id: Identifier
    relation_type: Identifier
    target_entity_id: Identifier
    directionality: Directionality = Directionality.DIRECTED
    valid_from_state_id: Identifier | None = None
    valid_to_state_id: Identifier | None = None
    qualifiers: MetadataItems = ()
    provenance_ids: tuple[Identifier, ...] = ()

    @field_validator("qualifiers")
    @classmethod
    def validate_qualifiers(cls, value: MetadataItems) -> MetadataItems:
        return _require_unique_metadata(value, owner="Relation qualifier")


class FrameScope(str, Enum):
    GLOBAL = "global"
    LOCAL = "local"


class PositiveDirection(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    UP = "up"
    DOWN = "down"
    UNSPECIFIED = "unspecified"


class ReferenceFrame(FrozenModel):
    """Minimal coordinate meaning for spatial representations."""

    frame_id: Identifier
    label: NonEmptyStr
    scope: FrameScope
    coordinate_names: tuple[Identifier, ...] = PydanticField(min_length=1)
    units: tuple[NonEmptyStr, ...] = PydanticField(min_length=1)
    positive_directions: tuple[PositiveDirection, ...] = PydanticField(min_length=1)
    provenance_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_axes(self) -> "ReferenceFrame":
        lengths = {
            len(self.coordinate_names),
            len(self.units),
            len(self.positive_directions),
        }
        if len(lengths) != 1:
            raise ValueError("coordinate names, units, and directions must have equal length")
        if len(set(self.coordinate_names)) != len(self.coordinate_names):
            raise ValueError("coordinate names must be unique")
        return self


class SupportKind(str, Enum):
    REGULAR_GRID = "regular_grid"
    CELLS = "cells"
    POINTS = "points"
    CURVE = "curve"
    SURFACE = "surface"
    VOLUME = "volume"
    NON_SPATIAL = "non_spatial"


class Support(FrozenModel):
    """Domain on which representation values are defined."""

    support_id: Identifier
    support_kind: SupportKind
    dimension_names: tuple[Identifier, ...] = ()
    shape: tuple[int, ...] = ()
    reference_frame_id: Identifier | None = None
    provenance_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_dimensions(self) -> "Support":
        if len(self.dimension_names) != len(self.shape):
            raise ValueError("support dimension_names and shape must have equal length")
        if len(set(self.dimension_names)) != len(self.dimension_names):
            raise ValueError("support dimension names must be unique")
        if any(size <= 0 for size in self.shape):
            raise ValueError("support shape values must be positive")
        if self.support_kind == SupportKind.NON_SPATIAL and self.reference_frame_id:
            raise ValueError("non-spatial support cannot reference a spatial frame")
        return self


class RepresentationKind(str, Enum):
    ARRAY = "array"
    GRID = "grid"
    SURFACE = "surface"
    CURVE = "curve"
    TABLE = "table"
    IMAGE = "image"


class Representation(FrozenModel):
    """One immutable, uniquely version-addressable computational depiction."""

    representation_id: Identifier
    version: Identifier
    subjects: tuple[SubjectRef, ...] = PydanticField(min_length=1)
    kind: RepresentationKind
    artifact_uri: NonEmptyStr
    content_sha256: str
    media_type: NonEmptyStr | None = None
    support_id: Identifier | None = None
    reference_frame_id: Identifier | None = None
    dimensions: tuple[Identifier, ...] = ()
    derived_from: tuple[SubjectRef, ...] = ()
    provenance_ids: tuple[Identifier, ...] = ()

    @field_validator("subjects")
    @classmethod
    def validate_subjects(cls, values: tuple[SubjectRef, ...]) -> tuple[SubjectRef, ...]:
        if len(set(values)) != len(values):
            raise ValueError("Representation subjects must be unique")
        return values

    @field_validator("content_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("content_sha256 must be 64 lowercase hexadecimal characters")
        return value

    @field_validator("derived_from")
    @classmethod
    def validate_derived_from(cls, values: tuple[SubjectRef, ...]) -> tuple[SubjectRef, ...]:
        if any(value.kind != SubjectKind.REPRESENTATION for value in values):
            raise ValueError("derived_from entries must reference representation versions")
        if len(set(values)) != len(values):
            raise ValueError("derived_from entries must be unique")
        return values

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, values: tuple[Identifier, ...]) -> tuple[Identifier, ...]:
        if len(set(values)) != len(values):
            raise ValueError("Representation dimensions must be unique")
        return values

    @property
    def ref(self) -> SubjectRef:
        return SubjectRef(
            kind=SubjectKind.REPRESENTATION,
            subject_id=self.representation_id,
            representation_version=self.version,
        )


class ValueKind(str, Enum):
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"


class PhysicalRank(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    SCALAR = "scalar"
    VECTOR = "vector"
    COVECTOR = "covector"
    TENSOR_2 = "tensor_2"


class Missingness(str, Enum):
    FORBID = "forbid"
    ALLOW = "allow"
    MASK = "mask"


class FieldDefinition(FrozenModel):
    """Reusable semantic definition independent of subject, state, or values."""

    field_id: Identifier
    canonical_name: Identifier
    unit: NonEmptyStr
    value_kind: ValueKind
    physical_rank: PhysicalRank
    missingness: Missingness = Missingness.FORBID
    admissible_support_kinds: tuple[SupportKind, ...] = ()
    domain_constraint_refs: tuple[Identifier, ...] = ()
    provenance_ids: tuple[Identifier, ...] = ()


class FieldBinding(FrozenModel):
    """State-specific occurrence of a reusable FieldDefinition."""

    binding_id: Identifier
    field_definition_id: Identifier
    subject: SubjectRef
    world_state_id: Identifier
    representation: SubjectRef
    support_id: Identifier | None = None
    scale_label: NonEmptyStr | None = None
    valid_from: TemporalValue | None = None
    valid_to: TemporalValue | None = None
    provenance_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_binding(self) -> "FieldBinding":
        if self.representation.kind != SubjectKind.REPRESENTATION:
            raise ValueError("FieldBinding representation must reference an exact version")
        _validate_temporal_interval(self.valid_from, self.valid_to)
        return self


class WorldStateRole(str, Enum):
    ASSERTED = "asserted"
    HYPOTHETICAL = "hypothetical"
    SIMULATED = "simulated"
    GROUND_TRUTH = "ground_truth"


class WorldState(FrozenModel):
    """Immutable, role-aware state assertion with explicit lineage."""

    state_id: Identifier
    world_id: Identifier
    role: WorldStateRole
    valid_from: TemporalValue | None = None
    valid_to: TemporalValue | None = None
    parent_state_id: Identifier | None = None
    field_binding_ids: tuple[Identifier, ...] = ()
    representation_refs: tuple[SubjectRef, ...] = ()
    provenance_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_state(self) -> "WorldState":
        if self.parent_state_id == self.state_id:
            raise ValueError("a WorldState cannot be its own parent")
        _validate_temporal_interval(self.valid_from, self.valid_to)
        if any(ref.kind != SubjectKind.REPRESENTATION for ref in self.representation_refs):
            raise ValueError("representation_refs must identify exact representation versions")
        if len(set(self.field_binding_ids)) != len(self.field_binding_ids):
            raise ValueError("field_binding_ids must be unique")
        return self


GROUND_TRUTH_SCOPE = (
    "ground_truth is reserved for states whose truth is known by construction, "
    "such as synthetic experiments"
)


class ObservationStatus(str, Enum):
    ACQUIRED = "acquired"
    SYNTHETIC = "synthetic"


class Observation(FrozenModel):
    """Immutable evidence, explicitly distinct from WorldState."""

    observation_id: Identifier
    world_id: Identifier
    status: ObservationStatus
    subjects: tuple[SubjectRef, ...] = PydanticField(min_length=1)
    representation: SubjectRef
    acquisition_time: TemporalValue | None = None
    valid_time: TemporalValue | None = None
    quality: MetadataItems = ()
    provenance_ids: tuple[Identifier, ...] = ()

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, value: MetadataItems) -> MetadataItems:
        return _require_unique_metadata(value, owner="Observation quality")

    @model_validator(mode="after")
    def validate_observation(self) -> "Observation":
        if self.representation.kind != SubjectKind.REPRESENTATION:
            raise ValueError("Observation representation must reference an exact version")
        if self.status == ObservationStatus.ACQUIRED and self.acquisition_time is None:
            raise ValueError("acquired Observation requires acquisition_time")
        return self


class Provenance(FrozenModel):
    """Immutable scientific derivation record, separate from telemetry."""

    provenance_id: Identifier
    activity_type: Identifier
    method: NonEmptyStr
    inputs: tuple[SubjectRef, ...] = ()
    outputs: tuple[SubjectRef, ...] = ()
    parent_provenance_ids: tuple[Identifier, ...] = ()
    parameters: MetadataItems = ()
    recorded_at: datetime | None = None

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: MetadataItems) -> MetadataItems:
        return _require_unique_metadata(value, owner="Provenance parameter")

    @field_validator("parent_provenance_ids")
    @classmethod
    def validate_parent_ids(cls, values: tuple[Identifier, ...]) -> tuple[Identifier, ...]:
        if len(set(values)) != len(values):
            raise ValueError("parent_provenance_ids must be unique")
        return values
