"""Bounded offline discovery and strict candidate-evidence contracts."""
from dataclasses import replace
import pytest
import xarray as xr
from pydantic import ValidationError
from geoworld_open.standard.capabilities import CapabilityContext, CapabilityRunResult, CapabilitySpec, CapabilityKind, VariableSpec, DTypeKind, ValidityDomain
from geoworld_open.standard.development import (
    CapabilityDevelopmentRequest, CapabilityReference, VerificationRequirement,
    CapabilityDevelopmentPlan, DevelopmentComponent, CandidateSourceFile,
    CandidateCapabilityManifest, CapabilityVerificationReport, VerificationEvidence,
)
from geoworld_open.sdk import CapabilityRegistry
from geoworld_open.sdk.development import assess_capability_gap, CapabilityAdapter
from geoworld_open.reference.physics import AcousticImpedanceReference
from geoworld_open.engine import compile_plan, ExecutionContext, SeedManager


CHECK=VerificationRequirement(check_id='equation',kind='scientific',criterion='Z equals Vp times density for independently chosen constant fields.',expectation_source='analytical')


def request(plugin=None, **changes):
    spec=(plugin or AcousticImpedanceReference()).spec
    values=dict(request_id='request:test',operation=CapabilityReference(capability_id=spec.capability_id,version=spec.version),
        description='Compute the requested quantity without changing its scientific meaning.',required_inputs=spec.inputs,
        required_outputs=spec.outputs,acceptance=(CHECK,))
    values.update(changes)
    return CapabilityDevelopmentRequest(**values)


class DensitySource:
    spec=CapabilitySpec(capability_id='reference.authored_density',version='1.0',kind=CapabilityKind.TRANSFORM,title='Already validated authored density',
        outputs=(AcousticImpedanceReference.spec.inputs[1],),
        validity_domain=ValidityDomain(description='Explicit constant test fixture, not geological inference.'))

    def execute(self,dataset,context):
        return CapabilityRunResult(xr.Dataset({'density_kg_m3':(('z','x'),[[2200.]],{'units':'kg/m^3'})}))


class OptionalOutputSource:
    required_output=VariableSpec(name='required_value',unit='1',dimensions=('z','x'),dtype_kind=DTypeKind.FLOAT)
    optional_output=VariableSpec(name='optional_value',unit='1',dimensions=('z','x'),
                                 dtype_kind=DTypeKind.FLOAT,required=False)
    spec=CapabilitySpec(
        capability_id='reference.optional_output_source',
        version='1.0',
        kind=CapabilityKind.TRANSFORM,
        title='Capability with an optional result',
        outputs=(required_output,optional_output),
        validity_domain=ValidityDomain(description='Explicit adapter contract test.'),
    )

    def __init__(self,include_optional):
        self.include_optional=include_optional

    def execute(self,dataset,context):
        outputs={
            'required_value':(('z','x'),[[1.]],{'units':'1'}),
        }
        if self.include_optional:
            outputs['optional_value']=(('z','x'),[[2.]],{'units':'1'})
        return CapabilityRunResult(xr.Dataset(outputs))


class OptionalOutputConsumer:
    spec=CapabilitySpec(
        capability_id='reference.optional_output_consumer',
        version='1.0',
        kind=CapabilityKind.TRANSFORM,
        title='Consumer requiring an optional upstream result',
        inputs=(VariableSpec(name='optional_value',unit='1',dimensions=('z','x'),
                             dtype_kind=DTypeKind.FLOAT),),
        outputs=(VariableSpec(name='consumed',unit='1',dimensions=('z','x'),
                              dtype_kind=DTypeKind.FLOAT),),
        validity_domain=ValidityDomain(description='Explicit dependency-planning test.'),
    )

    def execute(self,dataset,context):
        return CapabilityRunResult(xr.Dataset({'consumed':dataset['optional_value']}))


