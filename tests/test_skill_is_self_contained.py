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
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest
from conftest import SKILL_DIRECTORY, RepoBuilder


@dataclass(frozen=True)
class InstalledSkill:
    """Where an installer left the skill, and the script inside it.

    Both, because the tests need the boundary as well as the entry point, and
    recovering one from the other means writing down an offset between them --
    which is the mistake this whole file exists to catch.
    """

    root: Path
    script: Path


@pytest.fixture
def installed_skill(tmp_path: Path) -> InstalledSkill:
    """The skill copied out on its own, as an installer would leave it."""
    root = tmp_path / "install" / ".agents" / "skills" / "setup-py-deep-modules"
    shutil.copytree(
        SKILL_DIRECTORY,
        root,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return InstalledSkill(root=root, script=root / "scripts" / "setup_deep_modules.py")


def test_detect_runs_from_a_skill_only_install(
    user_repo: RepoBuilder, installed_skill: InstalledSkill
) -> None:
    """The first step of the skill, and the one the bug report died on."""
    repo = user_repo(script=installed_skill.script)

    facts = repo.facts()

    assert facts["root_package"] == "acme_widgets"
    # The pin is read out of the fixture, so it is the first thing to go missing
    # when the fixture is not there.
    assert facts["tach_requirement"].startswith("tach")


def test_every_write_step_runs_from_a_skill_only_install(
    user_repo: RepoBuilder, installed_skill: InstalledSkill
) -> None:
    """Each step renders from a different corner of the skill directory.

    ``configure`` reads the fixture's config and cycle check, ``scaffold`` copies
    its example package, and ``document`` renders the template from ``assets/``.
    A test that stopped at ``detect`` would leave three of them unproven.
    ``find-violation`` reads only the user's repo, and is here because step 5
    cannot run without it.
    """
    repo = user_repo(script=installed_skill.script)

    for step in (
        repo.configure(),
        repo.scaffold(),
        repo.find_violation(),
        repo.document(),
    ):
        assert step.passed, step.output

    assert repo.exists("tach.toml")
    assert repo.exists("scripts/check_cycles.py")
    assert repo.exists("src/acme_widgets/billing/__init__.py")


def test_no_path_the_script_reads_escapes_the_skill_directory(
    installed_skill: InstalledSkill,
) -> None:
    """The property, checked rather than left to hold by luck.

    The two tests above only cover the paths those steps happen to touch. This
    one covers the rest, and is what stops the next file the script needs from
    quietly reintroducing the bug.
    """
    module = _import_installed_script(installed_skill.script)
    skill_root = installed_skill.root

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


def test_the_script_works_out_where_it_lives_exactly_once(
    installed_skill: InstalledSkill,
) -> None:
    """The test above only sees paths resolved at module level.

    A read built inside a function body would slip past it while being the exact
    shape of the original bug, so this pins the other half: there is one
    derivation of the skill's location in the script, and everything hangs off
    it. Adding a second is how this bug would come back.
    """
    source = installed_skill.script.read_text()

    assert source.count("Path(__file__)") == 1, (
        "the script works out where it lives more than once; every path it reads "
        "should hang off the single SKILL_ROOT"
    )


def test_the_documented_command_points_at_the_installed_script(
    installed_skill: InstalledSkill,
) -> None:
    """SKILL.md is the agent's only instruction, so it has to be right too.

    It used to build the path from ``CLAUDE_PLUGIN_ROOT``, which is set only for
    plugin installs and expands to nothing otherwise -- the same bug wearing
    different clothes, and invisible to any test that only drove the script.
    """
    skill_md = (installed_skill.root / "SKILL.md").read_text()

    # Naming the variable is fine -- SKILL.md warns the agent off it. Assigning
    # the script path from it is the defect.
    assignments = [
        line for line in skill_md.splitlines() if line.strip().startswith("SETUP=")
    ]
    assert assignments, "SKILL.md no longer says where the script is"
    for line in assignments:
        assert "CLAUDE_PLUGIN_ROOT" not in line, (
            f"SKILL.md builds the script path from a plugin-only variable: {line}"
        )

    documented = "scripts/setup_deep_modules.py"
    assert all(documented in line for line in assignments)
    assert (installed_skill.root / documented).exists()


def _import_installed_script(script: Path) -> ModuleType:
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
