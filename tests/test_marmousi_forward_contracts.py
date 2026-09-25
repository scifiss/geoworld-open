import json

import pytest
from pydantic import ValidationError

from geoworld_open.client.execution import (
    ExecutionEstimate,
    ExecutionPlan,
    ExecutionPreference,
    ResourceSnapshot,
)
from geoworld_open.client.marmousi import MarmousiPreview, MarmousiSelection, ModelCrop
from geoworld_open.client.marmousi_forward import (
    MarmousiAcquisitionRequest,
    MarmousiForwardExperiment,
    MarmousiForwardPreview,
    MarmousiForwardResult,
    ResolvedMarmousiAcquisition,
)


def experiment(**acquisition):
    return MarmousiForwardExperiment(
        crop=ModelCrop(
            x_start_m=1000.0,
            x_stop_m=3400.0,
            z_start_m=0.0,
            z_stop_m=1000.0,
        ),
        acquisition=MarmousiAcquisitionRequest(
            number_of_shots=20,
            receivers_per_shot=100,
            **acquisition,
        ),
    )


def plan():
    return ExecutionPlan(
        plan_id="p" * 64,
        capability="configurable_marmousi_forward",
        workload_identity="w" * 64,
        preference=ExecutionPreference(),
        snapshot=ResourceSnapshot(
            timestamp=1.0,
            logical_cpus=8,
            available_cpu_budget=8,
            ram_available_bytes=8 * 1024**3,
            disk_free_bytes=8 * 1024**3,
        ),
        resolved_device="cpu",
        cpu_threads=2,
        estimated_ram_bytes=2 * 1024**3,
        estimated_vram_bytes=0,
        estimated_disk_bytes=128 * 1024**2,
        batch_size=1,
        execution_mode="sequential_forward_shots",
        scientific_mode="modified_experiment",
        estimate=ExecutionEstimate(
            runtime_seconds=(10.0, 60.0),
            confidence="low",
            evidence_sources=["test fixture"],
            assumptions=["test fixture"],
        ),
        feasible=True,
        reasons=["test fixture"],
        reserves={"cpu_threads": 1, "ram_bytes": 1, "vram_bytes": 1, "disk_bytes": 1},
        usable_budgets={"cpu_threads": 7, "ram_bytes": 1, "vram_bytes": 0, "disk_bytes": 1},
    )


def resolved_acquisition():
    sources = [[2, index] for index in range(20)]
    receivers = [[2, index] for index in range(100)]
    return ResolvedMarmousiAcquisition(
        source_indices_zx=sources,
        receiver_indices_zx=receivers,
        source_coordinates_xz_m=[[1000.0 + 4.0 * x, 8.0] for _, x in sources],
        receiver_coordinates_xz_m=[[1000.0 + 4.0 * x, 8.0] for _, x in receivers],
        requested_source_depth_m=8.0,
        requested_receiver_depth_m=8.0,
        resolved_source_depth_m=8.0,
        resolved_receiver_depth_m=8.0,
        geometry_sha256="b" * 64,
    )


def model_preview():
    crop = experiment().crop
    return MarmousiPreview(
        selection=MarmousiSelection(dataset="marmousi1", crop=crop),
        classification="modified_benchmark_model",
        configuration_sha256="c" * 64,
        dataset_extent=ModelCrop(
            x_start_m=0.0,
            x_stop_m=9200.0,
            z_start_m=0.0,
            z_stop_m=3000.0,
        ),
        resolved_crop=crop,
        shape_xz=[601, 251],
        spacing_m=4.0,
        fields=["vp", "density"],
        unit="m/s",
        x_m=[1000.0, 3400.0],
        z_m=[0.0, 1000.0],
        values_zx=[[1500.0, 1600.0], [1700.0, 1800.0]],
        provenance={"preview_sampling": "test fixture"},
        warnings=["No solver execution"],
    )


