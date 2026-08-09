"""Command-line interface for the public workflow."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from geoworld_open.artifacts import write_artifacts, write_structural_artifacts
from geoworld_open.science import run_structural_workflow
from geoworld_open.schema import load_scenario
from geoworld_open.specs import load_geospec_v2
from geoworld_open.workflow import run_workflow

app = typer.Typer(no_args_is_help=True, help="Run deterministic GeoWorld Open scenarios.")


@app.callback()
def main() -> None:
    """Run deterministic GeoWorld Open scenarios."""


@app.command()
def run(
    scenario: Path = typer.Argument(..., exists=True, readable=True, help="Public GeoSpec YAML file."),
    output: Path = typer.Option(Path("runs/demo"), "--output", "-o", help="Artifact directory."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace files in a non-empty output directory."),
) -> None:
    """Validate a scenario, execute the workflow, and write artifacts."""
    header = yaml.safe_load(scenario.read_text(encoding="utf-8"))
    if header.get("schema_version") == "2.0":
        spec_v2 = load_geospec_v2(scenario)
        result_v2 = run_structural_workflow(spec_v2)
        path = write_structural_artifacts(result_v2, output, overwrite=overwrite)
        typer.echo(f"Completed {spec_v2.metadata.name} [GeoSpec V2 structural]: {path.resolve()}")
        return
    spec_v1 = load_scenario(scenario)
    result_v1 = run_workflow(spec_v1)
    path = write_artifacts(result_v1, output, overwrite=overwrite)
    typer.echo(f"Completed {spec_v1.name} [GeoSpec V1 legacy]: {path.resolve()}")


if __name__ == "__main__":
    app()
