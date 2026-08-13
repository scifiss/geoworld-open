import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BANNED_IMPORT_ROOTS = {
    "boto3",
    "fastapi",
    "jwt",
    "langchain",
    "ollama",
    "psycopg",
    "sqlalchemy",
}

PROTECTED_SOURCE_TERMS = {
    "geoworld.agents",
    "geoworld.api",
    "geoworld.llm",
    "geoworld.memory",
    "geoworld.vendor",
}


def test_public_source_does_not_import_private_or_production_packages() -> None:
    failures: list[str] = []
    paths = [*(ROOT / "src").rglob("*.py"), *(ROOT / "apps").rglob("*.py")]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        for name in imported:
            root = name.split(".", 1)[0]
            if name == "geoworld" or name.startswith("geoworld.") or root in BANNED_IMPORT_ROOTS:
                failures.append(f"{path.relative_to(ROOT)} imports {name}")
    assert not failures, "\n".join(failures)


def test_public_source_contains_no_private_module_dependency() -> None:
    failures: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for term in PROTECTED_SOURCE_TERMS:
            if term in source:
                failures.append(f"{path.relative_to(ROOT)} references {term}")
    assert failures == []


def test_public_tree_has_no_production_configuration_files() -> None:
    forbidden_names = {"render.yaml", "docker-compose.yml", ".env", "geoworld.sqlite3"}
    found = [str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.name in forbidden_names]
    assert found == []


def test_world_kernel_has_no_domain_or_legacy_workflow_dependency() -> None:
    failures: list[str] = []
    world_root = ROOT / "src" / "geoworld_open" / "world"
    for path in world_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("geoworld_open.") and not alias.name.startswith(
                        "geoworld_open.world"
                    ):
                        failures.append(f"{path.name} imports {alias.name}")
            if module and module.startswith("geoworld_open.") and not module.startswith(
                "geoworld_open.world"
            ):
                failures.append(f"{path.name} imports {module}")
    assert failures == []


def test_world_kernel_source_contains_no_domain_entity_vocabulary() -> None:
    world_root = ROOT / "src" / "geoworld_open" / "world"
    forbidden = {"formation", "fault", "reservoir", "heart", "robot", "geology"}
    found: list[str] = []
    for path in world_root.glob("*.py"):
        source = path.read_text(encoding="utf-8").casefold()
        for word in forbidden:
            if re.search(rf"\b{re.escape(word)}\b", source):
                found.append(f"{path.name}: {word}")
    assert found == []
