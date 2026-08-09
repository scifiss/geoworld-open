from pathlib import Path

import pytest

from geoworld_open.schema import load_scenario


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def layered_scenario():
    return load_scenario(ROOT / "examples" / "scenarios" / "layered_reservoir.yaml")


@pytest.fixture
def co2_scenario():
    return load_scenario(ROOT / "examples" / "scenarios" / "co2_monitoring.yaml")

