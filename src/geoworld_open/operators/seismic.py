"""Textbook acoustic reflectivity and Ricker-wavelet convolution."""

from __future__ import annotations

from typing import Any

import numpy as np

from geoworld_open.schema import ScenarioSpec

from .base import OperatorMetadata


def ricker_wavelet(frequency_hz: float, dt_s: float, duration_s: float) -> np.ndarray:
    """Return a symmetric, peak-normalized Ricker wavelet."""
    sample_count = max(3, int(round(duration_s / dt_s)) + 1)
    if sample_count % 2 == 0:
        sample_count += 1
    time = (np.arange(sample_count) - sample_count // 2) * dt_s
    term = (np.pi * frequency_hz * time) ** 2
    wavelet = (1.0 - 2.0 * term) * np.exp(-term)
    return wavelet / np.max(np.abs(wavelet))


def convolve_traces(reflectivity: np.ndarray, wavelet: np.ndarray) -> np.ndarray:
    """Convolve each vertical trace and preserve the input shape."""
    result = np.empty_like(reflectivity, dtype=float)
    for column in range(reflectivity.shape[1]):
        full = np.convolve(reflectivity[:, column], wavelet, mode="full")
        start = (wavelet.size - 1) // 2
        result[:, column] = full[start : start + reflectivity.shape[0]]
    return result


class AcousticSyntheticOperator:
    metadata = OperatorMetadata(
        name="acoustic_synthetic",
        version="1.0",
        description="Normal-incidence impedance reflectivity convolved with a Ricker wavelet.",
    )

    def run(self, arrays: dict[str, np.ndarray], context: dict[str, Any]) -> dict[str, np.ndarray]:
        scenario: ScenarioSpec = context["scenario"]
        impedance = arrays["vp_m_s"] * arrays["density_kg_m3"]
        reflectivity = np.zeros_like(impedance)
        denominator = impedance[1:] + impedance[:-1]
        reflectivity[1:] = np.divide(
            impedance[1:] - impedance[:-1],
            denominator,
            out=np.zeros_like(denominator),
            where=np.abs(denominator) > 1e-12,
        )
        wavelet = ricker_wavelet(
            scenario.geophysics.wavelet_frequency_hz,
            scenario.geophysics.sample_interval_s,
            scenario.geophysics.wavelet_duration_s,
        )
        synthetic = convolve_traces(reflectivity, wavelet)
        return {
            "acoustic_impedance": impedance,
            "normal_reflectivity": np.nan_to_num(reflectivity),
            "synthetic_seismic": np.nan_to_num(synthetic),
            "ricker_wavelet": wavelet,
        }