def test_acceptance_experiment_roundtrip_and_bounded_fields():
    value = experiment()
    assert MarmousiForwardExperiment.model_validate_json(value.model_dump_json()) == value
    assert value.acquisition.number_of_shots == 20
    assert value.acquisition.receivers_per_shot == 100
    assert value.acquisition.spacing_policy == "uniform_surface"
    assert value.settings.solver == "deepwave_scalar_0.0.26"


@pytest.mark.parametrize(
    "value",
    [
        {"crop": {"x_start_m": 1000.0, "x_stop_m": 3400.0, "z_start_m": 0.0, "z_stop_m": 1000.0},
         "acquisition": {"number_of_shots": 0}},
        {"crop": {"x_start_m": 0.0, "x_stop_m": 8.0, "z_start_m": 0.0, "z_stop_m": 100.0},
         "acquisition": {"number_of_shots": 4}},
        {"crop": {"x_start_m": 1000.0, "x_stop_m": 3400.0, "z_start_m": 100.0, "z_stop_m": 1000.0},
         "acquisition": {"source_depth_m": 8.0}},
        {"crop": {"x_start_m": 1000.0, "x_stop_m": 9300.0, "z_start_m": 0.0, "z_stop_m": 1000.0}},
        {"dataset": "marmousi2",
         "crop": {"x_start_m": 1000.0, "x_stop_m": 3400.0, "z_start_m": 0.0, "z_stop_m": 1000.0}},
    ],
)
def test_contract_rejects_invalid_crop_or_acquisition(value):
    with pytest.raises(ValidationError):
        MarmousiForwardExperiment.model_validate(value)


def test_preview_and_result_bind_hashes():
    preview = MarmousiForwardPreview(
        experiment=experiment(),
        model_preview=model_preview(),
        resolved_acquisition=resolved_acquisition(),
        crop_vp_sha256="a" * 64,
        geometry_sha256="b" * 64,
        experiment_sha256="d" * 64,
        execution_plan=plan(),
        preparation_id="e" * 32,
    )
    assert preview.solver_executed is False
    result = MarmousiForwardResult(
        experiment_sha256=preview.experiment_sha256,
        crop_vp_sha256=preview.crop_vp_sha256,
        model_input_sha256=preview.crop_vp_sha256,
        geometry_sha256=preview.geometry_sha256,
        wavelet_sha256="f" * 64,
        observed_shots_sha256="1" * 64,
        settings=preview.experiment.settings,
        runtime_seconds=1.0,
        peak_memory_mib=1.0,
        artifacts=["observed_shots.npz"],
        diagnostics={},
    )
    assert result.crop_vp_sha256 == result.model_input_sha256
    with pytest.raises(ValidationError):
        MarmousiForwardResult.model_validate({**result.model_dump(), "model_input_sha256": "2" * 64})


def test_sdk_preview_uses_authenticated_typed_endpoint():
    from geoworld_open.client import GeoWorldBackendClient

    response = MarmousiForwardPreview(
        experiment=experiment(),
        model_preview=model_preview(),
        resolved_acquisition=resolved_acquisition(),
        crop_vp_sha256="a" * 64,
        geometry_sha256="b" * 64,
        experiment_sha256="d" * 64,
        execution_plan=plan(),
        preparation_id="e" * 32,
    )

    class Transport:
        def send(self, method, url, headers, body, timeout):
            assert method == "POST" and url.endswith("/models/marmousi/forward/preview")
            assert headers["Authorization"] == "Bearer token"
            payload = json.loads(body)
            assert payload["experiment"]["acquisition"]["number_of_shots"] == 20
            assert "source_indices_zx" not in payload["experiment"]["acquisition"]
            return 200, response.model_dump_json().encode()

    parsed = GeoWorldBackendClient(
        "http://localhost:8100", token="token", transport=Transport()
    ).preview_marmousi_forward(experiment())
    assert parsed.crop_vp_sha256 == "a" * 64
