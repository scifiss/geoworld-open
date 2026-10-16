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
from geoworld_open.client.scientific_workflow import ScientificGoalAction, ScientificWorkflowPreview


def make_plan(*, evidence=None, findings=None, readiness="conditional"):
    evidence = evidence or [InvestigationEvidence(
        evidence_id="dataset:baseline",
        kind="seismic_dataset",
        status="verified",
        summary="Owner-scoped validated SEG-Y survey metadata.",
        source_ref="d" * 24,
        metadata={"shape": [100, 200], "sample_unit": "s"},
    )]
    first = InvestigationStep(
        step_id="comparability",
        question="Are the surveys comparable?",
        method="Acquisition and processing QC",
        rationale="Differences can reflect acquisition or processing changes.",
        evidence_refs=[evidence[0].evidence_id],
        expected_products=["QC decision"],
        readiness="conditional",
        required_evidence=["Monitor survey and processing history"],
        validation=["Check coordinate and sample support"],
        assumptions=["Amplitude normalization is declared"],
    )
    second = InvestigationStep(
        step_id="difference",
        question="Is a repeatable time-lapse amplitude change present?",
        method="Matched-support difference",
        rationale="Only compare surveys after comparability checks.",
        evidence_refs=[evidence[0].evidence_id],
        expected_products=["Difference attributes"],
        readiness="unavailable",
        depends_on=[first.step_id],
        limitations=["No field difference was computed."],
        assumptions=["Surveys share acquisition geometry"],
    )
    return ScientificInvestigationPlan(
        request_text="Compare surveys and investigate amplitude changes.",
        understanding="Assess whether observed differences have a supported cause.",
        objectives=["Assess repeatability", "Evaluate possible fluid-related change"],
        requested_products=["Normalized difference", "Uncertainty assessment"],
        evidence=evidence,
        findings=findings if findings is not None else [InvestigationFinding(
            claim_type="not_established",
            statement="No difference was computed.",
            evidence_refs=[evidence[0].evidence_id],
        )],
        steps=[first, second],
        competing_explanations=["Acquisition and processing variation"],
        uncertainties=["No paired monitor survey was supplied."],
        readiness=readiness,
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


def test_plan_rejects_duplicate_evidence_ids():
    duplicate = InvestigationEvidence(
        evidence_id="dataset:baseline",
        kind="seismic_dataset",
        status="verified",
        summary="Duplicate source identity.",
        source_ref="e" * 24,
    )
    with pytest.raises(ValidationError, match="IDs must be unique"):
        make_plan(evidence=[make_plan().evidence[0], duplicate])


def test_verified_evidence_requires_a_source_reference():
    for source_ref in (None, "", "  "):
        with pytest.raises(ValidationError, match="source reference"):
            InvestigationEvidence(
                evidence_id="evidence:verified",
                kind="seismic_dataset",
                status="verified",
                summary="Validated source metadata.",
                source_ref=source_ref,
            )


@pytest.mark.parametrize(
    "claim_type",
    ["measured_observation", "calculated_result", "supported_inference", "user_reported_observation"],
)
def test_established_and_user_reported_findings_require_explicit_evidence(claim_type):
    finding = InvestigationFinding(claim_type=claim_type, statement="Claim without a source.")
    with pytest.raises(ValidationError, match="require evidence references"):
        make_plan(findings=[finding])


@pytest.mark.parametrize(
    "claim_type,evidence_kind,status",
    [
        ("measured_observation", "seismic_dataset", "missing"),
        ("measured_observation", "well_log", "unavailable"),
        ("measured_observation", "seismic_dataset", "incompatible"),
        ("calculated_result", "saved_scientific_result", "missing"),
        ("calculated_result", "seismic_dataset", "verified"),
        ("supported_inference", "capability", "verified"),
        ("supported_inference", "scientific_reference", "verified"),
        ("supported_inference", "world_state", "unavailable"),
    ],
)
def test_established_findings_reject_inadmissible_evidence(claim_type, evidence_kind, status):
    evidence = InvestigationEvidence(
        evidence_id="evidence:test",
        kind=evidence_kind,
        status=status,
        summary="Evidence that is not admissible for this finding.",
        source_ref="source:test",
    )
    finding = InvestigationFinding(
        claim_type=claim_type,
        statement="This must not be presented as an established result.",
        evidence_refs=[evidence.evidence_id],
    )
    with pytest.raises(ValidationError, match="require verified|require verified measurement|require verified saved"):
        make_plan(evidence=[evidence], findings=[finding])


def test_user_reports_and_verified_calculations_are_distinguished():
    reported = InvestigationEvidence(
        evidence_id="report:request",
        kind="user_report",
        status="user_reported",
        summary="A user-reported amplitude change, not independently measured.",
        source_ref="submitted_request",
    )
    calculated = InvestigationEvidence(
        evidence_id="result:saved",
        kind="saved_scientific_result",
        status="verified",
        summary="Owner-scoped saved result passed evidence verification.",
        source_ref="b" * 32,
    )
    plan = make_plan(
        evidence=[reported, calculated],
        findings=[
            InvestigationFinding(
                claim_type="user_reported_observation",
                statement="The user reported an amplitude change.",
                evidence_refs=[reported.evidence_id],
            ),
            InvestigationFinding(
                claim_type="calculated_result",
                statement="The verified saved computation produced a conditional response.",
                evidence_refs=[calculated.evidence_id],
            ),
        ],
    )
    assert [item.claim_type for item in plan.findings] == [
        "user_reported_observation",
        "calculated_result",
    ]

    mixed = plan.model_dump()
    mixed["findings"][0]["evidence_refs"] = [calculated.evidence_id]
    with pytest.raises(ValidationError, match="User-reported observations require"):
        ScientificInvestigationPlan.model_validate(mixed)

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

        def warning(self, value):
            rendered.append(value)

        def error(self, value):
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
    assert "Plan readiness" in rendered
    assert any("Assumptions: Surveys share acquisition geometry" in str(item) for item in rendered)
    assert any("Limitations: No field difference was computed." in str(item) for item in rendered)


@pytest.mark.parametrize("readiness", ["blocked", "unsupported"])
def test_renderer_emphasizes_non_executable_overall_readiness(monkeypatch, readiness):
    rendered = []

    class Display:
        session_state = {"studio_request_prompt": "Plan an investigation.", "studio_decision": None}

        def __getattr__(self, name):
            if name in {"subheader", "write", "markdown", "caption", "warning", "error"}:
                return lambda value: rendered.append((name, value))
            if name == "expander":
                return lambda *_args, **_kwargs: nullcontext()
            raise AssertionError(f"Unexpected renderer API: {name}")

    plan = ScientificInvestigationPlan.model_validate({
        **make_plan().model_dump(),
        "readiness": readiness,
    })
    Display.session_state["studio_decision"] = StudioDecision(
        interpretation=StudioIntent(operation="scientific"),
        route="ask_question",
        message="Plan only.",
        investigation_plan=plan,
    )
    monkeypatch.setattr(studio_request, "st", Display())

    studio_request.render_request(
        api=None,
        submit=lambda *_a, **_k: pytest.fail("No job may be submitted"),
        render_las=lambda *_a: pytest.fail("No execution renderer may run"),
    )

    assert ("subheader", "Plan readiness") in rendered
    assert ("write", readiness.title()) in rendered
    assert any(
        name == "warning" and "cannot currently be executed" in value
        for name, value in rendered
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"route": "build_model"},
        {"route": "scientific_workflow"},
        {"action": "scientific_goal"},
        {"build_spec": {"model": "untrusted"}},
        {"command": "run"},
        {
            "scientific": ScientificWorkflowPreview(
                goal=ScientificGoalAction(objective="baseline_avo"),
                message="Executable preview",
                execution_allowed=True,
            )
        },
    ],
)
def test_investigation_decisions_reject_executable_combinations(changes):
    decision = {
        "interpretation": {"operation": "scientific"},
        "route": "ask_question",
        "message": "Planning only.",
        "investigation_plan": make_plan().model_dump(),
        **changes,
    }
    with pytest.raises(ValidationError, match="non-executing ask_question"):
        StudioDecision.model_validate(decision)