def test_existing_exact_contract_reuse_and_missing_operation_no_substitution():
    registry=CapabilityRegistry();registry.register(AcousticImpedanceReference())
    accepted=assess_capability_gap(request(),registry)
    assert accepted.disposition=='execute_existing' and not accepted.execution_authorized
    missing=assess_capability_gap(request(operation=CapabilityReference(capability_id='pressure_diffusion',version='1.0')),registry)
    assert missing.disposition=='development_required' and missing.selected==()
    assert missing.missing[0].capability_id=='pressure_diffusion'
    assert registry.specs()==(AcousticImpedanceReference.spec,)


def test_composition_uses_existing_compiler_and_adapter_analytic_equation():
    registry=CapabilityRegistry();registry.register(AcousticImpedanceReference());registry.register(DensitySource())
    goal=request(required_inputs=(AcousticImpedanceReference.spec.inputs[0],),
        permitted_dependencies=(CapabilityReference(capability_id=DensitySource.spec.capability_id,version=DensitySource.spec.version),))
    assessment=assess_capability_gap(goal,registry)
    assert assessment.disposition=='compose_existing'
    assert [ref.capability_id for ref in assessment.selected]==['reference.authored_density','reference.acoustic_impedance']
    from geoworld_open.sdk.development import variable_contract
    plan=compile_plan([CapabilityAdapter(registry.get(ref.capability_id,ref.version)) for ref in assessment.selected],
                      [variable_contract(goal.required_inputs[0])])
    data=xr.Dataset({'vp_m_s':(('z','x'),[[3000.]],{'units':'m/s'})})
    before=data.copy(deep=True)
    seeds=SeedManager(17)
    for capability in plan.capabilities:
        context=ExecutionContext({},capability.metadata.capability_id,seeds.generator(capability.metadata.capability_id),seeds.lineage(capability.metadata.capability_id))
        fragment=capability.execute(data.copy(deep=True),context).dataset
        data=xr.merge((data,fragment),compat='identical')
    assert data['acoustic_impedance'].item()==6600000.
    xr.testing.assert_identical(before['vp_m_s'],data['vp_m_s'])


@pytest.mark.parametrize('change',[
    {'unresolved_questions':('Which physical model is scientifically admissible?',)},
    {'scientific_constraints':('field calibrated',)},
    {'required_inputs':(VariableSpec(name='vp_m_s',unit='ft/s',dimensions=('z','x'),dtype_kind=DTypeKind.FLOAT),)},
    {'required_outputs':(VariableSpec(name='acoustic_impedance',unit='Pa',dimensions=('z','x')), )},
    {'operation':CapabilityReference(capability_id='reference.acoustic_impedance',version='999')},
    {'required_inputs':()},
])
def test_ambiguous_incompatible_missing_data_are_not_code_generation(change):
    registry=CapabilityRegistry();registry.register(AcousticImpedanceReference())
    result=assess_capability_gap(request(**change),registry)
    assert result.disposition=='clarification_required' and result.questions and not result.missing


def test_duplicate_producers_unknown_inputs_and_cycles_fail_closed():
    registry=CapabilityRegistry();registry.register(AcousticImpedanceReference());registry.register(DensitySource())
    other=DensitySource();other.spec=other.spec.model_copy(update={'capability_id':'reference.other_density'})
    registry.register(other)
    goal=request(required_inputs=request().required_inputs[:1],permitted_dependencies=tuple(CapabilityReference(capability_id=item.spec.capability_id,version=item.spec.version) for item in (DensitySource(),other)))
    assessment=assess_capability_gap(goal,registry)
    assert assessment.disposition=='clarification_required' and 'Ambiguous producer' in assessment.questions[0]
    unknown=VariableSpec(name='mystery',unit='1')
    assert assess_capability_gap(request(required_inputs=(*request().required_inputs,unknown)),registry).disposition=='clarification_required'
    cyclic=DensitySource();cyclic.spec=cyclic.spec.model_copy(update={'inputs':AcousticImpedanceReference.spec.outputs})
    registry=CapabilityRegistry();registry.register(cyclic);registry.register(AcousticImpedanceReference())
    result=assess_capability_gap(request(required_inputs=request().required_inputs[:1],permitted_dependencies=(CapabilityReference(capability_id=cyclic.spec.capability_id,version=cyclic.spec.version),)),registry)
    assert result.disposition=='clarification_required' and 'cycle' in result.questions[0]


