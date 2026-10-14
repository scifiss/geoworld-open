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
from geoworld_open.standard.candidates import CandidateTextFile, CandidateLifecycleRecord, CandidateApproval


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
    with pytest.raises(ValidationError):
        CandidateApproval(candidate_id='candidate:test',package_sha256='b'*64,verification_sha256='c'*64,
            reviewer='reviewer',source_and_license_reviewed=False,scientific_scope_reviewed=True)
