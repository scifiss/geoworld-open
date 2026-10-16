"""PUBLIC_STANDARD: a non-authorizing, evidence-linked investigation proposal."""

from typing import Any, Literal

from pydantic import Field, model_validator

from .reference_experiment import ReferenceContract


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
    capability_id: str | None = Field(default=None, max_length=128)
    capability_version: str | None = Field(default=None, max_length=80)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    assumptions: list[str] = Field(default_factory=list, max_length=32)
    limitations: list[str] = Field(default_factory=list, max_length=32)
    validation: list[str] = Field(default_factory=list, max_length=32)


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
        if any(not set(finding.evidence_refs) <= known_evidence for finding in self.findings):
            raise ValueError("Investigation finding references unknown evidence")
        return self
