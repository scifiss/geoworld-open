"""PUBLIC_STANDARD: a non-authorizing, evidence-linked investigation proposal."""

from typing import Any, Literal

from pydantic import Field, model_validator

from .reference_experiment import ReferenceContract
from geoworld_open.world.models import Identifier


class InvestigationEvidence(ReferenceContract):
    evidence_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
    kind: Literal[
        "seismic_dataset", "well_log", "saved_scientific_result", "world_state",
        "capability", "scientific_reference", "user_report",
    ]
    status: Literal[
        "verified", "user_reported", "missing", "incompatible", "unavailable",
    ]
    summary: str = Field(min_length=1, max_length=1000)
    source_ref: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_metadata(self):
        import json

        if len(json.dumps(self.metadata, allow_nan=False)) > 8192:
            raise ValueError("Investigation evidence metadata exceeds its size limit")
        if (
            (self.status == "user_reported" and self.kind != "user_report")
            or (self.kind == "user_report" and self.status == "verified")
        ):
            raise ValueError(
                "User-reported status requires user_report evidence, which cannot be marked verified"
            )
        if self.status == "verified" and not (self.source_ref and self.source_ref.strip()):
            raise ValueError("Verified investigation evidence requires a source reference")
        if self.status == "user_reported" and not (self.source_ref and self.source_ref.strip()):
            raise ValueError("User-reported investigation evidence requires a source reference")
        return self


class InvestigationFinding(ReferenceContract):
    claim_type: Literal[
        "measured_observation", "user_reported_observation", "calculated_result",
        "supported_inference", "hypothesis", "not_established",
    ]
    statement: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)


class InvestigationStep(ReferenceContract):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    question: str = Field(min_length=1, max_length=1000)
    method: str = Field(min_length=1, max_length=300)
    rationale: str = Field(min_length=1, max_length=2000)
    required_evidence: list[str] = Field(default_factory=list, max_length=32)
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)
    expected_products: list[str] = Field(default_factory=list, max_length=20)
    readiness: Literal["ready", "conditional", "blocked", "unsupported", "unavailable"]
    capability_id: Identifier | None = Field(default=None, max_length=128)
    capability_version: Identifier | None = Field(default=None, max_length=80)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    assumptions: list[str] = Field(default_factory=list, max_length=32)
    limitations: list[str] = Field(default_factory=list, max_length=32)
    validation: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def capability_reference_is_complete(self):
        if (self.capability_id is None) != (self.capability_version is None):
            raise ValueError("Capability ID and version must be supplied together")
        return self


class ScientificInvestigationPlan(ReferenceContract):
    """Typed planning output; it is not scientific evidence or execution authority."""

    request_text: str = Field(min_length=1, max_length=8000)
    understanding: str = Field(min_length=1, max_length=2000)
    objectives: list[str] = Field(min_length=1, max_length=12)
    requested_products: list[str] = Field(default_factory=list, max_length=20)
    evidence: list[InvestigationEvidence] = Field(default_factory=list, max_length=64)
    findings: list[InvestigationFinding] = Field(default_factory=list, max_length=32)
    steps: list[InvestigationStep] = Field(min_length=1, max_length=24)
    competing_explanations: list[str] = Field(default_factory=list, max_length=32)
    uncertainties: list[str] = Field(default_factory=list, max_length=32)
    clarification_questions: list[str] = Field(default_factory=list, max_length=12)
    readiness: Literal["ready", "conditional", "blocked", "unsupported"]
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_references_and_order(self):
        evidence_ids = [item.evidence_id for item in self.evidence]
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        step_ids = [item.step_id for item in self.steps]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Investigation evidence IDs must be unique")
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Investigation step IDs must be unique")

        known_evidence = set(evidence_ids)
        prior_steps: set[str] = set()
        for step in self.steps:
            if not set(step.evidence_refs) <= known_evidence:
                raise ValueError("Investigation step references unknown evidence")
            if not set(step.depends_on) <= prior_steps:
                raise ValueError("Investigation dependencies must refer to earlier steps")
            prior_steps.add(step.step_id)
        for finding in self.findings:
            refs = set(finding.evidence_refs)
            if not refs <= known_evidence:
                raise ValueError("Investigation finding references unknown evidence")
            if finding.claim_type in {
                "measured_observation", "calculated_result", "supported_inference",
                "user_reported_observation",
            } and not refs:
                raise ValueError(
                    f"{finding.claim_type.replace('_', ' ').title()} findings require evidence references"
                )
            cited = [evidence_by_id[item] for item in finding.evidence_refs]
            if finding.claim_type == "user_reported_observation":
                if any(item.kind != "user_report" or item.status != "user_reported" for item in cited):
                    raise ValueError("User-reported observations require user-reported evidence")
            elif finding.claim_type in {
                "measured_observation", "calculated_result", "supported_inference",
            }:
                qualifying_kinds = {
                    "measured_observation": {"seismic_dataset", "well_log"},
                    "calculated_result": {"saved_scientific_result"},
                    "supported_inference": {
                        "seismic_dataset", "well_log", "saved_scientific_result", "world_state",
                    },
                }[finding.claim_type]
                if any(item.status != "verified" for item in cited):
                    raise ValueError("Established findings cannot cite unverified evidence")
                if not any(item.kind in qualifying_kinds for item in cited):
                    raise ValueError(
                        f"{finding.claim_type.replace('_', ' ').title()} findings require qualifying verified evidence"
                    )
        return self
