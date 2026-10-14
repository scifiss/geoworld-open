"""Provider-neutral development receipts above the existing scientific contracts.

These contracts authorize neither execution nor registry admission.
"""
from __future__ import annotations

from typing import Literal, Protocol
from pydantic import Field, model_validator
from geoworld_open.standard.capabilities import ContractModel, CapabilitySpec, VariableSpec
from geoworld_open.world.models import Identifier, NonEmptyStr


class CapabilityReference(ContractModel):
    capability_id: Identifier
    version: Identifier


class VerificationRequirement(ContractModel):
    check_id: Identifier
    kind: Literal['unit', 'integration', 'regression', 'negative', 'scientific', 'conformance', 'syntax', 'security']
    criterion: NonEmptyStr
    expectation_source: Literal['analytical', 'metamorphic', 'reviewed_reference', 'authored_contract']


class CapabilityDevelopmentRequest(ContractModel):
    request_id: Identifier
    operation: CapabilityReference
    description: NonEmptyStr
    required_inputs: tuple[VariableSpec, ...] = ()
    required_outputs: tuple[VariableSpec, ...] = Field(min_length=1)
    # Missing data must not trigger an unrequested source/benchmark generator.
    permitted_dependencies: tuple[CapabilityReference, ...] = ()
    scientific_constraints: tuple[NonEmptyStr, ...] = ()
    unresolved_questions: tuple[NonEmptyStr, ...] = ()
    acceptance: tuple[VerificationRequirement, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_interfaces(self):
        for values in (self.required_inputs, self.required_outputs):
            if len({value.name for value in values}) != len(values):
                raise ValueError('interface variables must have unique names')
        if len({check.check_id for check in self.acceptance}) != len(self.acceptance):
            raise ValueError('acceptance check IDs must be unique')
        return self


class CapabilityGapAssessment(ContractModel):
    request_id: Identifier
    disposition: Literal['execute_existing', 'compose_existing', 'development_required', 'clarification_required']
    reason: NonEmptyStr
    selected: tuple[CapabilityReference, ...] = ()
    missing: tuple[CapabilityReference, ...] = ()
    questions: tuple[NonEmptyStr, ...] = ()
    # A discovery receipt is not scientific applicability or execution admission.
    execution_authorized: Literal[False] = False

    @model_validator(mode='after')
    def consistent(self):
        if self.disposition in {'execute_existing', 'compose_existing'} and (not self.selected or self.missing or self.questions):
            raise ValueError('reuse requires selected capabilities without unresolved gaps')
        if self.disposition == 'development_required' and (not self.missing or self.questions):
            raise ValueError('development requires an identified missing operation, not ambiguity')
        if self.disposition == 'clarification_required' and not self.questions:
            raise ValueError('clarification requires questions')
        return self


class DevelopmentComponent(ContractModel):
    name: Identifier
    placement: Literal['public_standard', 'public_sdk', 'public_reference', 'private_implementation', 'private_intelligence']
    interface: NonEmptyStr
    purpose: NonEmptyStr


class CapabilityDevelopmentPlan(ContractModel):
    request: CapabilityDevelopmentRequest
    assessment: CapabilityGapAssessment
    reuse: tuple[CapabilityReference, ...] = ()
    components: tuple[DevelopmentComponent, ...] = Field(min_length=1)
    dependencies: tuple[NonEmptyStr, ...] = ()
    related_operations: tuple[NonEmptyStr, ...] = Field(min_length=1)
    verification: tuple[VerificationRequirement, ...] = Field(min_length=1)
    candidate_execution: Literal['disabled_pending_isolation'] = 'disabled_pending_isolation'

    @model_validator(mode='after')
    def validate_plan(self):
        if self.assessment.request_id != self.request.request_id or self.assessment.disposition != 'development_required':
            raise ValueError('only an unambiguous development gap may create a development plan')
        if self.request.unresolved_questions or self.request.operation not in self.assessment.missing:
            raise ValueError('development must resolve questions and identify the exact requested missing operation')
        kinds = {check.kind for check in self.verification}
        if not {'unit', 'integration', 'regression', 'negative', 'scientific', 'conformance'} <= kinds:
            raise ValueError('development verification must cover all six test kinds')
        by_id = {check.check_id: check for check in self.verification}
        if len(by_id) != len(self.verification) or any(by_id.get(check.check_id) != check for check in self.request.acceptance):
            raise ValueError('verification must preserve every requested acceptance criterion')
        return self


class CandidateSourceFile(ContractModel):
    path: NonEmptyStr
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def relative_source(self):
        from pathlib import PurePosixPath
        path = PurePosixPath(self.path)
        if path.is_absolute() or '..' in path.parts or '\\' in self.path:
            raise ValueError('candidate paths must be portable relative paths')
        return self


class CandidateCapabilityManifest(ContractModel):
    candidate_id: Identifier
    request_id: Identifier
    capability: CapabilitySpec
    source_files: tuple[CandidateSourceFile, ...] = Field(min_length=1)
    entrypoint: NonEmptyStr
    license: NonEmptyStr
    generator: NonEmptyStr
    execution_eligible: Literal[False] = False

    @model_validator(mode='after')
    def unique_sources(self):
        if len({value.path for value in self.source_files}) != len(self.source_files):
            raise ValueError('candidate source paths must be unique')
        return self


class VerificationEvidence(ContractModel):
    requirement: VerificationRequirement
    outcome: Literal['passed', 'failed', 'not_run']
    evidence_uri: NonEmptyStr
    evidence_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class CapabilityVerificationReport(ContractModel):
    candidate_id: Identifier
    manifest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    verifier: NonEmptyStr
    evidence: tuple[VerificationEvidence, ...] = ()
    disposition: Literal['incomplete', 'rejected', 'verified'] = 'incomplete'
    # Verification is a receipt, never an automatic production/sandbox permission.
    execution_authorized: Literal[False] = False

    @model_validator(mode='after')
    def sufficient_evidence(self):
        if len({item.requirement.check_id for item in self.evidence}) != len(self.evidence):
            raise ValueError('verification check IDs must be unique')
        if self.disposition == 'verified':
            if not self.evidence or any(item.outcome != 'passed' for item in self.evidence):
                raise ValueError('verified requires actual passing evidence')
            if not {'unit', 'integration', 'regression', 'negative', 'scientific', 'conformance'} <= {item.requirement.kind for item in self.evidence}:
                raise ValueError('imports or a single convenient test cannot verify a capability')
            if not any(item.requirement.kind == 'scientific' and item.requirement.expectation_source in {'analytical', 'metamorphic', 'reviewed_reference'} for item in self.evidence):
                raise ValueError('scientific verification needs an independent expectation')
        return self


class CapabilityGenerator(Protocol):
    def propose(self, plan: CapabilityDevelopmentPlan) -> CandidateCapabilityManifest:
        """Return source descriptions for isolated review; do not execute them."""
        ...