def test_investigation_plan_cannot_accompany_auto_executable_scientific_preview():
    with pytest.raises(ValidationError, match="non-executing ask_question"):
        StudioDecision.model_validate({
            "interpretation": {"operation": "scientific"},
            "route": "scientific_workflow",
            "message": "Plan and execute.",
            "investigation_plan": make_plan().model_dump(),
            "scientific": ScientificWorkflowPreview(
                goal=ScientificGoalAction(objective="baseline_avo"),
                message="Automatically executable preview",
                execution_allowed=True,
                automatic_execution=True,
            ),
        })


def test_renderer_revalidates_mutated_decision_before_any_execution_path(monkeypatch):
    rendered = []

    class Display:
        session_state = {"studio_request_prompt": "Plan an investigation.", "studio_decision": None}

        def error(self, value):
            rendered.append(value)

    valid = StudioDecision(
        interpretation=StudioIntent(operation="scientific"),
        route="ask_question",
        message="Planning only.",
        investigation_plan=make_plan(),
    )
    Display.session_state["studio_decision"] = valid.model_copy(update={"route": "scientific_workflow"})
    monkeypatch.setattr(studio_request, "st", Display())

    studio_request.render_request(
        api=None,
        submit=lambda *_a, **_k: pytest.fail("An invalid decision must not submit"),
        render_las=lambda *_a: pytest.fail("An invalid decision must not render execution"),
    )

    assert rendered and "invalid" in rendered[0].lower()


def test_renderer_reports_unvalidated_non_decision_object(monkeypatch):
    rendered = []

    class Display:
        session_state = {"studio_request_prompt": "Plan an investigation.", "studio_decision": {}}

        def error(self, value):
            rendered.append(value)

    monkeypatch.setattr(studio_request, "st", Display())
    studio_request.render_request(
        api=None,
        submit=lambda *_a, **_k: pytest.fail("An unvalidated object must not submit"),
        render_las=lambda *_a: pytest.fail("An unvalidated object must not render execution"),
    )
    assert rendered and "invalid" in rendered[0].lower()
