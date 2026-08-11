"""xarray adapter for numerical FieldBindings; semantic models remain authoritative."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

import numpy as np
import xarray as xr

from geoworld_open.world.models import (
    FieldBinding,
    FieldDefinition,
    Missingness,
    PositiveDirection,
    Provenance,
    ReferenceFrame,
    Representation,
    RepresentationKind,
    SubjectKind,
    SubjectRef,
    Support,
    WorldState,
)


_DATASET_ATTRS = {
    "geoworld:world_id",
    "geoworld:state_id",
    "geoworld:representation_id",
    "geoworld:representation_version",
    "geoworld:support_id",
    "geoworld:reference_frame_id",
}
_VARIABLE_ATTRS = {
    "geoworld:field_definition_id",
    "geoworld:field_binding_id",
    "geoworld:physical_rank",
}


def _canonical_json_value(value: object, *, path: str) -> object:
    if isinstance(value, np.generic):
        return _canonical_json_value(value.item(), path=path)
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            raise TypeError(f"{path} contains an unsupported object-dtype array")
        return _canonical_json_value(value.tolist(), path=path)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError(f"{path} metadata mapping keys must be strings")
        return {
            key: _canonical_json_value(item, path=f"{path}.{key}")
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _canonical_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not np.isfinite(value):
            raise TypeError(f"{path} metadata float must be finite")
        return value
    raise TypeError(f"{path} contains unsupported metadata type {type(value).__name__}")


def _canonical_attrs(attrs: Mapping[object, object]) -> bytes:
    if any(not isinstance(key, str) for key in attrs):
        raise TypeError("xarray metadata keys must be strings for canonical hashing")
    payload = {
        key: _canonical_json_value(attrs[key], path=f"attrs.{key}")
        for key in attrs
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _canonical_array(values: np.ndarray) -> np.ndarray:
    if values.dtype.hasobject:
        raise TypeError("xarray adapter does not accept object-dtype values")
    dtype = values.dtype.newbyteorder("<")
    normalized = np.asarray(values, dtype=dtype)
    if np.issubdtype(dtype, np.floating):
        normalized = np.array(normalized, copy=True)
        normalized[np.isnan(normalized)] = np.nan
    elif np.issubdtype(dtype, np.complexfloating):
        normalized = np.array(normalized, copy=True)
        normalized.real[np.isnan(normalized.real)] = np.nan
        normalized.imag[np.isnan(normalized.imag)] = np.nan
    return np.ascontiguousarray(normalized)


def _is_ordered_subset(values: tuple[str, ...], candidates: tuple[str, ...]) -> bool:
    positions = {value: index for index, value in enumerate(candidates)}
    try:
        indices = [positions[value] for value in values]
    except KeyError:
        return False
    return indices == sorted(indices)


def _validate_variable_values(
    values: np.ndarray,
    definition: FieldDefinition,
    variable_name: str,
) -> None:
    if values.dtype.hasobject:
        raise TypeError(f"variable {variable_name!r} has unsupported object dtype")
    if definition.missingness == Missingness.MASK:
        raise ValueError(
            f"variable {variable_name!r} requests MASK missingness, which requires "
            "an explicit mask representation beyond the Gate-2 adapter"
        )

    if np.issubdtype(values.dtype, np.inexact):
        missing = np.isnan(values)
        infinite = np.isinf(values)
    elif np.issubdtype(values.dtype, np.datetime64) or np.issubdtype(
        values.dtype, np.timedelta64
    ):
        missing = np.isnat(values)
        infinite = np.zeros(values.shape, dtype=bool)
    else:
        missing = np.zeros(values.shape, dtype=bool)
        infinite = np.zeros(values.shape, dtype=bool)

    if np.any(infinite):
        raise ValueError(f"variable {variable_name!r} contains infinite values")
    if definition.missingness == Missingness.FORBID and np.any(missing):
        raise ValueError(
            f"variable {variable_name!r} contains missing values forbidden by FieldDefinition"
        )


def dataset_content_sha256(dataset: xr.Dataset) -> str:
    """Hash one normalized Dataset including values, coordinates, and metadata."""
    digest = hashlib.sha256()
    digest.update(_canonical_attrs(dataset.attrs))
    for category, variables in (("coord", dataset.coords), ("data", dataset.data_vars)):
        for name in sorted(variables):
            array = variables[name]
            values = _canonical_array(np.asarray(array.values))
            digest.update(category.encode())
            digest.update(name.encode())
            digest.update(json.dumps(array.dims).encode())
            digest.update(values.dtype.str.encode())
            digest.update(json.dumps(values.shape).encode())
            digest.update(np.ascontiguousarray(values).tobytes())
            digest.update(_canonical_attrs(array.attrs))
    return digest.hexdigest()


class XarrayBundle:
    """Bounded in-memory adapter that never exposes its stored Dataset mutably."""

    __slots__ = ("_dataset", "representation", "variable_bindings")

    def __init__(
        self,
        dataset: xr.Dataset,
        representation: Representation,
        variable_bindings: tuple[tuple[str, str], ...],
    ) -> None:
        stored = dataset.copy(deep=True)
        if dataset_content_sha256(stored) != representation.content_sha256:
            raise ValueError("Dataset content does not match Representation content_sha256")
        for variable in stored.variables.values():
            values = np.asarray(variable.values)
            values.setflags(write=False)
        object.__setattr__(self, "_dataset", stored)
        object.__setattr__(self, "representation", representation)
        object.__setattr__(self, "variable_bindings", variable_bindings)

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("XarrayBundle is immutable")
        object.__setattr__(self, name, value)

    def to_dataset(self) -> xr.Dataset:
        """Return a deep copy so callers cannot mutate the versioned content."""
        return self._dataset.copy(deep=True)

    def values_for_binding(self, binding_id: str) -> np.ndarray:
        """Return copied numerical values for one semantic FieldBinding."""
        by_binding = {binding: variable for variable, binding in self.variable_bindings}
        if binding_id not in by_binding:
            raise KeyError(binding_id)
        return np.array(self._dataset[by_binding[binding_id]].values, copy=True)


def create_xarray_bundle(
    dataset: xr.Dataset,
    *,
    world_id: str,
    state: WorldState,
    support: Support,
    reference_frame: ReferenceFrame | None,
    representation_id: str,
    version: str,
    variable_bindings: Mapping[str, FieldBinding],
    field_definitions: Sequence[FieldDefinition],
    provenance: Provenance,
    derived_from: tuple[SubjectRef, ...] = (),
) -> XarrayBundle:
    """Normalize and bind numerical variables without making attrs authoritative."""
    if state.world_id != world_id:
        raise ValueError("state belongs to a different World")
    if support.reference_frame_id != (
        reference_frame.frame_id if reference_frame is not None else None
    ):
        raise ValueError("Support and ReferenceFrame do not agree")
    if set(dataset.data_vars) != set(variable_bindings):
        raise ValueError("every Dataset data variable must map to exactly one FieldBinding")
    binding_ids = [binding.binding_id for binding in variable_bindings.values()]
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError("each FieldBinding may map to only one Dataset variable")
    dataset_dimensions = tuple(dataset.sizes)
    if not _is_ordered_subset(support.dimension_names, dataset_dimensions):
        raise ValueError("Dataset dimensions do not contain Support dimensions in order")
    if any(
        dataset.sizes[dimension] != size
        for dimension, size in zip(support.dimension_names, support.shape)
    ):
        raise ValueError("Dataset shape does not match Support")
    reserved_dataset = _DATASET_ATTRS.intersection(dataset.attrs)
    if reserved_dataset:
        raise ValueError(f"input Dataset contains reserved semantic attrs: {sorted(reserved_dataset)}")

    definitions = {definition.field_id: definition for definition in field_definitions}
    if len(definitions) != len(field_definitions):
        raise ValueError("FieldDefinition IDs must be unique")

    expected_ref = SubjectRef(
        kind=SubjectKind.REPRESENTATION,
        subject_id=representation_id,
        representation_version=version,
    )
    normalized = dataset.copy(deep=True)
    binding_pairs: list[tuple[str, str]] = []
    subjects: list[SubjectRef] = []

    for variable_name in sorted(variable_bindings):
        binding = variable_bindings[variable_name]
        if binding.field_definition_id not in definitions:
            raise ValueError(f"unknown FieldDefinition for variable {variable_name!r}")
        if binding.world_state_id != state.state_id:
            raise ValueError(f"FieldBinding for {variable_name!r} belongs to another state")
        if binding.support_id != support.support_id:
            raise ValueError(f"FieldBinding for {variable_name!r} uses another Support")
        if binding.representation != expected_ref:
            raise ValueError(f"FieldBinding for {variable_name!r} references another Representation")
        if binding.binding_id not in state.field_binding_ids:
            raise ValueError(f"WorldState does not include FieldBinding {binding.binding_id!r}")

        definition = definitions[binding.field_definition_id]
        variable = normalized[variable_name]
        if not _is_ordered_subset(support.dimension_names, tuple(variable.dims)):
            raise ValueError(
                f"variable {variable_name!r} dimensions do not contain Support dimensions in order"
            )
        reserved_variable = _VARIABLE_ATTRS.intersection(variable.attrs)
        if reserved_variable:
            raise ValueError(
                f"input variable {variable_name!r} contains reserved semantic attrs"
            )
        supplied_unit = variable.attrs.get("units")
        if supplied_unit is not None and supplied_unit != definition.unit:
            raise ValueError(
                f"variable {variable_name!r} unit conflicts with FieldDefinition"
            )
        _validate_variable_values(np.asarray(variable.values), definition, variable_name)
        variable.attrs.update(
            {
                "units": definition.unit,
                "geoworld:field_definition_id": definition.field_id,
                "geoworld:field_binding_id": binding.binding_id,
                "geoworld:physical_rank": definition.physical_rank.value,
            }
        )
        binding_pairs.append((variable_name, binding.binding_id))
        subjects.append(
            SubjectRef(kind=SubjectKind.FIELD_BINDING, subject_id=binding.binding_id)
        )

    if reference_frame is not None:
        if not _is_ordered_subset(
            support.dimension_names,
            reference_frame.coordinate_names,
        ):
            raise ValueError("Support dimensions are incompatible with ReferenceFrame axes")
        frame_axes = {
            name: (unit, direction)
            for name, unit, direction in zip(
                reference_frame.coordinate_names,
                reference_frame.units,
                reference_frame.positive_directions,
            )
        }
        for dimension in support.dimension_names:
            if dimension not in normalized.coords:
                continue
            coordinate = normalized.coords[dimension]
            if coordinate.ndim != 1 or coordinate.dims != (dimension,):
                raise ValueError(
                    f"coordinate {dimension!r} must be one-dimensional on its own axis"
                )
            expected_unit, direction = frame_axes[dimension]
            supplied_unit = coordinate.attrs.get("units")
            if supplied_unit is not None and supplied_unit != expected_unit:
                raise ValueError(
                    f"coordinate {dimension!r} unit conflicts with ReferenceFrame"
                )
            coordinate.attrs["units"] = expected_unit
            coordinate_values = np.asarray(coordinate.values)
            if np.issubdtype(coordinate_values.dtype, np.number) and coordinate_values.size > 1:
                if not np.all(np.isfinite(coordinate_values)):
                    raise ValueError(f"coordinate {dimension!r} must contain finite values")
                differences = np.diff(coordinate_values)
                if direction == PositiveDirection.INCREASING and not np.all(differences > 0):
                    raise ValueError(f"coordinate {dimension!r} must be strictly increasing")
                if direction == PositiveDirection.DECREASING and not np.all(differences < 0):
                    raise ValueError(f"coordinate {dimension!r} must be strictly decreasing")

    normalized.attrs.update(
        {
            "geoworld:world_id": world_id,
            "geoworld:state_id": state.state_id,
            "geoworld:representation_id": representation_id,
            "geoworld:representation_version": version,
            "geoworld:support_id": support.support_id,
            "geoworld:reference_frame_id": (
                reference_frame.frame_id if reference_frame is not None else ""
            ),
        }
    )
    content_sha256 = dataset_content_sha256(normalized)
    representation = Representation(
        representation_id=representation_id,
        version=version,
        subjects=tuple(subjects),
        kind=RepresentationKind.ARRAY,
        artifact_uri=f"memory://{representation_id}/{version}",
        content_sha256=content_sha256,
        media_type="application/x-xarray-dataset",
        support_id=support.support_id,
        reference_frame_id=(reference_frame.frame_id if reference_frame else None),
        dimensions=tuple(normalized.sizes),
        derived_from=derived_from,
        provenance_ids=(provenance.provenance_id,),
    )
    return XarrayBundle(normalized, representation, tuple(binding_pairs))
