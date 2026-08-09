from typer.testing import CliRunner

from geoworld_open.cli import app


def test_cli_runs_canonical_workflow(tmp_path) -> None:
    scenario = "examples/scenarios/layered_reservoir.yaml"
    output = tmp_path / "cli-run"
    result = CliRunner().invoke(app, ["run", scenario, "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert "Completed layered_reservoir" in result.output
    assert (output / "manifest.json").is_file()
    assert (output / "summary.png").is_file()


def test_cli_dispatches_native_v2_structural_workflow(tmp_path) -> None:
    scenario = "examples/scenarios/structural_multifault_v2.yaml"
    output = tmp_path / "v2-run"
    result = CliRunner().invoke(app, ["run", scenario, "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert "GeoSpec V2 structural" in result.output
    assert (output / "manifest.json").is_file()
    assert (output / "structure_diagnostic.png").is_file()
    assert not (output / "arrays" / "vp_m_s.npy").exists()
