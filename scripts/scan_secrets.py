#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "runs",
}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PLACEHOLDER_MARKERS = (
    "${",
    "<",
    ">",
    "abc123",
    "changeme",
    "change-me",
    "dummy",
    "example",
    "placeholder",
    "random-secret",
    "redacted",
    "replace-me",
    "test-secret",
    "token123",
    "user:pass@",
)
PATTERNS = {
    "AWS access key": re.compile(r"(?:A" + r"KIA|ASIA)[A-Z0-9]{16}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "OpenAI-style token": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    "credential URL": re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@[^\s]+", re.IGNORECASE),
}
ASSIGNMENT = re.compile(
    r"(?i)\b(?:AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|DATABASE_URL|JWT_SECRET|"
    r"API_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD)\s*=\s*([^\s#]+)"
)


def tracked_files() -> list[Path]:
    completed = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True)
    return [Path(item.decode()) for item in completed.stdout.split(b"\0") if item]


def all_files(root: Path) -> list[Path]:
    return [
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)
    ]


def is_placeholder(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def scan_file(path: Path) -> list[tuple[int, str]]:
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return []
    if path.name.startswith(".env") and not path.name.endswith(".example"):
        return [(1, "non-example environment file")]
    if path.suffix.casefold() not in TEXT_SUFFIXES or path.stat().st_size > 5_000_000:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line) and not is_placeholder(line):
                findings.append((line_number, label))
        assignment = ASSIGNMENT.search(line)
        if assignment and not is_placeholder(line) and not is_placeholder(assignment.group(1)):
            findings.append((line_number, "non-placeholder sensitive assignment"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan repository text for likely committed secrets.")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--all-files", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    paths = args.paths or (all_files(root) if args.all_files else tracked_files())
    findings = []
    for relative in paths:
        path = relative if relative.is_absolute() else root / relative
        if not path.exists() or not path.is_file():
            continue
        for line_number, label in scan_file(path):
            findings.append(f"{path.relative_to(root)}:{line_number}: {label}")
    if findings:
        print("Potential secrets detected:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print(f"Secret scan passed ({len(paths)} paths checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

