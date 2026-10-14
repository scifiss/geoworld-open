"""Bind a verification receipt to its exact development plan and source manifest.

No test/source execution and no automatic capability registration occur here.
The authenticity and independence of verifier evidence require a reviewed runner.
"""
from geoworld_open.sdk.serialization import model_sha256
from geoworld_open.standard.development import CapabilityDevelopmentPlan, CandidateCapabilityManifest, CapabilityVerificationReport


def verify_candidate_receipt(plan, manifest, report):
    plan=CapabilityDevelopmentPlan.model_validate(plan)
    manifest=CandidateCapabilityManifest.model_validate(manifest)
    report=CapabilityVerificationReport.model_validate(report)
    if manifest.request_id!=plan.request.request_id or report.candidate_id!=manifest.candidate_id or report.manifest_sha256!=model_sha256(manifest):
        raise ValueError('Verification receipt does not bind the planned candidate and exact source manifest')
    if (manifest.capability.capability_id,manifest.capability.version)!=(plan.request.operation.capability_id,plan.request.operation.version):
        raise ValueError('Verification candidate does not implement the requested operation/version')
    expected={check.check_id:check for check in plan.verification}
    received={item.requirement.check_id:item for item in report.evidence}
    if report.disposition=='verified' and (set(expected)!=set(received) or any(received[key].requirement!=check for key,check in expected.items())):
        raise ValueError('Verification omits or substitutes planned scientific acceptance evidence')
    return report
