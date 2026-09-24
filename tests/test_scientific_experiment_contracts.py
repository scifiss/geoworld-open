import pytest
from pydantic import ValidationError

from geoworld_open.client.scientific_experiment import (
    AcquisitionRequest,
    ConversationState,
    ConversationTurn,
    ExperimentConversationRequest,
    InversionRequest,
    ModelSelection,
    RequestedOutputs,
    ScientificExperimentDraft,
)


def test_typed_experiment_roundtrip_and_explicit_units():
    draft = ScientificExperimentDraft(
        model=ModelSelection(x_start_m=0, x_stop_m=2396, z_start_m=0, z_stop_m=996),
        acquisition=AcquisitionRequest(shots=30, receivers=100),
        inversion=InversionRequest(updates=75),
        requested_outputs=RequestedOutputs(residual=True),
        execution_intent="run",
        status="ready",
    )
    assert ScientificExperimentDraft.model_validate_json(draft.model_dump_json()) == draft
    assert draft.acquisition.shots == 30
    assert draft.inversion.updates == 75
    assert draft.requested_outputs.residual is True


@pytest.mark.parametrize(
    "value",
    [
        {"model": {"dataset": "marmousi2"}},
        {"operation": "elastic_fwi"},
        {"inversion": {"method": "lbfgs"}},
        {"acquisition": {"shots": 0}},
        {"inversion": {"updates": 251}},
        {"model": {"x_start_m": 1000, "x_stop_m": 500}},
        {"density_recovery": True},
    ],
)
def test_contract_rejects_unsupported_or_invalid_science(value):
    with pytest.raises(ValidationError):
        ScientificExperimentDraft.model_validate(value)


def test_conversation_keeps_history_context_and_active_draft_separate():
    turn = ConversationTurn(
        user_text="Make it 30 shots.",
        assistant_summary="Updated shot count to 30.",
        status="prepare_only",
        patched_fields=["acquisition.shots"],
    )
    state = ConversationState(
        conversation_id="a" * 32,
        visible_history=[turn],
        recent_planner_context=[turn],
        active_experiment=ScientificExperimentDraft(),
        status="prepare_only",
    )
    assert state.visible_history[0].user_text == "Make it 30 shots."
    assert state.active_experiment.acquisition.shots == 20
    assert ExperimentConversationRequest(prompt="Run it.").conversation_id is None


def test_ready_and_prepare_only_status_require_matching_permission():
    with pytest.raises(ValidationError):
        ScientificExperimentDraft(execution_intent="prepare", status="ready")
    with pytest.raises(ValidationError):
        ScientificExperimentDraft(execution_intent="run", status="prepare_only")
