"""Reusable conformance checks for GeoWorld-compatible implementations."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr
from pydantic import BaseModel, ConfigDict

from geoworld_open.sdk import verify_manifest, verify_provenance
from geoworld_open.standard import (
    CapabilityContext,
    CapabilityRunResult,
    CapabilitySpec,
    PhysicsCapability,
    RenderRequest,
    RenderResult,
    RenderStatus,
)
from geoworld_open.standard.capabilities import VariableSpec, numpy_dtype_kind
from geoworld_open.world import StateTransition, World, apply_transition


class ConformanceIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class ConformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str
    conforms: bool
    checks: tuple[str, ...]
    issues: tuple[ConformanceIssue, ...] = ()


def _validate_variables(
    dataset: xr.Dataset,
    variables: tuple[VariableSpec, ...],
    *,
    owner: str,
) -> list[ConformanceIssue]:
    issues: list[ConformanceIssue] = []
    for variable in variables:
        if variable.name not in dataset:
            if variable.required:
                issues.append(ConformanceIssue(code="missing_variable", message=f"{owner} omits {variable.name}"))
            continue
        array = dataset[variable.name]
        if tuple(array.dims) != variable.dimensions:
            issues.append(
                ConformanceIssue(
                    code="dimension_mismatch",
                    message=f"{variable.name} has {tuple(array.dims)}, expected {variable.dimensions}",
                )
            )
        if array.attrs.get("units") != variable.unit:
            issues.append(
                ConformanceIssue(
                    code="unit_mismatch",
                    message=f"{variable.name} unit is {array.attrs.get('units')!r}, expected {variable.unit!r}",
                )
            )
        if variable.dtype_kind and numpy_dtype_kind(array.dtype) != variable.dtype_kind:
            issues.append(
                ConformanceIssue(
                    code="dtype_mismatch",
                    message=f"{variable.name} dtype does not match {variable.dtype_kind.value}",
                )
            )
    return issues


def check_capability(
    capability: PhysicsCapability,
    sample_input: xr.Dataset,
    *,
    context: CapabilityContext | None = None,
) -> ConformanceReport:
    """Execute and validate one capability without trusting its implementation."""

    checks = ["spec", "inputs", "execution", "immutability", "outputs", "determinism"]
    issues: list[ConformanceIssue] = []
    if not isinstance(capability, PhysicsCapability):
        return ConformanceReport(
            subject=type(capability).__name__,
            conforms=False,
            checks=("protocol",),
            issues=(ConformanceIssue(code="protocol", message="does not implement PhysicsCapability"),),
        )
    try:
        spec = CapabilitySpec.model_validate(capability.spec)
    except Exception as exc:
        return ConformanceReport(
            subject=type(capability).__name__,
            conforms=False,
            checks=("spec",),
            issues=(ConformanceIssue(code="invalid_spec", message=str(exc)),),
        )
    issues.extend(_validate_variables(sample_input, spec.inputs, owner="input"))
    if issues:
        return ConformanceReport(subject=spec.capability_id, conforms=False, checks=tuple(checks), issues=tuple(issues))

    before = sample_input.copy(deep=True)
    execution_context = context or CapabilityContext(seed=0)
    try:
        first = capability.execute(sample_input, execution_context)
    except Exception as exc:
        return ConformanceReport(
            subject=spec.capability_id,
            conforms=False,
            checks=tuple(checks),
            issues=(ConformanceIssue(code="execution_failed", message=str(exc)),),
        )
    if not isinstance(first, CapabilityRunResult):
        issues.append(ConformanceIssue(code="result_type", message="execute must return CapabilityRunResult"))
        return ConformanceReport(subject=spec.capability_id, conforms=False, checks=tuple(checks), issues=tuple(issues))
    try:
        xr.testing.assert_identical(sample_input, before)
    except AssertionError:
        issues.append(ConformanceIssue(code="input_mutation", message="capability mutated its input dataset"))

    issues.extend(_validate_variables(first.dataset, spec.outputs, owner="output"))
    allowed = {item.name for item in spec.inputs} | {item.name for item in spec.outputs}
    undeclared = sorted(set(first.dataset.data_vars) - allowed)
    if undeclared:
        issues.append(
            ConformanceIssue(code="undeclared_output", message=f"undeclared output variables: {undeclared}")
        )
    for variable in spec.inputs:
        if variable.name in before and variable.name in first.dataset:
            try:
                xr.testing.assert_identical(before[variable.name], first.dataset[variable.name])
            except AssertionError:
                issues.append(
                    ConformanceIssue(code="input_overwrite", message=f"capability overwrote {variable.name}")
                )

    if spec.deterministic:
        try:
            second = capability.execute(before.copy(deep=True), execution_context)
            for variable in spec.outputs:
                xr.testing.assert_identical(first.dataset[variable.name], second.dataset[variable.name])
        except Exception as exc:
            issues.append(ConformanceIssue(code="nondeterministic", message=str(exc)))
    return ConformanceReport(
        subject=spec.capability_id,
        conforms=not issues,
        checks=tuple(checks),
        issues=tuple(issues),
    )


def check_world(value: World | dict[str, object] | str | bytes) -> ConformanceReport:
    try:
        world = value if isinstance(value, World) else (
            World.model_validate_json(value) if isinstance(value, (str, bytes)) else World.model_validate(value)
        )
        verify_provenance(world)
    except Exception as exc:
        return ConformanceReport(
            subject="World", conforms=False, checks=("world", "provenance"),
            issues=(ConformanceIssue(code="invalid_world", message=str(exc)),),
        )
    return ConformanceReport(subject=world.world_id, conforms=True, checks=("world", "provenance"))


def check_transition(world: World, input_state_id: str, transition: StateTransition) -> ConformanceReport:
    before = world.model_dump_json()
    try:
        apply_transition(world, input_state_id, transition)
    except Exception as exc:
        unchanged = world.model_dump_json() == before
        suffix = "" if unchanged else "; input World was mutated"
        return ConformanceReport(
            subject=getattr(transition, "transition_id", type(transition).__name__),
            conforms=False,
            checks=("transition", "provenance", "immutability"),
            issues=(ConformanceIssue(code="invalid_transition", message=f"{exc}{suffix}"),),
        )
    return ConformanceReport(
        subject=transition.transition_id,
        conforms=world.model_dump_json() == before,
        checks=("transition", "provenance", "immutability"),
        issues=() if world.model_dump_json() == before else (
            ConformanceIssue(code="input_mutation", message="transition mutated its input World"),
        ),
    )


def check_render_contract(request: RenderRequest, result: RenderResult) -> ConformanceReport:
    issues: list[ConformanceIssue] = []
    try:
        RenderRequest.model_validate(request.model_dump(mode="python"))
        RenderResult.model_validate(result.model_dump(mode="python"))
    except Exception as exc:
        issues.append(ConformanceIssue(code="invalid_render_contract", message=str(exc)))
    if request.request_id != result.request_id:
        issues.append(ConformanceIssue(code="request_mismatch", message="render request_id mismatch"))
    if result.status == RenderStatus.SUCCEEDED:
        allowed = {item.value for item in request.spec.output.format.__class__}
        for artifact in result.artifacts:
            extension = Path(artifact.path).suffix.lstrip(".").lower()
            if extension not in allowed or extension != request.spec.output.format.value:
                issues.append(ConformanceIssue(code="format_mismatch", message=artifact.path))
    return ConformanceReport(
        subject=request.spec.render_id,
        conforms=not issues,
        checks=("render_request", "render_result", "render_output"),
        issues=tuple(issues),
    )


def check_manifest(run_dir: str | Path) -> ConformanceReport:
    try:
        verified = verify_manifest(run_dir)
    except Exception as exc:
        return ConformanceReport(
            subject=str(run_dir), conforms=False, checks=("manifest", "checksums"),
            issues=(ConformanceIssue(code="invalid_manifest", message=str(exc)),),
        )
    return ConformanceReport(
        subject=verified.manifest_path,
        conforms=True,
        checks=("manifest", "checksums"),
    )
