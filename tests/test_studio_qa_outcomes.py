from geoworld_open.client.models import JobResult
from geoworld_open.studio_qa import qa_outcome_message
from geoworld_open.studio_presentation import build_clean_report


def test_citation_failure_is_not_reported_as_missing_evidence():
    result = JobResult(intent="rag_qa", reason="question", answer="No validated answer.",
        mode="grounding_validation_failed", grounding_status="evidence_insufficient")
    message = qa_outcome_message(result)
    assert "failed citation validation" in message
    assert "does not mean" in message
    html = build_clean_report(prompt="Explain FWI", result=result, figures=[])
    assert "Citation validation failed" in html
    assert "Insufficient evidence for a grounded answer" not in html


def test_provider_failure_and_project_denial_have_distinct_messages():
    for mode, text in [("llm_unavailable", "provider is unavailable"), ("knowledge_access_denied", "was denied"), ("retrieval_evidence_insufficient", "does not sufficiently support")]:
        result = JobResult(intent="rag_qa", reason="question", answer="Unavailable", mode=mode, grounding_status="evidence_insufficient")
        assert text in qa_outcome_message(result)
