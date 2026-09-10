"""User-facing model attribution from existing, authenticated runtime evidence.

Health describes configuration, never who answered an earlier question. These
helpers allowlist display fields; they do not expose raw diagnostics or prompts.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

from geoworld_open.client.models import JobResult


_PROVIDERS = {"openai": "OpenAI", "bedrock": "Amazon Bedrock", "ollama": "Ollama"}


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _model_label(value: object) -> str | None:
    record = _mapping(value)
    provider, model = record.get("provider"), record.get("model")
    if not isinstance(provider, str) or provider not in _PROVIDERS:
        return None
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", model):
        return None
    # Never turn arbitrary diagnostics, HTML, account ARNs, or credential-shaped
    # values into a friendly model badge. Unrecognized metadata stays unknown.
    if model.startswith(("arn:", "sk-", "ABSK", "AKIA", "ASIA")) or "://" in model:
        return None
    return f"{_PROVIDERS[provider]} · {model}"


def configured_model_lines(health: object) -> list[str]:
    health = _mapping(health)
    details = _mapping(health.get("details"))
    # A provider-chain health response may describe the backup at the top level.
    # Only use that legacy shape when there is no explicit primary field.
    primary = details.get("primary") if "primary" in details else health
    label = _model_label(primary)
    lines = [f"Configured AI: {label}" if label else "Configured AI: model information unavailable."]
    for key, title in (("fallback", "Backup AI"), ("local_fallback", "Local backup")):
        label = _model_label(details.get(key))
        if label:
            lines.append(f"{title}: {label}")
    return lines


def execution_model_line(metadata: object, *, purpose: str) -> str:
    record = _mapping(metadata)
    label = _model_label(record)
    if not label:
        return f"{purpose}: model information not recorded."
    if record.get("success") is False:
        return f"{purpose}: {label} — attempt failed; not a completed generation."
    if record.get("success") is not True:
        return f"{purpose}: {label} — completion not recorded."
    # The reason may contain technical information. Only show that failover
    # occurred, never the raw reason or error message.
    suffix = " (backup used)" if record.get("fallback_reason") else ""
    return f"{purpose}: {label}{suffix}"


def preparation_model_line(preview: object) -> str:
    record = _mapping(preview)
    mode = record.get("interpretation_mode") or record.get("parser_mode")
    if mode == "deterministic_fallback":
        return "Model preparation: deterministic fallback; no successful LLM interpretation."
    if mode == "user_geospec_v2":
        return "Model preparation: supplied GeoSpec; no LLM interpretation."
    return execution_model_line(record.get("llm"), purpose="Model preparation")


def result_model_lines(
    result: JobResult,
    *,
    answer: object = None,
    trace: object = None,
    preparation: str | None = None,
) -> list[str]:
    if result.intent == "deepwave_reference":
        evidence = result.reference.llm if result.reference is not None else None
        line = (execution_model_line(evidence, purpose="Reference interpretation") if evidence else
                "Reference interpretation: structured selection; no LLM call." if result.interpretation_mode == "structured_input" else
                "Reference interpretation: model information not recorded.")
        return [line, "Numerical execution: pinned Deepwave forward/RTM reference, not an LLM."]
    if result.intent == "las_quicklook" or result.mode == "las_quicklook_v1":
        return ["LAS analysis: deterministic computation, not an LLM."]
    if result.intent == "csv_analysis" or result.mode == "csv_summary":
        return ["CSV analysis: deterministic computation, not an LLM."]
    model_run = result.intent in {"scenario_generation", "build_model", "model_rtm"}
    records = _mapping(trace).get("capability_uses")
    relevant = "rtm_interpretation" if result.intent == "model_rtm" else "semantic_model_parser" if model_run else "rag_qa"
    evidence = []
    if not model_run and _mapping(answer).get("llm_usage") is not None:
        evidence.append(_mapping(answer).get("llm_usage"))
    elif isinstance(records, list):
        for item in records:
            item = _mapping(item)
            if item.get("capability_name") == relevant:
                llm = _mapping(item.get("diagnostics")).get("llm")
                if llm is not None:
                    evidence.append(llm)
    purpose = "Model preparation" if model_run else "Answer generation"
    if model_run and preparation is not None:
        lines = [preparation]
    elif evidence:
        lines = list(dict.fromkeys(execution_model_line(item, purpose=purpose) for item in evidence))
    elif result.intent == "model_rtm" and result.interpretation_mode == "structured_input":
        lines = ["Experiment interpretation: structured input; no LLM call."]
    elif model_run:
        lines = [preparation_model_line({"interpretation_mode": result.interpretation_mode})]
    elif result.mode == "knowledge_access_denied":
        lines = ["Answer generation: not run; project access was denied."]
    else:
        lines = [f"{purpose}: model information not recorded."]
    if model_run:
        lines.append("Scientific model: Deepwave acoustic propagation and Born adjoint, not an LLM."
                     if result.intent == "model_rtm" else "Scientific model: deterministic computation, not an LLM.")
    return lines
