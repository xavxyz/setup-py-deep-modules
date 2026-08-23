"""The one seam: ``tach check`` run against a real copy of the fixture project.

Every test here asserts on the observable contract -- the exit status, and which
import gets named as a violation. Nothing asserts on the contents of
``tach.toml``: a test that pinned a particular regex would keep passing while the
rule underneath it broke.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parent.parent / "fixture"


@dataclass(frozen=True)
class CheckResult:
    """What ``tach check`` said."""

    exit_code: int
    output: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def names(self, import_path: str) -> bool:
        """Whether the report points at ``import_path`` as the offending import."""
        return import_path in self.output


class Fixture:
    """A throwaway copy of the fixture project that tests may vandalise."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def check(self) -> CheckResult:
        return self._run("tach", "check")

    def run_test_suite(self) -> CheckResult:
        return self._run("pytest", "-q")

    def sync(self) -> CheckResult:
        return self._run("tach", "sync")

    def append(self, relative_path: str, line: str) -> None:
        path = self.root / relative_path
        path.write_text(f"{path.read_text()}\n{line}\n")

    def write(self, relative_path: str, contents: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    def read(self, relative_path: str) -> str:
        return (self.root / relative_path).read_text()

    def _run(self, module: str, *args: str) -> CheckResult:
        completed = subprocess.run(
            [sys.executable, "-m", module, *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        return CheckResult(
            exit_code=completed.returncode,
            output=completed.stdout + completed.stderr,
        )


@pytest.fixture
def project(tmp_path: Path) -> Fixture:
    """A clean copy of the committed fixture, one per test."""
    root = tmp_path / "project"
    shutil.copytree(
        FIXTURE,
        root,
        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", ".pytest_cache"),
    )
    return Fixture(root)
