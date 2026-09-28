import pytest
from pydantic import ValidationError

from geoworld_open.client.seismic import (
    SeismicConversationRequest,
    SeismicDatasetSummary,
    SeismicAxis,
    SeismicViewRequest,
    SeismicWindow,
    SeismicDatasetCatalog,
    SeismicUploadRecord,
)


def _dataset():
    return SeismicDatasetSummary(
        dataset_id="a" * 24, display_name="Synthetic cube", format="segy",
        dimensionality="3d", vertical_domain="time", sample_interval=.004,
        sample_unit="s", shape=[3, 4, 20], geometry_status="established",
        axes=[
            SeismicAxis(name="inline", count=3, unit="number", start=100, stop=102, coordinates=[100, 101, 102]),
            SeismicAxis(name="crossline", count=4, unit="number", start=200, stop=203, coordinates=[200, 201, 202, 203]),
            SeismicAxis(name="time", count=20, unit="s", start=0, step=.004, stop=.076),
        ], amplitude_min=-1, amplitude_max=1, amplitude_scope="bounded sample",
        source="configured://synthetic.sgy",
    )


def test_seismic_contracts_never_require_paths_and_bound_payloads():
    dataset = _dataset()
    assert dataset.source.startswith("configured://")
    request = SeismicViewRequest(dataset_id=dataset.dataset_id, view_kind="inline", inline=101)
    assert request.max_output_samples == 500_000
    with pytest.raises(ValidationError):
        SeismicViewRequest(dataset_id=dataset.dataset_id, max_output_samples=2_000_000)
    with pytest.raises(ValidationError):
        SeismicWindow(vertical_start=2., vertical_stop=1.)
    with pytest.raises(ValidationError):
        SeismicWindow(trace_stop=0)


def test_conversation_request_carries_opaque_dataset_identity_only():
    request = SeismicConversationRequest(prompt="Show inline 1200", dataset_id="b" * 24)
    assert "path" not in request.model_dump()


def test_catalog_can_explain_rejected_geometry_without_a_host_path():
    catalog = SeismicDatasetCatalog(
        warnings=["ambiguous.sgy: 3D geometry could not be established safely."]
    )
    assert catalog.datasets == []
    assert "/home/" not in catalog.warnings[0]


def test_upload_status_exposes_identity_without_managed_path():
    record = SeismicUploadRecord(
        upload_id="f" * 32, display_filename="owned.sgy", status="ready",
        created_at="2026-09-28T12:00:00+00:00", dataset=_dataset(),
    )
    payload = record.model_dump(mode="json")
    assert payload["dataset"]["source"].startswith("configured://")
    assert "path" not in payload
