"""PUBLIC_SDK_INFRA: truthful display of typed Q&A outcomes."""


def qa_outcome_message(result):
    if result.mode == "grounding_validation_failed":
        return "The generated answer failed citation validation. No validated answer is available; this does not mean the catalog has no evidence."
    if result.mode == "knowledge_access_denied":
        return "Access to this project's evidence was denied. No general answer can replace authorized project evidence."
    if result.mode in {"llm_unavailable", "rag_context_available_llm_unavailable"}:
        return "The answer provider is unavailable. No answer was generated."
    if result.grounding_status == "evidence_insufficient":
        return "The available reviewed evidence does not sufficiently support an answer to this question."
    if result.grounding_status == "general_model_uncited":
        return "General model answer — not supported by a GeoWorld knowledge citation."
    return ""
