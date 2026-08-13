"""Canonical JSON and typed model serialization helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


def canonical_json_bytes(model: BaseModel) -> bytes:
    """Serialize a public contract deterministically without Python repr fallbacks."""

    payload = model.model_dump(mode="json", exclude_none=False)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def model_sha256(model: BaseModel) -> str:
    return hashlib.sha256(canonical_json_bytes(model)).hexdigest()


def write_model(model: BaseModel, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(model) + b"\n")
    return output


def load_model(path: str | Path, model_type: type[ModelT]) -> ModelT:
    return model_type.model_validate_json(Path(path).read_bytes())
