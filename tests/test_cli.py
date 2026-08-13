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


def test_cli_validates_geospec_and_lists_benchmarks() -> None:
    runner = CliRunner()
    validated = runner.invoke(
        app,
        ["validate-geospec", "examples/scenarios/structural_multifault.yaml"],
    )
    assert validated.exit_code == 0, validated.output
    assert "Valid GeoSpec: structural_multifault" in validated.output

    listed = runner.invoke(app, ["benchmark-list"])
    assert listed.exit_code == 0, listed.output
    assert "faulted-reservoir" in listed.output
    assert "state-observation" in listed.output


def test_cli_reference_conformance() -> None:
    result = CliRunner().invoke(app, ["conformance-reference"])
    assert result.exit_code == 0, result.output
    assert "Reference capability conforms" in result.output
