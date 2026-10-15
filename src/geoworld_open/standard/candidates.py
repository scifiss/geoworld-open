"""Interoperable source packages and nonauthorizing development lifecycle records.

These are receipts, not permission to import or register candidate source.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Literal, Protocol
import json
import re

from pydantic import Field, model_validator
from geoworld_open.standard.capabilities import ContractModel
from geoworld_open.standard.development import (
    CapabilityDevelopmentPlan, CandidateCapabilityManifest, CapabilityVerificationReport,
)
from geoworld_open.world.models import NonEmptyStr

Digest = str


class LockedDependency(ContractModel):
    name: NonEmptyStr
    version: NonEmptyStr
    content_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')


class CandidateTextFile(ContractModel):
    path: NonEmptyStr
    content: str = Field(max_length=131072)

    @model_validator(mode='after')
    def safe_path(self):
        path = PurePosixPath(self.path)
        if (path.is_absolute() or '..' in path.parts or '\\' in self.path
                or str(path) != self.path or not path.name
                or path.suffix not in {'.py', '.md', '.json'}):
            raise ValueError('candidate files require canonical relative Python/document paths')
        return self


class GenerationReceipt(ContractModel):
    provider: NonEmptyStr
    mode: Literal['offline_fixture', 'provider_response']
    request_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    model: str | None = None
    # Attribution supplied by the provider is recorded, not independently proved.


class CandidateGenerationRequest(ContractModel):
    plan: CapabilityDevelopmentPlan
    allowed_dependencies: tuple[LockedDependency, ...] = Field(min_length=1)
    source_protocol: Literal['geoworld-json-variables-v1'] = 'geoworld-json-variables-v1'


class CandidateSourcePackage(ContractModel):
    manifest: CandidateCapabilityManifest
    files: tuple[CandidateTextFile, ...] = Field(min_length=3, max_length=32)
    dependencies: tuple[LockedDependency, ...] = Field(min_length=1)
    generation: GenerationReceipt
    source_protocol: Literal['geoworld-json-variables-v1'] = 'geoworld-json-variables-v1'

    @model_validator(mode='after')
    def complete_source(self):
        expected = {item.path: item.sha256 for item in self.manifest.source_files}
        actual = {item.path: sha256(item.content.encode()).hexdigest() for item in self.files}
        if len(actual) != len(self.files) or actual != expected:
            raise ValueError('source bytes must match the exact manifest, without duplicate paths')
        if sum(len(item.content.encode()) for item in self.files) > 524288:
            raise ValueError('candidate exceeds the bounded package size')
        if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*', self.manifest.entrypoint):
            raise ValueError('entrypoint must be a module:function reference')
        module, _ = self.manifest.entrypoint.split(':')
        if module.replace('.', '/') + '.py' not in actual:
            raise ValueError('entrypoint implementation is absent')
        if not any(item.path.startswith('tests/test_') and item.path.endswith('.py') for item in self.files):
            raise ValueError('candidate package must include tests')
        if not any(item.path.endswith('.md') for item in self.files):
            raise ValueError('candidate package must document its validity and interfaces')
        if len({item.name for item in self.dependencies}) != len(self.dependencies):
            raise ValueError('dependency locks must be unique')
        return self


class CodingAgent(Protocol):
    def generate(self, request: CandidateGenerationRequest) -> CandidateSourcePackage:
        """Propose source; no scientific execution, installation or activation."""
        ...


class NumericalSourceResponse(ContractModel):
    """Model supplies numerical Python only; the host owns package transport."""
    source: str = Field(min_length=1, max_length=65536)


class DevelopmentBudget(ContractModel):
    max_attempts: int = Field(default=3, ge=1, le=3)
    total_tokens: int = Field(default=8192, ge=1, le=32768)
    output_tokens_per_attempt: int = Field(default=1600, ge=1, le=4096)


class DevelopmentDiagnosis(ContractModel):
    category: Literal['syntax', 'interface', 'unit_test', 'numerical', 'security',
                      'resource', 'provider', 'budget', 'environment']
    message: str = Field(min_length=1, max_length=512)
    check_id: str | None = None


class DevelopmentAttemptReceipt(ContractModel):
    attempt: int = Field(ge=1, le=3)
    candidate_id: NonEmptyStr
    request_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    predecessor_sha256: Digest | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    evidence_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    package_sha256: Digest | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    state: Literal['proposed', 'generated', 'tested', 'verified']
    diagnoses: tuple[DevelopmentDiagnosis, ...] = ()
    prompt_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    # An attempt receipt never authorizes activation.
    execution_authorized: Literal[False] = False

    @model_validator(mode='after')
    def consistent_attempt(self):
        if (self.attempt == 1) != (self.predecessor_sha256 is None):
            raise ValueError('Repair attempts require an exact predecessor receipt hash')
        if self.state != 'proposed' and self.package_sha256 is None:
            raise ValueError('Generated/tested attempts require a source package hash')
        if self.state == 'verified' and self.diagnoses:
            raise ValueError('A verified attempt cannot have unresolved failures')
        return self


class VerificationEnvironment(ContractModel):
    runner: NonEmptyStr
    policy_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    runtime: LockedDependency
    toolchain: tuple[LockedDependency, ...] = ()
    kernel: NonEmptyStr
    isolation: tuple[NonEmptyStr, ...]
    limits: dict[str, int]


class CandidateVerificationBundle(ContractModel):
    package_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    plan_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    report: CapabilityVerificationReport
    details_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    environment: VerificationEnvironment | None = None
    failure_reasons: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode='after')
    def verified_environment(self):
        if self.report.disposition == 'verified' and (self.environment is None or self.failure_reasons):
            raise ValueError('verified requires a recorded isolation environment and no failures')
        return self


class CandidateLifecycleRecord(ContractModel):
    candidate_id: NonEmptyStr
    revision: int = Field(ge=1)
    state: Literal['proposed', 'generated', 'tested', 'verified', 'approved', 'active']
    request_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    package_sha256: Digest | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    previous_sha256: Digest | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    evidence_sha256: Digest | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    reason: NonEmptyStr
    activation_scope: Literal['disabled', 'offline_review'] = 'disabled'
    execution_authorized: Literal[False] = False

    @model_validator(mode='after')
    def bounded_state(self):
        if self.revision == 1 and self.state != 'proposed':
            raise ValueError('candidate lifecycle must begin at revision 1 in proposed state')
        if self.revision == 1 and (self.package_sha256 is not None or self.evidence_sha256 is not None):
            raise ValueError('initial proposed lifecycle record cannot claim generated package or verification evidence')
        if self.state != 'proposed' and not self.package_sha256:
            raise ValueError('post-generation state requires exact source package identity')
        if (self.revision == 1) != (self.previous_sha256 is None):
            raise ValueError('lifecycle requires a predecessor hash after the first record')
        if self.state in {'tested', 'verified', 'approved', 'active'} and not self.evidence_sha256:
            raise ValueError('tested/reviewed states require recorded evidence')
        if self.state == 'active' and self.activation_scope != 'offline_review':
            raise ValueError('this gate cannot activate production candidates')
        return self


LEGACY_CANDIDATE_LIFECYCLE_FIELDS = frozenset({
    'candidate_id', 'revision', 'state', 'request_sha256', 'package_sha256',
    'previous_sha256', 'evidence_sha256', 'reason', 'activation_scope',
})


def candidate_lifecycle_record_sha256(
    record: CandidateLifecycleRecord | Mapping[str, object],
    *,
    schema: Literal['current', 'legacy'] | None = None,
) -> str:
    """Hash a current or explicitly supported historical lifecycle receipt."""
    current_fields = frozenset(CandidateLifecycleRecord.model_fields)
    legacy_fields = LEGACY_CANDIDATE_LIFECYCLE_FIELDS
    if schema not in (None, 'current', 'legacy'):
        raise ValueError('unknown lifecycle receipt schema')
    if isinstance(record, Mapping):
        payload = dict(record)
        fields = frozenset(payload)
        if schema is None:
            schema = 'current' if fields == current_fields else 'legacy' if fields == legacy_fields else None
        expected_fields = current_fields if schema == 'current' else legacy_fields
        if schema is None or fields != expected_fields:
            raise ValueError('lifecycle receipt must match the current or documented legacy schema')
        if schema == 'current' and payload['execution_authorized'] is not False:
            raise ValueError('lifecycle receipts cannot authorize execution')
    else:
        if record.execution_authorized is not False:
            raise ValueError('lifecycle receipts cannot authorize execution')
        schema = schema or 'current'
        payload = record.model_dump(mode='json')
        if schema == 'legacy':
            payload.pop('execution_authorized')
            if frozenset(payload) != legacy_fields:
                raise ValueError('current lifecycle record cannot be represented by the documented legacy schema')
    payload=json.dumps(
        payload,
        sort_keys=True,
        separators=(',',':'),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    return sha256(payload).hexdigest()


class CandidateLifecycleChain(ContractModel):
    """Validate lifecycle order and linkage; never an admission authorization."""

    records: tuple[CandidateLifecycleRecord, ...] = Field(min_length=1)
    execution_authorized: Literal[False] = False

    @model_validator(mode='after')
    def append_only_progression(self):
        if any(record.execution_authorized is not False for record in self.records):
            raise ValueError('lifecycle receipts cannot authorize execution')
        first=self.records[0]
        if first.revision!=1 or first.state!='proposed' or first.previous_sha256 is not None:
            raise ValueError('candidate lifecycle chain must begin with revision 1 proposed')
        allowed={
            'proposed':{'generated'},
            'generated':{'tested'},
            'tested':{'tested','verified'},
            'verified':{'approved'},
            'approved':{'active'},
            'active':set(),
        }
        for index,(previous,current) in enumerate(zip(self.records,self.records[1:]),start=2):
            if (
                current.candidate_id!=first.candidate_id
                or current.revision!=index
                or current.request_sha256!=first.request_sha256
            ):
                raise ValueError('lifecycle records must retain candidate, request, and contiguous revisions')
            valid_hashes = {
                candidate_lifecycle_record_sha256(previous),
                candidate_lifecycle_record_sha256(previous, schema='legacy'),
            }
            if current.previous_sha256 not in valid_hashes:
                raise ValueError('lifecycle predecessor hash does not match the previous immutable receipt')
            if current.state not in allowed[previous.state]:
                raise ValueError(
                    f'invalid candidate lifecycle transition: {previous.state} -> {current.state}'
                )
            if previous.package_sha256 is not None and current.package_sha256!=previous.package_sha256:
                raise ValueError('lifecycle package identity cannot change after generation')
        return self


class CandidateApproval(ContractModel):
    candidate_id: NonEmptyStr
    package_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    verification_sha256: Digest = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: NonEmptyStr
    source_and_license_reviewed: Literal[True]
    scientific_scope_reviewed: Literal[True]
    scope: Literal['offline_review'] = 'offline_review'


class CapabilityDevelopmentPreview(ContractModel):
    request_text: NonEmptyStr
    plan: CapabilityDevelopmentPlan | None = None
    disposition: Literal['execute_existing', 'compose_existing', 'development_required', 'clarification_required']
    message: NonEmptyStr
    production_execution_allowed: Literal[False] = False