def test_missing_data_never_triggers_unrequested_source_generation():
    registry=CapabilityRegistry();registry.register(AcousticImpedanceReference());registry.register(DensitySource())
    result=assess_capability_gap(request(required_inputs=request().required_inputs[:1]),registry)
    assert result.disposition=='clarification_required' and result.selected==()
    goal=request(operation=CapabilityReference(capability_id='unknown_physics',version='1'),scientific_constraints=('unreviewed physical assumption',))
    assert assess_capability_gap(goal,registry).disposition=='clarification_required'


def test_optional_supplied_inputs_and_runtime_inputs_are_validated():
    plugin=AcousticImpedanceReference()
    optional=plugin.spec.inputs[1].model_copy(update={'required':False})
    plugin.spec=plugin.spec.model_copy(update={'inputs':(plugin.spec.inputs[0],optional)})
    registry=CapabilityRegistry();registry.register(plugin)
    bad=optional.model_copy(update={'unit':'Pa'})
    goal=request(plugin,required_inputs=(plugin.spec.inputs[0],bad))
    assert assess_capability_gap(goal,registry).disposition=='clarification_required'
    adapter=CapabilityAdapter(AcousticImpedanceReference())
    seeds=SeedManager(17)
    context=ExecutionContext({},adapter.metadata.capability_id,seeds.generator('test'),seeds.lineage('test'))
    data=xr.Dataset({'vp_m_s':(('z','x'),[[3000.]],{'units':'ft/s'}),
                     'density_kg_m3':(('z','x'),[[2200.]],{'units':'kg/m^3'})})
    before=data.copy(deep=True)
    with pytest.raises(ValueError,match='input violates'):
        adapter.execute(data,context)
    xr.testing.assert_identical(before,data)


@pytest.mark.parametrize('include_optional',[False,True])
def test_optional_outputs_are_not_guaranteed_but_are_selected_when_present(include_optional):
    plugin=OptionalOutputSource(include_optional)
    adapter=CapabilityAdapter(plugin)
    assert tuple(item.name for item in adapter.metadata.produces)==('required_value',)
    seeds=SeedManager(17)
    context=ExecutionContext(
        {},
        adapter.metadata.capability_id,
        seeds.generator('optional-output'),
        seeds.lineage('optional-output'),
    )
    result=adapter.execute(xr.Dataset(),context).dataset
    assert 'required_value' in result
    assert ('optional_value' in result)==include_optional


def test_dependency_planning_does_not_use_optional_output_as_a_producer():
    registry=CapabilityRegistry()
    registry.register(OptionalOutputSource(include_optional=True))
    registry.register(OptionalOutputConsumer())
    consumer=OptionalOutputConsumer()
    assessment=assess_capability_gap(
        request(
            consumer,
            required_inputs=(),
            permitted_dependencies=(
                CapabilityReference(
                    capability_id=OptionalOutputSource.spec.capability_id,
                    version=OptionalOutputSource.spec.version,
                ),
            ),
        ),
        registry,
    )
    assert assessment.disposition=='clarification_required'
    assert 'Missing validated input' in assessment.questions[0]


def plan():
    goal=request(operation=CapabilityReference(capability_id='missing',version='1.0'))
    assessment=assess_capability_gap(goal,CapabilityRegistry())
    checks=tuple(VerificationRequirement(check_id=kind,kind=kind,criterion='Independent accepted '+kind+' check.',expectation_source='analytical' if kind=='scientific' else 'authored_contract')
        for kind in ('unit','integration','regression','negative','scientific','conformance'))
    return CapabilityDevelopmentPlan(request=goal,assessment=assessment,components=(DevelopmentComponent(name='operator',placement='private_implementation',interface='existing standard execute(dataset, context)',purpose='Reusable numerical operator'),),
        related_operations=('changed geometry','different grid resolution'),verification=(CHECK,*checks))


