"""The one seam: ``tach check`` run against a real copy of the fixture project.

Tests assert on the observable contract -- the exit status, and which import gets
named as a violation. None of them treats the text of ``tach.toml`` as the
definition of correct behaviour: a test that pinned a particular regex would keep
passing while the rule underneath it broke. (Two tests do read the file: one
class to assert it went *unchanged*, and the cycle proof to rewrite a scratch
copy. Neither takes its contents as evidence that the rule works.)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest

FIXTURE_PROJECT = Path(__file__).resolve().parent.parent / "fixture"


@dataclass(frozen=True)
class CommandResult:
    """The outcome of one command run inside the project copy."""

    exit_code: int
    output: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def mentions(self, text: str) -> bool:
        """Whether ``text`` appears anywhere in the combined output.

        Used to check that a report points at the offending import, which is the
        part of tach's contract these tests depend on.
        """
        return text in self.output


class Project:
    """A throwaway copy of the fixture project that tests may vandalise."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def check(self) -> CommandResult:
        return self._run("tach", "check")

    def sync(self) -> CommandResult:
        return self._run("tach", "sync")

    def run_test_suite(self) -> CommandResult:
        return self._run("pytest", "-q")

    def append(self, relative_path: str, line: str) -> None:
        path = self.root / relative_path
        path.write_text(f"{path.read_text()}\n{line}\n")

    def remove(self, relative_path: str, line: str) -> None:
        """Undo an :meth:`append`, failing loudly if the line is not there."""
        path = self.root / relative_path
        contents = path.read_text()
        appended = f"\n{line}\n"
        assert appended in contents, f"{relative_path} does not contain {line!r}"
        path.write_text(contents.replace(appended, ""))

    def write(self, relative_path: str, contents: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    def read(self, relative_path: str) -> str:
        return (self.root / relative_path).read_text()

    def _run(self, module: str, *args: str) -> CommandResult:
        completed = subprocess.run(
            [sys.executable, "-m", module, *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        return CommandResult(
            exit_code=completed.returncode,
            output=completed.stdout + completed.stderr,
        )


@contextmanager
def config_untouched(project: Project) -> Iterator[None]:
    """Assert the body changed nothing about ``tach.toml``.

    This is the no-config-edits property, checked rather than assumed.
    """
    before = project.read("tach.toml")
    yield
    assert project.read("tach.toml") == before


@pytest.fixture
def project(tmp_path: Path) -> Project:
    """A clean copy of the committed fixture, one per test."""
    root = tmp_path / "project"
    shutil.copytree(
        FIXTURE_PROJECT,
        root,
        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", ".pytest_cache"),
    )
    return Project(root)
