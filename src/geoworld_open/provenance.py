"""Public, sanitized scientific provenance helpers."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from geoworld_open import __version__


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEPENDENCIES = ("numpy", "xarray", "pydantic", "PyYAML", "matplotlib")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def canonical_json(payload: Any) -> bytes:
    return json.dumps(json_safe(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_value(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def software_provenance() -> dict[str, Any]:
    dependencies: dict[str, str | None] = {}
    for package in DEPENDENCIES:
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    revision = _git_value("rev-parse", "HEAD")
    status = _git_value("status", "--porcelain", "--untracked-files=no")
    return {
        "software": {"name": "geoworld-open", "version": __version__},
        "git": {
            "revision": revision,
            "dirty": None if status is None and revision is None else bool(status),
        },
        "runtime": {
            "python_version": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "dependencies": dependencies,
    }


def dataset_metadata(dataset: xr.Dataset) -> dict[str, Any]:
    return {
        "dimensions": {name: int(size) for name, size in dataset.sizes.items()},
        "coordinates": {
            name: {
                "dimensions": list(coordinate.dims),
                "dtype": str(coordinate.dtype),
                "size": int(coordinate.size),
                "metadata": json_safe(coordinate.attrs),
            }
            for name, coordinate in dataset.coords.items()
        },
        "variables": {
            name: {
                "dimensions": list(variable.dims),
                "dtype": str(variable.dtype),
                "shape": list(variable.shape),
                "metadata": json_safe(variable.attrs),
            }
            for name, variable in dataset.data_vars.items()
        },
        "metadata": json_safe(dataset.attrs),
    }


def hash_data_array(variable: xr.DataArray) -> str:
    digest = hashlib.sha256()
    digest.update(canonical_json({"name": variable.name, "dims": variable.dims, "attrs": variable.attrs}))
    values = np.asarray(variable.values)
    digest.update(values.dtype.str.encode("ascii"))
    if values.dtype.kind in {"O", "U", "S"}:
        digest.update(canonical_json(values.tolist()))
    else:
        digest.update(np.ascontiguousarray(values).tobytes())
    return digest.hexdigest()


def scientific_hashes(dataset: xr.Dataset) -> dict[str, Any]:
    coordinate_hashes = {name: hash_data_array(value) for name, value in dataset.coords.items()}
    variable_hashes = {name: hash_data_array(value) for name, value in dataset.data_vars.items()}
    combined = sha256_bytes(canonical_json({"coordinates": coordinate_hashes, "variables": variable_hashes}))
    return {
        "dataset_sha256": combined,
        "coordinates": coordinate_hashes,
        "variables": variable_hashes,
    }