def test_development_contracts_require_verification_and_never_authorize_execution():
    value=plan()
    assert CapabilityDevelopmentPlan.model_validate_json(value.model_dump_json())==value
    with pytest.raises(ValidationError):
        CapabilityDevelopmentPlan.model_validate({**value.model_dump(),'verification':[CHECK.model_dump()]})
    unresolved=value.model_dump();unresolved['request']['unresolved_questions']=['Which physical model?']
    with pytest.raises(ValidationError,match='resolve questions'):
        CapabilityDevelopmentPlan.model_validate(unresolved)
    unrelated=value.model_dump();unrelated['assessment']['missing']=[{'capability_id':'unrelated','version':'1'}]
    with pytest.raises(ValidationError,match='exact requested'):
        CapabilityDevelopmentPlan.model_validate(unrelated)
    with pytest.raises(ValidationError):
        CapabilityDevelopmentRequest.model_validate({**request().model_dump(),'unexpected':True})
    with pytest.raises(ValidationError):
        CapabilityDevelopmentRequest.model_validate({**request().model_dump(),'required_outputs':[]})
    with pytest.raises(ValidationError):
        CandidateSourceFile(path='../escape.py',sha256='a'*64)
    with pytest.raises(ValidationError):
        CandidateSourceFile(path='operator.py',sha256='wrong')
    with pytest.raises(ValidationError):
        CapabilityVerificationReport(candidate_id='candidate',manifest_sha256='a'*64,verifier='import',disposition='verified')
    evidence=tuple(VerificationEvidence(requirement=check,outcome='passed',evidence_uri='artifact://checks/'+check.check_id,evidence_sha256='a'*64) for check in value.verification)
    report=CapabilityVerificationReport(candidate_id='candidate',manifest_sha256='a'*64,verifier='reviewed-offline-runner',evidence=evidence,disposition='verified')
    assert not report.execution_authorized
    bad=[item.model_dump() for item in evidence];bad[0]['outcome']='not_run'
    with pytest.raises(ValidationError):
        CapabilityVerificationReport(candidate_id='candidate',manifest_sha256='a'*64,verifier='reviewed-offline-runner',evidence=bad,disposition='verified')


def test_verification_receipt_is_bound_to_source_and_exact_acceptance():
    from geoworld_open.sdk.verification import verify_candidate_receipt
    from geoworld_open.sdk.serialization import model_sha256
    value=plan()
    manifest=CandidateCapabilityManifest(candidate_id='candidate',request_id=value.request.request_id,
        capability=AcousticImpedanceReference.spec.model_copy(update={'capability_id':value.request.operation.capability_id,'version':value.request.operation.version}),source_files=(CandidateSourceFile(path='operator.py',sha256='a'*64),),
        entrypoint='operator:execute',license='review-required',generator='offline')
    evidence=tuple(VerificationEvidence(requirement=check,outcome='passed',evidence_uri='artifact://checks/'+check.check_id,evidence_sha256='b'*64) for check in value.verification)
    report=CapabilityVerificationReport(candidate_id=manifest.candidate_id,manifest_sha256=model_sha256(manifest),verifier='reviewed-runner',evidence=evidence,disposition='verified')
    assert verify_candidate_receipt(value,manifest,report)==report
    modified=manifest.model_copy(update={'source_files':(CandidateSourceFile(path='operator.py',sha256='c'*64),)})
    with pytest.raises(ValueError,match='manifest'):
        verify_candidate_receipt(value,modified,report)
    changed=evidence[0].requirement.model_copy(update={'criterion':'Convenient self-generated assertion'})
    substituted=report.model_copy(update={'evidence':(evidence[0].model_copy(update={'requirement':changed}),*evidence[1:])})
    with pytest.raises(ValueError,match='substitutes'):
        verify_candidate_receipt(value,manifest,substituted)
