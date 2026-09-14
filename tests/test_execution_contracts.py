import pytest
from geoworld_open.client.execution import *


def example_plan():
    return ExecutionPlan(plan_id='test-only-plan',capability='test',workload_identity='test',
        preference=ExecutionPreference(),snapshot=ResourceSnapshot(timestamp=1.,logical_cpus=8,
            available_cpu_budget=6,ram_available_bytes=16*1024**3,disk_free_bytes=100*1024**3),
        resolved_device='cpu',cpu_threads=2,estimated_ram_bytes=1024**3,estimated_vram_bytes=0,
        execution_mode='test',scientific_mode='exact',
        estimate=ExecutionEstimate(runtime_seconds=(5,15),confidence='low',evidence_sources=['test fixture'],assumptions=[]),
        feasible=True,reasons=[],reserves={},usable_budgets={})


def test_execution_roundtrip_and_defaults():
    plan=example_plan()
    assert ExecutionPlan.model_validate_json(plan.model_dump_json())==plan
    assert ExecutionPreference().model_dump()==dict(device='auto',priority='balanced',locality='prefer_local',
        max_cpu_threads=None,max_ram_bytes=None,max_vram_bytes=None)
    assert plan.allocation_guaranteed is False


@pytest.mark.parametrize('field',['hostname','username','ip_address','environment','credentials','path'])
def test_snapshot_rejects_host_identifiers(field):
    payload=example_plan().snapshot.model_dump()
    payload[field]='must not leak'
    with pytest.raises(ValueError):
        ResourceSnapshot(**payload)


@pytest.mark.parametrize('value',[(20,10),(-1,1),(0,float('inf'))])
def test_estimate_rejects_invalid_range(value):
    with pytest.raises(ValueError):
        ExecutionEstimate(runtime_seconds=value,confidence='low',evidence_sources=[],assumptions=[])


def test_fwi_contract_never_accepts_arbitrary_solver_inputs():
    from geoworld_open.client.fwi import FWISelection,FWIPreviewRequest
    with pytest.raises(ValueError):
        FWISelection(velocity=[[1500]])
    with pytest.raises(ValueError):
        FWIPreviewRequest(prompt='run',selection=FWISelection())
