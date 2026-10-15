"""Offline transport/lifecycle checks; no private source or code execution."""
import pytest


def test_source_only_response_and_bounded_repair_receipts():
    from geoworld_open.standard.candidates import NumericalSourceResponse, DevelopmentBudget, DevelopmentAttemptReceipt
    from pydantic import ValidationError
    assert NumericalSourceResponse(source='def compute(x): return {}').source.startswith('def')
    with pytest.raises(ValidationError):
        NumericalSourceResponse(source='x', files=[])
    with pytest.raises(ValidationError):
        DevelopmentBudget(max_attempts=4)
    with pytest.raises(ValidationError, match='predecessor'):
        DevelopmentAttemptReceipt(attempt=2,candidate_id='test',request_sha256='a'*64,
            evidence_sha256='b'*64,state='proposed')
from pydantic import ValidationError
from geoworld_open.standard.candidates import (
    CandidateApproval,
    CandidateLifecycleChain,
    CandidateLifecycleRecord,
    CandidateTextFile,
    candidate_lifecycle_record_sha256,
)


@pytest.mark.parametrize('path', ['../bad.py', '/tmp/bad.py', './bad.py', 'a//bad.py', 'a\\bad.py', '.', 'native.so'])
def test_source_transport_rejects_unsafe_or_noncanonical_paths(path):
    with pytest.raises(ValidationError):
        CandidateTextFile(path=path, content='pass')


def test_lifecycle_records_are_nonauthorizing_and_require_identity_evidence():
    proposed = CandidateLifecycleRecord(candidate_id='candidate:test', revision=1, state='proposed', request_sha256='a'*64, reason='Proposal only')
    assert proposed.activation_scope == 'disabled'
    with pytest.raises(ValidationError):
        CandidateLifecycleRecord(candidate_id='candidate:test', revision=2, state='generated', request_sha256='a'*64, reason='missing hashes')
    with pytest.raises(ValidationError):
        CandidateLifecycleRecord(candidate_id='candidate:test', revision=2, state='active', request_sha256='a'*64,
            package_sha256='b'*64, previous_sha256='c'*64, evidence_sha256='d'*64, reason='cannot activate production')
    for state in ('approved','active'):
        with pytest.raises(ValidationError,match='begin at revision 1'):
            CandidateLifecycleRecord(
                candidate_id='candidate:test',
                revision=1,
                state=state,
                request_sha256='a'*64,
                package_sha256='b'*64,
                previous_sha256=None,
                evidence_sha256='c'*64,
                reason='Forged initial lifecycle state',
                activation_scope='offline_review',
            )
    with pytest.raises(ValidationError):
        CandidateApproval(candidate_id='candidate:test',package_sha256='b'*64,verification_sha256='c'*64,
            reviewer='reviewer',source_and_license_reviewed=False,scientific_scope_reviewed=True)


def test_gate_2b_lifecycle_chain_requires_proposed_start_and_verified_progression():
    records=[]

    def append(state,*,package=None,evidence=None,activation_scope='disabled'):
        values=dict(
            candidate_id='candidate:gate2b-spatial',
            revision=len(records)+1,
            state=state,
            request_sha256='a'*64,
            package_sha256=package,
            previous_sha256=candidate_lifecycle_record_sha256(records[-1]) if records else None,
            evidence_sha256=evidence,
            reason=f'Gate 2B reviewed lifecycle state: {state}',
            activation_scope=activation_scope,
        )
        records.append(CandidateLifecycleRecord(**values))

    append('proposed')
    append('generated',package='b'*64)
    append('tested',package='b'*64,evidence='c'*64)
    append('verified',package='b'*64,evidence='d'*64)
    append('approved',package='b'*64,evidence='e'*64)
    append('active',package='b'*64,evidence='f'*64,activation_scope='offline_review')

    chain=CandidateLifecycleChain(records=tuple(records))
    assert chain.execution_authorized is False
    assert all(record.execution_authorized is False for record in chain.records)
    assert tuple(item.state for item in chain.records)==(
        'proposed','generated','tested','verified','approved','active'
    )


