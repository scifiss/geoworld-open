from __future__ import annotations

from pathlib import Path

import pytest

from scripts.scan_secrets import scan_file


@pytest.mark.parametrize(
    "content",
    [
        "AWS_ACCESS_" + "KEY_ID=" + "A" + "KIA" + "A" * 16,
        "AWS_BEARER_TOKEN_" + "BEDROCK=" + "sensitive-" + "value" * 6,
        "GITHUB_" + "TOKEN=" + "gh" + "p_" + "A" * 24,
        "TOKEN=" + "github_" + "pat_" + "A" * 24,
        "-----BEGIN " + "PRIVATE KEY-----",
        "https://user:" + "password" + "@service.invalid/path",
    ],
)
def test_secret_shapes_are_detected(tmp_path: Path, content: str) -> None:
    candidate = tmp_path / "candidate.txt"
    candidate.write_text(content, encoding="utf-8")

    assert scan_file(candidate)


def test_placeholder_example_is_allowed(tmp_path: Path) -> None:
    candidate = tmp_path / ".env.example"
    candidate.write_text(
        "AWS_BEARER_TOKEN_BEDROCK=<replace-me>\n",
        encoding="utf-8",
    )

    assert scan_file(candidate) == []


def test_nonexample_environment_file_is_rejected(tmp_path: Path) -> None:
    candidate = tmp_path / ".env"
    candidate.write_text("# even an apparently empty env file is unsafe\n", encoding="utf-8")

    assert scan_file(candidate) == [(1, "non-example environment file")]
