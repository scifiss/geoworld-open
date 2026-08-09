import ast
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


def test_public_tree_has_no_production_configuration_files() -> None:
    forbidden_names = {"render.yaml", "docker-compose.yml", ".env", "geoworld.sqlite3"}
    found = [str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.name in forbidden_names]
    assert found == []