@pytest.mark.parametrize(
    'states',
    [
        ('proposed','verified'),
        ('proposed','generated','approved'),
        ('proposed','generated','tested','verified','active'),
    ],
)
def test_lifecycle_chain_rejects_hash_linked_but_invalid_transitions(states):
    records=[]
    for index,state in enumerate(states, start=1):
        package=None if state=='proposed' else 'b'*64
        evidence='c'*64 if state in {'tested','verified','approved','active'} else None
        records.append(
            CandidateLifecycleRecord(
                candidate_id='candidate:forged',
                revision=index,
                state=state,
                request_sha256='a'*64,
                package_sha256=package,
                previous_sha256=candidate_lifecycle_record_sha256(records[-1]) if records else None,
                evidence_sha256=evidence,
                reason='Hash-linked but invalid lifecycle transition',
                activation_scope='offline_review' if state=='active' else 'disabled',
            )
        )
    with pytest.raises(ValidationError,match='invalid candidate lifecycle transition'):
        CandidateLifecycleChain(records=tuple(records))


def test_lifecycle_chain_rejects_forged_predecessor_and_is_non_authorizing():
    proposed=CandidateLifecycleRecord(
        candidate_id='candidate:tampered',
        revision=1,
        state='proposed',
        request_sha256='a'*64,
        reason='Proposal',
    )
    generated=CandidateLifecycleRecord(
        candidate_id='candidate:tampered',
        revision=2,
        state='generated',
        request_sha256='a'*64,
        package_sha256='b'*64,
        previous_sha256='f'*64,
        reason='Forged predecessor digest',
    )
    with pytest.raises(ValidationError,match='predecessor hash'):
        CandidateLifecycleChain(records=(proposed,generated))


def test_lifecycle_chain_preserves_historical_receipt_hashes_and_current_hashes():
    import json
    from hashlib import sha256

    legacy_proposed = {
        'candidate_id': 'candidate:legacy',
        'revision': 1,
        'state': 'proposed',
        'request_sha256': 'a'*64,
        'package_sha256': None,
        'previous_sha256': None,
        'evidence_sha256': None,
        'reason': 'Historical proposal',
        'activation_scope': 'disabled',
    }
    legacy_hash = sha256(json.dumps(
        legacy_proposed, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False,
    ).encode()).hexdigest()
    legacy_generated = {
        'candidate_id': 'candidate:legacy',
        'revision': 2,
        'state': 'generated',
        'request_sha256': 'a'*64,
        'package_sha256': 'b'*64,
        'previous_sha256': legacy_hash,
        'evidence_sha256': None,
        'reason': 'Historical generation',
        'activation_scope': 'disabled',
    }
    proposed = CandidateLifecycleRecord.model_validate(legacy_proposed)
    generated = CandidateLifecycleRecord.model_validate(legacy_generated)
    assert candidate_lifecycle_record_sha256(legacy_proposed) == legacy_hash
    assert candidate_lifecycle_record_sha256(proposed, recorded_fields=True) == legacy_hash
    assert CandidateLifecycleChain(records=(proposed, generated)).execution_authorized is False

    current_proposed = CandidateLifecycleRecord(
        candidate_id='candidate:current',
        revision=1,
        state='proposed',
        request_sha256='c'*64,
        reason='Current proposal',
    )
    current_hash = candidate_lifecycle_record_sha256(current_proposed)
    current_generated = CandidateLifecycleRecord(
        candidate_id='candidate:current',
        revision=2,
        state='generated',
        request_sha256='c'*64,
        package_sha256='d'*64,
        previous_sha256=current_hash,
        reason='Current generation',
    )
    serialized = tuple(
        CandidateLifecycleRecord.model_validate_json(record.model_dump_json())
        for record in (current_proposed, current_generated)
    )
    assert CandidateLifecycleChain(records=serialized).execution_authorized is False
    assert serialized[1].previous_sha256 == candidate_lifecycle_record_sha256(serialized[0])
