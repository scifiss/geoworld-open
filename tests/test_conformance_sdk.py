import numpy as np
import xarray as xr

from geoworld_open.conformance import check_capability
from geoworld_open.reference import AcousticImpedanceReference
from geoworld_open.standard import CapabilityContext, CapabilityRunResult


def _dataset() -> xr.Dataset:
    return xr.Dataset(
        {
            "vp_m_s": (("z", "x"), np.full((2, 2), 2500.0), {"units": "m/s"}),
            "density_kg_m3": (
                ("z", "x"),
                np.full((2, 2), 2200.0),
                {"units": "kg/m^3"},
            ),
        }
    )


def test_reference_capability_passes_conformance() -> None:
    report = check_capability(AcousticImpedanceReference(), _dataset())
    assert report.conforms, report.issues


class MutatingCapability(AcousticImpedanceReference):
    def execute(self, dataset: xr.Dataset, context: CapabilityContext) -> CapabilityRunResult:
        dataset["vp_m_s"].values[0, 0] = 1.0
        return super().execute(dataset, context)


class WrongUnitCapability(AcousticImpedanceReference):
    def execute(self, dataset: xr.Dataset, context: CapabilityContext) -> CapabilityRunResult:
        result = super().execute(dataset, context)
        result.dataset["acoustic_impedance"].attrs["units"] = "wrong"
        return result


def test_conformance_detects_input_mutation() -> None:
    report = check_capability(MutatingCapability(), _dataset())
    assert not report.conforms
    assert "input_mutation" in {item.code for item in report.issues}


def test_conformance_detects_invalid_output_contract() -> None:
    report = check_capability(WrongUnitCapability(), _dataset())
    assert not report.conforms
    assert "unit_mismatch" in {item.code for item in report.issues}
