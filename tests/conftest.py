"""The one seam: ``tach check`` run against a real copy of the fixture project.

Tests assert on the observable contract -- the exit status, and which import gets
named as a violation. None of them treats the text of ``tach.toml`` as the
definition of correct behaviour: a test that pinned a particular regex would keep
passing while the rule underneath it broke. (Two tests do read the file: one
class to assert it went *unchanged*, and the cycle proof to rewrite a scratch
copy. Neither takes its contents as evidence that the rule works.)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import pytest

#: The skill as it ships: everything an installer copies, and nothing else.
SKILL_DIRECTORY = (
    Path(__file__).resolve().parent.parent / "skills" / "setup-py-deep-modules"
)

#: The mechanical half, which the skill drives.
SKILL_SCRIPT = SKILL_DIRECTORY / "scripts" / "setup_deep_modules.py"

#: The fixture is part of the skill, not a sibling of it.
FIXTURE_PROJECT = SKILL_DIRECTORY / "fixture"


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

    def check_cycles(self) -> CommandResult:
        return self._run_script("scripts/check_cycles.py")

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
        return self._invoke(["-m", module, *args])

    def _run_script(self, relative_path: str) -> CommandResult:
        return self._invoke([relative_path])

    def _invoke(self, arguments: list[str]) -> CommandResult:
        completed = subprocess.run(
            [sys.executable, *arguments],
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


class UserRepo(Project):
    """A synthetic repo standing in for the one a user runs the skill in.

    It is a ``Project`` too, so the same ``check``/``check_cycles`` assertions
    that prove the fixture apply to a repo the skill has just set up -- which is
    the point: what the skill writes has to bite the same way.

    ``script`` is which copy of the skill to drive. It defaults to the one in
    this checkout; the self-containment tests point it at a scratch install
    instead, which is the whole question they ask.
    """

    def __init__(self, root: Path, script: Path = SKILL_SCRIPT) -> None:
        super().__init__(root)
        self.script = script

    def detect(self) -> CommandResult:
        return self.skill("detect")

    def facts(self) -> dict:
        """The detection result, parsed. Fails loudly if detection did not run."""
        result = self.detect()
        assert result.passed, result.output
        return json.loads(result.output)

    def configure(self, *args: str) -> CommandResult:
        return self.skill("configure", *args)

    def scaffold(self, *args: str) -> CommandResult:
        return self.skill("scaffold", *args)

    def document(self, *args: str) -> CommandResult:
        return self.skill("document", *args)

    def skill(self, *args: str) -> CommandResult:
        return self._invoke([str(self.script), *args])

    def exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).exists()


#: What the ``user_repo`` fixture hands a test: a builder for one synthetic repo.
RepoBuilder = Callable[..., "UserRepo"]


@pytest.fixture
def user_repo(tmp_path: Path) -> RepoBuilder:
    """Builds a synthetic user repo of a given layout, on demand.

    Layouts are built by hand rather than copied from the fixture: the whole
    question these tests answer is whether the skill copes with a project it did
    not write, so the input must not be the thing it is about to produce.
    """

    def build(
        layout: str = "src",
        *,
        name: str = "acme-widgets",
        package: str = "acme_widgets",
        pyproject: str | None = None,
        files: dict[str, str] | None = None,
        tests: bool = True,
        script: Path = SKILL_SCRIPT,
    ) -> UserRepo:
        root = tmp_path / "user_repo"
        root.mkdir(exist_ok=True)
        repo = UserRepo(root, script)

        if pyproject is None:
            pyproject = DEFAULT_PYPROJECT.format(name=name, layout_config=(
                SETUPTOOLS_SRC if layout == "src" else ""
            ))
        repo.write("pyproject.toml", pyproject)

        package_root = f"src/{package}" if layout == "src" else package
        repo.write(f"{package_root}/__init__.py", '"""The user\'s own code."""\n')
        repo.write(
            f"{package_root}/app.py",
            '"""A loose module at the root package level."""\n\n\n'
            "def run() -> str:\n    return 'ok'\n",
        )
        if tests:
            repo.write(
                "tests/test_app.py",
                f"from {package}.app import run\n\n\ndef test_run():\n    assert run() == 'ok'\n",
            )
        for relative_path, contents in (files or {}).items():
            repo.write(relative_path, contents)
        return repo

    return build


DEFAULT_PYPROJECT = """[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []
{layout_config}"""

SETUPTOOLS_SRC = """
[tool.setuptools.packages.find]
where = ["src"]
"""
