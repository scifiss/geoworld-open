import pytest
from contextlib import nullcontext
from pydantic import ValidationError

from geoworld_open import studio_request
from geoworld_open.client.scientific_investigation import (
    InvestigationEvidence,
    InvestigationFinding,
    InvestigationStep,
    ScientificInvestigationPlan,
)
from geoworld_open.client.studio_request import EvidenceAssessmentReceipt, StudioDecision, StudioIntent


def make_plan():
    evidence = InvestigationEvidence(
        evidence_id="dataset:baseline",
        kind="seismic_dataset",
        status="verified",
        summary="Owner-scoped validated SEG-Y survey metadata.",
        source_ref="d" * 24,
        metadata={"shape": [100, 200], "sample_unit": "s"},
    )
    first = InvestigationStep(
        step_id="comparability",
        question="Are the surveys comparable?",
        method="Acquisition and processing QC",
        rationale="Differences can reflect acquisition or processing changes.",
        evidence_refs=[evidence.evidence_id],
        expected_products=["QC decision"],
        readiness="conditional",
        required_evidence=["Monitor survey and processing history"],
        validation=["Check coordinate and sample support"],
    )
    second = InvestigationStep(
        step_id="difference",
        question="Is a repeatable time-lapse amplitude change present?",
        method="Matched-support difference",
        rationale="Only compare surveys after comparability checks.",
        evidence_refs=[evidence.evidence_id],
        expected_products=["Difference attributes"],
        readiness="unavailable",
        depends_on=[first.step_id],
        limitations=["No field difference was computed."],
    )
    return ScientificInvestigationPlan(
        request_text="Compare surveys and investigate amplitude changes.",
        understanding="Assess whether observed differences have a supported cause.",
        objectives=["Assess repeatability", "Evaluate possible fluid-related change"],
        requested_products=["Normalized difference", "Uncertainty assessment"],
        evidence=[evidence],
        findings=[InvestigationFinding(
            claim_type="not_established",
            statement="No difference was computed.",
            evidence_refs=[evidence.evidence_id],
        )],
        steps=[first, second],
        competing_explanations=["Acquisition and processing variation"],
        uncertainties=["No paired monitor survey was supplied."],
        readiness="conditional",
    )


def test_plan_round_trip_and_studio_response_preserve_machine_readable_proposal():
    plan = make_plan()
    response = StudioDecision(
        interpretation=StudioIntent(operation="scientific"),
        route="ask_question",
        message="A conditional investigation plan is ready.",
        investigation_plan=plan,
    )

    restored = StudioDecision.model_validate_json(response.model_dump_json())
    assert restored.investigation_plan == plan
    assert restored.investigation_plan.execution_authorized is False
    assert restored.investigation_plan.requested_products == ["Normalized difference", "Uncertainty assessment"]
    assert restored.investigation_plan.steps[1].depends_on == ["comparability"]


@pytest.mark.parametrize("changes", [
    {"execution_authorized": True},
    {"evidence": []},
    {"steps": [make_plan().steps[1]]},
])
def test_plan_rejects_authority_or_broken_evidence_and_dependency_links(changes):
    payload = make_plan().model_dump()
    payload.update(changes)
    with pytest.raises(ValidationError):
        ScientificInvestigationPlan.model_validate(payload)


def test_plan_rejects_forward_dependency_and_unreferenced_evidence():
    plan = make_plan().model_dump()
    plan["steps"][0]["depends_on"] = ["difference"]
    with pytest.raises(ValidationError, match="earlier steps"):
        ScientificInvestigationPlan.model_validate(plan)

    plan = make_plan().model_dump()
    plan["findings"][0]["evidence_refs"] = ["unknown"]
    with pytest.raises(ValidationError, match="unknown evidence"):
        ScientificInvestigationPlan.model_validate(plan)


def test_saved_assessment_investigation_plan_renders_without_submitting_a_job(monkeypatch):
    rendered = []

    class Display:
        session_state = {
            "studio_request_prompt": "Why did the saved response change?",
            "studio_decision": None,
        }

        def subheader(self, value):
            rendered.append(value)

        def write(self, value):
            rendered.append(value)

        def markdown(self, value):
            rendered.append(value)

        def caption(self, value):
            rendered.append(value)

        def expander(self, *_args, **_kwargs):
            return nullcontext()

    plan = make_plan()
    decision = StudioDecision(
        interpretation=StudioIntent(operation="question"),
        route="ask_question",
        message="A saved-result interpretation.",
        evidence_assessment=EvidenceAssessmentReceipt(
            record_id="a" * 64,
            source_job_id="b" * 32,
            objective="fluid_pp_causality",
            answer="A saved-result interpretation.",
            conclusion="Field attribution is not established.",
            evidence_count=4,
            gaps=["No field calibration"],
        ),
        investigation_plan=plan,
    )
    Display.session_state["studio_decision"] = decision
    monkeypatch.setattr(studio_request, "st", Display())

    studio_request.render_request(
        api=None,
        submit=lambda *_args, **_kwargs: pytest.fail("Rendering a plan must not submit a job"),
        render_las=lambda *_args: pytest.fail("Investigation plans do not open LAS execution"),
    )

    assert "Requested products" in rendered
    assert any("Normalized difference" in str(item) for item in rendered)
    assert "Recommended investigation" in rendered
    assert any("Planning only" in str(item) for item in rendered)
