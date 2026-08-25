"""What the skill has to learn about a repo before it may touch it.

Detection is the one part of the skill with real branching in it -- layout,
package manager, an existing ``packages/`` directory -- so it is a script with
tests rather than prose an agent improvises differently each run. The tests
assert on the facts the later steps consume, not on how they were derived.
"""

from __future__ import annotations

from conftest import UserRepo

POETRY_PYPROJECT = """[tool.poetry]
name = "acme-widgets"
version = "0.1.0"
packages = [{ include = "acme_widgets", from = "src" }]

[tool.poetry.dependencies]
python = "^3.10"
"""

HATCH_PYPROJECT = """[project]
name = "acme-widgets"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
packages = ["src/acme_widgets"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""


def test_a_src_layout_repo_is_detected(user_repo) -> None:
    facts = user_repo("src").facts()

    assert facts["layout"] == "src"
    assert facts["root_package"] == "acme_widgets"
    assert facts["package_root"] == "src/acme_widgets"
    assert facts["source_roots"] == ["src", "tests"]


def test_a_flat_layout_repo_is_detected(user_repo) -> None:
    """The flat layout needs no restructuring to adopt the rule: its single
    source root is the repo itself, which already holds the tests."""
    facts = user_repo("flat").facts()

    assert facts["layout"] == "flat"
    assert facts["root_package"] == "acme_widgets"
    assert facts["package_root"] == "acme_widgets"
    assert facts["source_roots"] == ["."]


def test_a_hyphenated_project_name_maps_to_its_module_name(user_repo) -> None:
    """``acme-widgets`` on PyPI is ``acme_widgets`` to an importer, and it is the
    importer's spelling every later step needs."""
    facts = user_repo("src", name="acme-widgets", package="acme_widgets").facts()

    assert facts["root_package"] == "acme_widgets"


def test_a_source_root_declared_only_by_the_build_backend_is_found(user_repo) -> None:
    """Poetry's ``packages = [{include = ..., from = "src"}]`` is the only
    statement of the layout in such a repo -- there is no setuptools table."""
    facts = user_repo("src", pyproject=POETRY_PYPROJECT).facts()

    assert facts["layout"] == "src"
    assert facts["root_package"] == "acme_widgets"


def test_a_hatch_project_is_detected(user_repo) -> None:
    facts = user_repo("src", pyproject=HATCH_PYPROJECT).facts()

    assert facts["layout"] == "src"
    assert facts["package_root"] == "src/acme_widgets"


def test_the_tests_directory_is_only_a_source_root_when_it_exists(user_repo) -> None:
    """Naming a directory that is not there makes tach fail outright, so the
    source roots have to describe the repo rather than the convention."""
    facts = user_repo("src", tests=False).facts()

    assert facts["source_roots"] == ["src"]


def test_the_deep_module_tier_is_the_root_packages_subpackages(user_repo) -> None:
    facts = user_repo("src").facts()

    assert facts["module_glob"] == "acme_widgets.*"
    assert facts["package_tier"] == "src/acme_widgets"


def test_an_existing_packages_directory_is_honoured(user_repo) -> None:
    """A repo that already keeps its packages in ``src/packages/`` has a
    convention of its own. The rule adopts it rather than competing with it."""
    repo = user_repo(
        "src",
        files={
            "src/packages/__init__.py": '"""Existing package tier."""\n',
            "src/packages/billing/__init__.py": '"""Existing package."""\n',
        },
    )

    facts = repo.facts()

    assert facts["module_glob"] == "packages.*"
    assert facts["package_tier"] == "src/packages"


def test_a_packages_directory_inside_the_root_package_is_honoured(user_repo) -> None:
    repo = user_repo(
        "src",
        files={
            "src/acme_widgets/packages/__init__.py": '"""Existing package tier."""\n',
            "src/acme_widgets/packages/billing/__init__.py": '"""Existing package."""\n',
        },
    )

    facts = repo.facts()

    assert facts["module_glob"] == "acme_widgets.packages.*"
    assert facts["package_tier"] == "src/acme_widgets/packages"


def test_uv_is_detected_from_its_lockfile(user_repo) -> None:
    repo = user_repo("src", files={"uv.lock": "version = 1\n"})

    facts = repo.facts()

    assert facts["package_manager"] == "uv"
    assert facts["install_command"] == 'uv add --dev "tach~=0.35.0"'
    assert facts["records_dependency"] is True


def test_poetry_is_detected_from_its_table(user_repo) -> None:
    facts = user_repo("src", pyproject=POETRY_PYPROJECT).facts()

    assert facts["package_manager"] == "poetry"
    assert facts["install_command"] == 'poetry add --group dev "tach~=0.35.0"'


def test_pdm_is_detected_from_its_lockfile(user_repo) -> None:
    repo = user_repo("src", files={"pdm.lock": "[metadata]\n"})

    facts = repo.facts()

    assert facts["package_manager"] == "pdm"
    assert facts["install_command"] == 'pdm add --dev "tach~=0.35.0"'


def test_pip_is_the_fallback_and_records_nothing_by_itself(user_repo) -> None:
    """``pip install`` leaves no pin behind, so the skill is told it must write
    the dependency down itself -- a pin nobody records is not a pin."""
    facts = user_repo("src").facts()

    assert facts["package_manager"] == "pip"
    assert facts["records_dependency"] is False


def test_the_pin_is_compatible_minor_and_read_from_the_proven_fixture(user_repo) -> None:
    """One place holds the version this repo has actually proven. Detection
    reads it there rather than repeating it, so a bump cannot half-land."""
    facts = user_repo("src").facts()

    assert facts["tach_requirement"].startswith("tach~=0.")
    assert facts["tach_requirement"] == _fixture_pin()


def test_a_repo_with_no_pyproject_is_refused(user_repo) -> None:
    """Every later step reads the layout from ``pyproject.toml``. Guessing
    without one would mean configuring the wrong thing silently."""
    repo = user_repo("src")
    (repo.root / "pyproject.toml").unlink()

    result = repo.detect()

    assert not result.passed
    assert result.mentions("pyproject.toml")


def test_an_ambiguous_root_package_is_refused(user_repo) -> None:
    """Several distributions in one repo is out of scope, and picking one at
    random would configure the rule for half the codebase."""
    repo = user_repo("src", files={"src/acme_other/__init__.py": '"""Another."""\n'})
    repo.write("pyproject.toml", '[project]\nname = "unrelated-name"\nversion = "0.1.0"\n')

    result = repo.detect()

    assert not result.passed
    assert result.mentions("acme_widgets")
    assert result.mentions("acme_other")


def _fixture_pin() -> str:
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / "fixture" / "pyproject.toml").read_text()
    for line in text.splitlines():
        stripped = line.strip().strip(",").strip('"')
        if stripped.startswith("tach~="):
            return stripped
    raise AssertionError("the fixture no longer pins tach")


def test_detection_leaves_the_repo_alone(user_repo) -> None:
    """Detection is a read. Nothing is written before the user has been told
    what was found."""
    repo: UserRepo = user_repo("src")
    before = sorted(path.name for path in repo.root.rglob("*"))

    repo.facts()

    assert sorted(path.name for path in repo.root.rglob("*")) == before
