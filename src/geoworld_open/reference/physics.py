"""Minimal transparent physics used only to demonstrate the public interface."""

from __future__ import annotations

import xarray as xr

from geoworld_open.standard import (
    CapabilityContext,
    CapabilityKind,
    CapabilityRunResult,
    CapabilitySpec,
    DTypeKind,
    ValidityDomain,
    VariableSpec,
)


class AcousticImpedanceReference:
    """Textbook acoustic impedance ``Z = Vp * rho`` with no calibration."""

    spec = CapabilitySpec(
        capability_id="reference.acoustic_impedance",
        version="1.0",
        kind=CapabilityKind.PHYSICS,
        title="Reference acoustic impedance",
        law_name="Z = Vp * density",
        inputs=(
            VariableSpec(
                name="vp_m_s",
                unit="m/s",
                dimensions=("z", "x"),
                dtype_kind=DTypeKind.FLOAT,
            ),
            VariableSpec(
                name="density_kg_m3",
                unit="kg/m^3",
                dimensions=("z", "x"),
                dtype_kind=DTypeKind.FLOAT,
            ),
        ),
        outputs=(
            VariableSpec(
                name="acoustic_impedance",
                unit="kg/(m^2*s)",
                dimensions=("z", "x"),
                dtype_kind=DTypeKind.FLOAT,
            ),
        ),
        validity_domain=ValidityDomain(
            description="Algebraic impedance from finite positive Vp and density arrays.",
            constraints=("Vp and density share the same z,x grid.",),
            excluded_uses=(
                "This reference does not infer Vp or density.",
                "This reference is not a calibrated rock-physics model.",
            ),
        ),
        assumptions=("Inputs are already expressed in declared SI units.",),
        references=("Sheriff, Encyclopedic Dictionary of Applied Geophysics.",),
    )

    def execute(
        self,
        dataset: xr.Dataset,
        context: CapabilityContext,
    ) -> CapabilityRunResult:
        del context
        result = dataset.copy(deep=True)
        impedance = result["vp_m_s"] * result["density_kg_m3"]
        impedance.attrs = {
            "units": "kg/(m^2*s)",
            "method": "reference.algebraic_product_v1",
        }
        result["acoustic_impedance"] = impedance
        return CapabilityRunResult(
            dataset=result,
            diagnostics={"method": "Z = Vp * density", "reference_implementation": True},
        )
