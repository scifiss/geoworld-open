"""Transparent analytic numerics for the bounded flagship demonstration."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import numpy as np
import xarray as xr

from geoworld_open.domains.geoscience.flagship.input import CompiledFlagshipInput
from geoworld_open.engine import SeedManager


DEPTH_X = ("depth", "x")


@dataclass(frozen=True)
class PressureObservationRow:
    well_id: str
    sample_depth_m: float
    model_time_days: float
    true_model_pressure_pa: float
    observed_pressure_pa: float


def compute_baseline_fields(
    flagship_input: CompiledFlagshipInput,
    structural_dataset: xr.Dataset,
) -> xr.Dataset:
    """Return illustrative hydrostatic pressure and linear temperature fields."""
    depth = np.asarray(structural_dataset.coords["depth"].values, dtype=float)
    reservoir = np.asarray(structural_dataset["reservoir_selection"].values, dtype=bool)
    baseline = flagship_input.baseline
    pressure_by_depth = baseline.pressure_reference_pa + (
        baseline.reference_density_kg_m3
        * baseline.gravity_m_s2
        * (depth - baseline.pressure_reference_depth_m)
    )
    pressure = np.broadcast_to(pressure_by_depth[:, None], reservoir.shape).copy()
    pressure[~reservoir] = np.nan
    temperature_by_depth = baseline.temperature_reference_deg_c + (
        baseline.geothermal_gradient_deg_c_per_m
        * (depth - baseline.temperature_reference_depth_m)
    )
    temperature = np.broadcast_to(
        temperature_by_depth[:, None], reservoir.shape
    ).copy()
    return xr.Dataset(
        data_vars={
            "pressure": (
                DEPTH_X,
                pressure,
                {
                    "units": "Pa",
                    "long_name": "illustrative hydrostatic baseline pressure",
                    "method_id": "illustrative_hydrostatic_pressure_v1",
                    "applicability": "finite only where reservoir_selection is true",
                },
            ),
            "temperature": (
                DEPTH_X,
                temperature,
                {
                    "units": "degC",
                    "long_name": "illustrative linear geothermal-gradient field",
                    "method_id": "linear_geothermal_gradient_v1",
                },
            ),
        },
        coords={
            "depth": structural_dataset.coords["depth"],
            "x": structural_dataset.coords["x"],
        },
    )


def compute_perturbed_pressure_fields(
    flagship_input: CompiledFlagshipInput,
    structural_dataset: xr.Dataset,
    baseline_dataset: xr.Dataset,
) -> xr.Dataset:
    """Apply the explicit Gaussian-like benchmark; no flow equation is solved."""
    x = np.asarray(structural_dataset.coords["x"].values, dtype=float)
    depth = np.asarray(structural_dataset.coords["depth"].values, dtype=float)
    xx, zz = np.meshgrid(x, depth)
    reservoir = np.asarray(structural_dataset["reservoir_selection"].values, dtype=bool)
    config = flagship_input.perturbation
    exponent = -0.5 * (
        ((xx - config.center_x_m) / config.sigma_x_m) ** 2
        + ((zz - config.center_depth_m) / config.sigma_depth_m) ** 2
    )
    delta_pressure = config.maximum_delta_pressure_pa * np.exp(exponent)
    delta_pressure = np.where(reservoir, delta_pressure, 0.0)
    pressure = np.asarray(baseline_dataset["pressure"].values) + delta_pressure
    temperature = np.asarray(baseline_dataset["temperature"].values).copy()
    return xr.Dataset(
        data_vars={
            "pressure": (
                DEPTH_X,
                pressure,
                {
                    "units": "Pa",
                    "long_name": "pressure after analytic synthetic perturbation",
                    "method_id": "analytic_pressure_perturbation_v1",
                    "applicability": "finite only where reservoir_selection is true",
                },
            ),
            "pressure_perturbation": (
                DEPTH_X,
                delta_pressure,
                {
                    "units": "Pa",
                    "long_name": "analytic Gaussian-like pressure perturbation",
                    "method_id": "analytic_pressure_perturbation_v1",
                    "outside_reservoir": "zero",
                },
            ),
            "temperature": (
                DEPTH_X,
                temperature,
                {
                    "units": "degC",
                    "long_name": "unchanged illustrative linear geothermal-gradient field",
                    "method_id": "linear_geothermal_gradient_v1",
                },
            ),
        },
        coords={
            "depth": structural_dataset.coords["depth"],
            "x": structural_dataset.coords["x"],
        },
    )


def sample_well_pressure(
    flagship_input: CompiledFlagshipInput,
    perturbed_dataset: xr.Dataset,
) -> tuple[tuple[PressureObservationRow, ...], dict[str, object]]:
    """Nearest-cell sample with explicit deterministic Gaussian noise."""
    x = np.asarray(perturbed_dataset.coords["x"].values, dtype=float)
    depth = np.asarray(perturbed_dataset.coords["depth"].values, dtype=float)
    pressure = np.asarray(perturbed_dataset["pressure"].values, dtype=float)
    x_index = int(np.argmin(np.abs(x - flagship_input.well.x_m)))
    manager = SeedManager(flagship_input.observation.noise_seed)
    namespace = flagship_input.observation.noise_namespace
    rng = manager.generator(namespace)
    rows: list[PressureObservationRow] = []
    for sample_depth in flagship_input.observation.sample_depths_m:
        depth_index = int(np.argmin(np.abs(depth - sample_depth)))
        true_pressure = float(pressure[depth_index, x_index])
        if not np.isfinite(true_pressure):
            raise ValueError(
                f"well-pressure sample at {sample_depth:g} m lies outside ReservoirRegion"
            )
        noise = (
            float(rng.normal(0.0, flagship_input.observation.noise_sigma_pa))
            if flagship_input.observation.noise_sigma_pa
            else 0.0
        )
        rows.append(
            PressureObservationRow(
                well_id=f"well:{flagship_input.well.id}",
                sample_depth_m=float(depth[depth_index]),
                model_time_days=flagship_input.perturbation.model_time_days,
                true_model_pressure_pa=true_pressure,
                observed_pressure_pa=true_pressure + noise,
            )
        )
    return tuple(rows), manager.lineage(namespace)


def well_trajectory_csv_bytes(flagship_input: CompiledFlagshipInput) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("well_id", "sample", "x_m", "depth_m"))
    for sample, depth in enumerate(
        (flagship_input.well.top_depth_m, flagship_input.well.bottom_depth_m)
    ):
        writer.writerow(
            (
                f"well:{flagship_input.well.id}",
                sample,
                format(flagship_input.well.x_m, ".17g"),
                format(depth, ".17g"),
            )
        )
    return stream.getvalue().encode("utf-8")


def observation_csv_bytes(rows: tuple[PressureObservationRow, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "well_id",
            "sample_depth_m",
            "model_time_days",
            "true_model_pressure_pa",
            "observed_pressure_pa",
        )
    )
    for row in rows:
        writer.writerow(
            (
                row.well_id,
                format(row.sample_depth_m, ".17g"),
                format(row.model_time_days, ".17g"),
                format(row.true_model_pressure_pa, ".17g"),
                format(row.observed_pressure_pa, ".17g"),
            )
        )
    return stream.getvalue().encode("utf-8")
