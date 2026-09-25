from __future__ import annotations

import pytest
from types import SimpleNamespace

from geoworld_open.client.models import JobResult
from geoworld_open.studio_llm import (
    configured_model_lines,
    execution_model_line,
    preparation_model_line,
    result_model_lines,
)


NOVA = {"provider": "bedrock", "model": "us.amazon.nova-2-lite-v1:0"}
OPENAI = {"provider": "openai", "model": "gpt-4.1-mini"}


def test_configured_primary_is_not_replaced_by_healths_active_backup():
    health = {**OPENAI, "reachable": True, "details": {
        "primary": {**NOVA, "reachable": False},
        "fallback": {**OPENAI, "reachable": True},
        "active_provider": "openai", "active_model": "gpt-4.1-mini",
    }}
    assert configured_model_lines(health) == [
        "Configured AI: Amazon Bedrock · us.amazon.nova-2-lite-v1:0",
        "Backup AI: OpenAI · gpt-4.1-mini",
    ]


def test_legacy_and_incomplete_health_do_not_claim_actual_usage():
    assert configured_model_lines(OPENAI) == ["Configured AI: OpenAI · gpt-4.1-mini"]
    assert configured_model_lines({**OPENAI, "details": {"primary": None}}) == [
        "Configured AI: model information unavailable.",
    ]
    assert configured_model_lines(None) == ["Configured AI: model information unavailable."]


@pytest.mark.parametrize("model", ["<script>bad</script>", "[model](https://example.test)", "x\ny", "arn:aws:bedrock:private", "sk-example-credential", "x" * 161])
def test_bad_model_metadata_is_not_rendered(model):
    assert execution_model_line({**OPENAI, "model": model, "success": True}, purpose="Answer generation") == (
        "Answer generation: model information not recorded."
    )


@pytest.mark.parametrize("record", [None, [], {"provider": []}, {"provider": "unrecognized", "model": "x"}])
def test_malformed_records_are_unknown(record):
    assert execution_model_line(record, purpose="Answer generation") == "Answer generation: model information not recorded."


@pytest.mark.parametrize("success,ending", [(True, ""), (False, " — attempt failed; not a completed generation."), (None, " — completion not recorded.")])
def test_failed_or_legacy_calls_are_not_presented_as_completed(success, ending):
    assert execution_model_line({**NOVA, "success": success}, purpose="Model preparation") == (
        "Model preparation: Amazon Bedrock · us.amazon.nova-2-lite-v1:0" + ending
    )


def test_answer_uses_recorded_backup_without_exposing_raw_diagnostics():
    result = JobResult(intent="rag_qa", reason="test", answer="Result")
    lines = result_model_lines(result, answer={"llm_usage": {
        **OPENAI, "success": True, "fallback_reason": "private diagnostic",
        "error_message": "private error", "request_id": "private reference",
    }})
    assert lines == ["Answer generation: OpenAI · gpt-4.1-mini (backup used)"]


def test_model_trace_attributes_preparation_not_scientific_computation():
    result = JobResult(intent="scenario_generation", reason="test", answer="Model")
    trace = {"capability_uses": [
        {"capability_name": "unrelated", "diagnostics": {"llm": {**OPENAI, "success": True}}},
        {"capability_name": "semantic_model_parser", "diagnostics": {"llm": {**NOVA, "success": True}}},
    ]}
    assert result_model_lines(result, trace=trace) == [
        "Model preparation: Amazon Bedrock · us.amazon.nova-2-lite-v1:0",
        "Scientific model: deterministic computation, not an LLM.",
    ]
    assert result_model_lines(result, trace=trace, preparation="Bound preview evidence") == [
        "Bound preview evidence", "Scientific model: deterministic computation, not an LLM.",
    ]


def test_qa_trace_and_absent_evidence():
    result = JobResult(intent="rag_qa", reason="test", answer="Answer")
    assert result_model_lines(result, trace={"capability_uses": [None, {
        "capability_name": "rag_qa", "diagnostics": {"llm": {**NOVA, "success": True}},
    }]}) == ["Answer generation: Amazon Bedrock · us.amazon.nova-2-lite-v1:0"]
    assert result_model_lines(result) == ["Answer generation: model information not recorded."]
    # Evidence-insufficient answers may still have used an LLM; absence of
    # attribution must not be interpreted as proof that no LLM ran.
    result.grounding_status = "evidence_insufficient"
    assert result_model_lines(result) == ["Answer generation: model information not recorded."]


@pytest.mark.parametrize("intent,mode,label", [
    ("las_quicklook", "las_quicklook_v1", "LAS analysis: deterministic computation, not an LLM."),
    ("csv_analysis", "csv_summary", "CSV analysis: deterministic computation, not an LLM."),
    ("rag_qa", "knowledge_access_denied", "Answer generation: not run; project access was denied."),
])
def test_deterministic_or_denied_paths(intent, mode, label):
    result = JobResult(intent=intent, mode=mode, reason="test", answer="Result")
    assert result_model_lines(result) == [label]


@pytest.mark.parametrize("mode,label", [
    ("deterministic_fallback", "Model preparation: deterministic fallback; no successful LLM interpretation."),
    ("user_geospec_v2", "Model preparation: supplied GeoSpec; no LLM interpretation."),
])
def test_preparation_distinguishes_deterministic_modes(mode, label):
    assert preparation_model_line({"interpretation_mode": mode}) == label


def test_configurable_fwi_separates_interpretation_computation_and_summary():
    result = JobResult.model_construct(
        intent="configurable_marmousi_fwi",
        configurable_fwi=SimpleNamespace(diagnostics={"resolved_device": "cuda"}),
    )
    assert result_model_lines(result, preparation=(
        "Request interpretation: Amazon Bedrock · us.amazon.nova-2-lite-v1:0"
    )) == [
        "Request interpretation: Amazon Bedrock · us.amazon.nova-2-lite-v1:0",
        "Scientific computation: Deepwave 0.0.26 · CUDA.",
        "Result summary: deterministic from saved run metrics; no LLM-generated numerical result.",
    ]
    assert result_model_lines(result) == [
        "Scientific computation: Deepwave 0.0.26 · CUDA.",
        "Result summary: deterministic from saved run metrics; no LLM-generated numerical result.",
    ]
