"""Read-only discovery through the existing registry and dependency compiler."""
from __future__ import annotations

from geoworld_open.engine import CapabilityMetadata, CapabilityResult, VariableContract, compile_plan
from geoworld_open.engine.plan import _assert_compatible
from geoworld_open.sdk.registry import CapabilityRegistry
from geoworld_open.standard.capabilities import CapabilityContext, DTypeKind
from geoworld_open.standard.development import CapabilityDevelopmentRequest, CapabilityGapAssessment, CapabilityReference


def variable_contract(variable):
    dtype = {DTypeKind.FLOAT:'f', DTypeKind.INTEGER:'i', DTypeKind.BOOLEAN:'b', DTypeKind.STRING:'U'}.get(variable.dtype_kind)
    return VariableContract(variable.name, variable.dimensions, variable.unit, dtype)


class CapabilityAdapter:
    """Bridge public plugin declarations to Gate 3's execution contract."""
    def __init__(self, capability):
        self.capability = capability
        spec = capability.spec
        self.metadata = CapabilityMetadata(spec.capability_id, spec.version, spec.law_name or spec.capability_id,
            requires=tuple(variable_contract(item) for item in spec.inputs if item.required),
            produces=tuple(variable_contract(item) for item in spec.outputs),
            assumptions=spec.assumptions, references=spec.references, deterministic=spec.deterministic)

    def execute(self, dataset, context):
        from copy import deepcopy
        import xarray as xr
        from geoworld_open.conformance.suite import _validate_variables
        issues=_validate_variables(dataset,self.capability.spec.inputs,owner='input')
        if issues:
            raise ValueError('Plugin input violates its public contract: '+str(issues))
        # Use the existing derived seed, not a new randomization authority.
        seed = int(context.seed_lineage['state_preview'][0])
        parameters = deepcopy(context.input_data) if isinstance(context.input_data, dict) else {}
        supplied=dataset.copy(deep=True)
        result = self.capability.execute(supplied, CapabilityContext(seed=seed, parameters=parameters))
        xr.testing.assert_identical(supplied,dataset)
        issues=_validate_variables(result.dataset,self.capability.spec.outputs,owner='output')
        if issues:
            raise ValueError('Plugin output violates its public contract: '+str(issues))
        fragment=result.dataset[[item.name for item in self.metadata.produces]]
        return CapabilityResult(fragment, result.diagnostics)


def assess_capability_gap(request: CapabilityDevelopmentRequest, registry: CapabilityRegistry) -> CapabilityGapAssessment:
    """Exact typed operation discovery, never natural-language/scenario substitution.

    Contract compatibility is a planning check. Data applicability, licensing and
    execution authorization remain existing deterministic execution gates.
    """
    request = CapabilityDevelopmentRequest.model_validate(request)
    def clarify(message):
        return CapabilityGapAssessment(request_id=request.request_id, disposition='clarification_required',
            reason='Existing interfaces cannot safely resolve this request.', questions=(message,))
    if request.unresolved_questions:
        return clarify(request.unresolved_questions[0])
    specs = registry.specs()
    root = next((item for item in specs if (item.capability_id,item.version)==
                 (request.operation.capability_id,request.operation.version)),None)
    if root is None:
        if request.scientific_constraints:
            return clarify('The missing operation has unreviewed scientific constraints. Resolve validity before requesting implementation.')
        if any(item.capability_id == request.operation.capability_id for item in specs):
            return clarify('The requested version is unavailable; approve an explicit compatible version.')
        return CapabilityGapAssessment(request_id=request.request_id, disposition='development_required',
            reason='The requested operation is not registered; no substitute or scenario was selected.', missing=(request.operation,))
    declared = {item.name:variable_contract(item) for item in root.outputs}
    def compatible(required,produced):
        if produced is None or required.name!=produced.name:
            return False
        try:
            _assert_compatible(required,produced,request.operation.capability_id)
        except ValueError:
            return False
        return True
    if any(not compatible(variable_contract(item),declared.get(item.name)) for item in request.required_outputs):
        return clarify('Requested outputs or their units/dimensions do not match the registered operation.')
    supported_constraints = set(root.validity_domain.constraints)
    if any(item not in supported_constraints for item in request.scientific_constraints):
        return clarify('Scientific constraints require explicit applicability review; they are not established by interface matching.')
    available = {item.name:variable_contract(item) for item in request.required_inputs}
    selected, visiting = {}, set()
    permitted={(item.capability_id,item.version) for item in request.permitted_dependencies}
    permitted.add((request.operation.capability_id,request.operation.version))
    def visit(spec):
        key=(spec.capability_id,spec.version)
        if key in visiting:
            raise ValueError('Capability dependency cycle')
        if key in selected:
            return
        visiting.add(key)
        for required in spec.inputs:
            contract=variable_contract(required)
            if required.name in available:
                if not compatible(contract,available[required.name]):
                    raise ValueError('Input units, dimensions or dtype are incompatible: '+required.name)
                continue
            if not required.required:
                continue
            producers=[candidate for candidate in specs if (candidate.capability_id,candidate.version) in permitted
                       and any(compatible(contract,variable_contract(output)) for output in candidate.outputs)]
            if len(producers)!=1:
                raise ValueError(('Missing validated input or unique producer: ' if not producers else 'Ambiguous producer for: ')+required.name)
            visit(producers[0])
        visiting.remove(key)
        selected[key]=CapabilityAdapter(registry.get(*key))
    try:
        visit(root)
        plan=compile_plan(selected.values(), available.values())
        consumed={variable.name for adapter in selected.values() for variable in adapter.capability.spec.inputs}
        if set(available)-consumed:
            raise ValueError('Supplied inputs are not consumed by the selected interfaces: '+', '.join(sorted(set(available)-consumed)))
    except (ValueError, KeyError) as exc:
        return clarify(str(exc))
    references=tuple(CapabilityReference(capability_id=item.metadata.capability_id,version=item.metadata.version) for item in plan.capabilities)
    return CapabilityGapAssessment(request_id=request.request_id,
        disposition='execute_existing' if len(references)==1 else 'compose_existing',
        reason='Existing versioned interfaces form a compatible dependency plan; execution admission is still required.', selected=references)
