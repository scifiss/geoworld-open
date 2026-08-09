"""Standalone local demo; no API, authentication, database, or LLM."""

from pathlib import Path
import tempfile

import streamlit as st
import yaml

from geoworld_open.artifacts import write_artifacts
from geoworld_open.schema import ScenarioSpec
from geoworld_open.workflow import run_workflow


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = sorted((ROOT / "examples" / "scenarios").glob("*.yaml"))

st.set_page_config(page_title="GeoWorld Open", layout="wide")
st.title("GeoWorld Open")
st.caption("A local, deterministic synthetic geoscience sandbox. No account or network service is used.")

selected = st.selectbox("Public scenario", SCENARIOS, format_func=lambda path: path.stem.replace("_", " ").title())
source = st.text_area("GeoSpec YAML", selected.read_text(encoding="utf-8"), height=420)

try:
    scenario = ScenarioSpec.model_validate(yaml.safe_load(source))
except Exception as exc:  # Streamlit should show Pydantic's actionable validation text.
    st.error(f"GeoSpec is invalid: {exc}")
    scenario = None
else:
    st.success("GeoSpec is valid and ready to run.")

if st.button("Run deterministic workflow", type="primary", disabled=scenario is None):
    assert scenario is not None
    with st.spinner("Running transparent NumPy operators..."):
        result = run_workflow(scenario)
        output = Path(tempfile.mkdtemp(prefix="geoworld-open-"))
        write_artifacts(result, output)
    st.success("Run completed.")
    st.image(str(output / "summary.png"), use_container_width=True)
    st.markdown((output / "report.md").read_text(encoding="utf-8"))
    with st.expander("Execution trace and local artifact path"):
        st.json(result.trace)
        st.code(str(output))

