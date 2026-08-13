"""Typed loaders and validators for public World and Provenance contracts."""

from __future__ import annotations

from pathlib import Path

from geoworld_open.world import World


def validate_world(value: World | dict[str, object] | str | bytes) -> World:
    if isinstance(value, World):
        return World.model_validate(value.model_dump(mode="python"))
    if isinstance(value, (str, bytes)):
        return World.model_validate_json(value)
    return World.model_validate(value)


def load_world(path: str | Path) -> World:
    return validate_world(Path(path).read_bytes())


def verify_provenance(world: World) -> None:
    """Revalidate aggregate reference and acyclic-lineage invariants."""

    World.model_validate(world.model_dump(mode="python"))
