"""Write reproducibility artifacts and provenance."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from geoworld_open import __version__
from geoworld_open.viz import save_summary_figure
from geoworld_open.workflow import WorkflowResult


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scenario_bytes(result: WorkflowResult) -> bytes:
    payload = result.scenario.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(payload, sort_keys=False).encode("utf-8")


def write_artifacts(result: WorkflowResult, output_dir: str | Path, overwrite: bool = False) -> Path:
    """Write one complete, inspectable result directory."""
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    arrays_dir = output / "arrays"
    arrays_dir.mkdir(exist_ok=True)

    scenario_path = output / "scenario.yaml"
    scenario_path.write_bytes(_scenario_bytes(result))
    for name, array in sorted(result.arrays.items()):
        np.save(arrays_dir / f"{name}.npy", array, allow_pickle=False)

    summary_path = output / "summary.png"
    save_summary_figure(result, summary_path)

    trace_path = output / "trace.json"
    trace_path.write_text(json.dumps(result.trace, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        f"# {result.scenario.name}",
        "",
        result.scenario.description,
        "",
        "## Assumptions",
        "",
        *[f"- {item}" for item in result.scenario.assumptions],
        "",
        "## Scientific scope",
        "",
        "This output is a deterministic synthetic teaching example. Properties are explicit inputs,",
        "and the seismic response uses textbook approximations. It is not field-data inversion,",
        "history matching, uncertainty quantification, or a calibrated reservoir model.",
        "",
        "## Outputs",
        "",
        *[f"- `{name}`: shape {list(array.shape)}, dtype `{array.dtype}`" for name, array in sorted(result.arrays.items())],
    ]
    (output / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    artifact_paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "schema_version": "1.0",
        "software": {"name": "geoworld-open", "version": __version__},
        "scenario": result.scenario.name,
        "scenario_sha256": hashlib.sha256(_scenario_bytes(result)).hexdigest(),
        "seed": result.scenario.seed,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "operators": [
            {key: step[key] for key in ("operator", "version", "description")} for step in result.trace
        ],
        "limitations": [
            "Synthetic educational workflow, not field-data inversion.",
            "Layer properties and perturbation multipliers are explicit scenario inputs.",
            "AVO uses a simplified linearized Aki-Richards approximation.",
        ],
        "artifacts": [
            {
                "path": str(path.relative_to(output)),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "deterministic": path == scenario_path or path.parent == arrays_dir,
            }
            for path in artifact_paths
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output
