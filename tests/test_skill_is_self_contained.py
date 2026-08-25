"""The skill directory, on its own, is the whole skill.

The script derives everything it writes from the fixture, and used to find it by
walking a fixed number of parents up from its own file -- an offset that only
lands on the fixture inside a checkout of this repo, where it sat beside
``skills/``. Installed as a bare skill directory, which is all a skill installer
copies, that offset pointed outside the installed tree at a directory that was
never fetched, and every step died on it (issue #8).

So these tests install the skill the way an installer does: copy the directory,
and nothing else, into a tree with no checkout above it. The layout below is the
one from the bug report, chosen because the old offset lands on its ``.agents``
directory -- close enough to look plausible, empty of everything that matters.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
from conftest import SKILL_DIRECTORY, RepoBuilder, UserRepo


@pytest.fixture
def installed_skill(tmp_path: Path) -> Path:
    """The skill copied out on its own, as an installer would leave it."""
    destination = tmp_path / "install" / ".agents" / "skills" / "setup-py-deep-modules"
    shutil.copytree(
        SKILL_DIRECTORY,
        destination,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return destination / "scripts" / "setup_deep_modules.py"


def test_detect_runs_from_a_skill_only_install(
    user_repo: RepoBuilder, installed_skill: Path
) -> None:
    """The first step of the skill, and the one the bug report died on."""
    repo = user_repo(script=installed_skill)

    facts = repo.facts()

    assert facts["root_package"] == "acme_widgets"
    # The pin is read out of the fixture, so it is the first thing to go missing
    # when the fixture is not there.
    assert facts["tach_requirement"].startswith("tach")


def test_every_write_step_runs_from_a_skill_only_install(
    user_repo: RepoBuilder, installed_skill: Path
) -> None:
    """Each step renders from a different corner of the skill directory.

    ``configure`` reads the fixture's config and cycle check, ``scaffold`` copies
    its example package, and ``document`` renders the template from ``assets/``.
    A test that stopped at ``detect`` would leave three of them unproven.
    """
    repo = user_repo(script=installed_skill)

    for step in (repo.configure(), repo.scaffold(), repo.document()):
        assert step.passed, step.output

    assert repo.exists("tach.toml")
    assert repo.exists("scripts/check_cycles.py")
    assert repo.exists("src/acme_widgets/billing/__init__.py")


def test_no_path_the_script_reads_escapes_the_skill_directory(
    installed_skill: Path,
) -> None:
    """The property, checked rather than left to hold by luck.

    The three tests above only cover the paths those steps happen to touch. This
    one covers the rest, and is what stops the next file the script needs from
    quietly reintroducing the bug.
    """
    module = _load(installed_skill)
    skill_root = installed_skill.parent.parent

    roots = {
        name: value
        for name, value in vars(module).items()
        if isinstance(value, Path)
    }
    assert roots, "the script no longer resolves anything, so this proves nothing"

    escapees = {
        name: str(path)
        for name, path in roots.items()
        if not path.resolve().is_relative_to(skill_root)
    }
    assert not escapees, (
        f"these resolve outside the installed skill directory {skill_root}: {escapees}"
    )


def _load(script: Path):
    """Import the installed copy, without putting it on the import path."""
    name = "installed_skill_script"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The script defines dataclasses, and dataclass resolves annotations through
    # sys.modules, so the module has to be registered before it is executed.
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[name]
    return module
