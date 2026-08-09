"""Command-line interface for the public workflow."""

from __future__ import annotations

from pathlib import Path

import typer

from geoworld_open.artifacts import write_artifacts
from geoworld_open.schema import load_scenario
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
    spec = load_scenario(scenario)
    result = run_workflow(spec)
    path = write_artifacts(result, output, overwrite=overwrite)
    typer.echo(f"Completed {spec.name}: {path.resolve()}")


if __name__ == "__main__":
    app()
