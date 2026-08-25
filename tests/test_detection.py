"""What the skill has to learn about a repo before it may touch it.

Detection is the one part of the skill with real branching in it -- layout,
package manager, an existing ``packages/`` directory -- so it is a script with
tests rather than prose an agent improvises differently each run. The tests
assert on the facts the later steps consume, not on how they were derived.
"""

from __future__ import annotations

import tomllib

from conftest import FIXTURE_PROJECT, RepoBuilder, UserRepo

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


def test_a_src_layout_repo_is_detected(user_repo: RepoBuilder) -> None:
    facts = user_repo("src").facts()

    assert facts["layout"] == "src"
    assert facts["root_package"] == "acme_widgets"
    assert facts["package_root"] == "src/acme_widgets"
    assert facts["source_roots"] == ["src", "tests"]


def test_a_flat_layout_repo_is_detected(user_repo: RepoBuilder) -> None:
    """The flat layout needs no restructuring to adopt the rule: its single
    source root is the repo itself, which already holds the tests."""
    facts = user_repo("flat").facts()

    assert facts["layout"] == "flat"
    assert facts["root_package"] == "acme_widgets"
    assert facts["package_root"] == "acme_widgets"
    assert facts["source_roots"] == ["."]


def test_a_hyphenated_project_name_maps_to_its_module_name(user_repo: RepoBuilder) -> None:
    """``acme-widgets`` on PyPI is ``acme_widgets`` to an importer, and it is the
    importer's spelling every later step needs."""
    facts = user_repo("src", name="acme-widgets", package="acme_widgets").facts()

    assert facts["root_package"] == "acme_widgets"


def test_a_source_root_declared_only_by_the_build_backend_is_found(user_repo: RepoBuilder) -> None:
    """Poetry's ``packages = [{include = ..., from = "src"}]`` is the only
    statement of the layout in such a repo -- there is no setuptools table."""
    facts = user_repo("src", pyproject=POETRY_PYPROJECT).facts()

    assert facts["layout"] == "src"
    assert facts["root_package"] == "acme_widgets"


def test_a_hatch_project_is_detected(user_repo: RepoBuilder) -> None:
    facts = user_repo("src", pyproject=HATCH_PYPROJECT).facts()

    assert facts["layout"] == "src"
    assert facts["package_root"] == "src/acme_widgets"


def test_the_tests_directory_is_only_a_source_root_when_it_exists(user_repo: RepoBuilder) -> None:
    """Naming a directory that is not there makes tach fail outright, so the
    source roots have to describe the repo rather than the convention."""
    facts = user_repo("src", tests=False).facts()

    assert facts["source_roots"] == ["src"]


def test_the_deep_module_tier_is_the_root_packages_subpackages(user_repo: RepoBuilder) -> None:
    facts = user_repo("src").facts()

    assert facts["module_glob"] == "acme_widgets.*"
    assert facts["package_tier"] == "src/acme_widgets"


def test_an_existing_packages_directory_is_honoured(user_repo: RepoBuilder) -> None:
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


def test_a_packages_directory_inside_the_root_package_is_honoured(user_repo: RepoBuilder) -> None:
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


def test_uv_is_detected_from_its_lockfile(user_repo: RepoBuilder) -> None:
    repo = user_repo("src", files={"uv.lock": "version = 1\n"})

    facts = repo.facts()

    assert facts["package_manager"] == "uv"
    assert facts["install_command"] == 'uv add --dev "tach~=0.35.0"'
    assert facts["records_dependency"] is True


def test_poetry_is_detected_from_its_table(user_repo: RepoBuilder) -> None:
    facts = user_repo("src", pyproject=POETRY_PYPROJECT).facts()

    assert facts["package_manager"] == "poetry"
    assert facts["install_command"] == 'poetry add --group dev "tach~=0.35.0"'


def test_pdm_is_detected_from_its_lockfile(user_repo: RepoBuilder) -> None:
    repo = user_repo("src", files={"pdm.lock": "[metadata]\n"})

    facts = repo.facts()

    assert facts["package_manager"] == "pdm"
    assert facts["install_command"] == 'pdm add --dev "tach~=0.35.0"'


def test_pip_is_the_fallback_and_records_nothing_by_itself(user_repo: RepoBuilder) -> None:
    """``pip install`` leaves no pin behind, so the skill is told it must write
    the dependency down itself -- a pin nobody records is not a pin."""
    facts = user_repo("src").facts()

    assert facts["package_manager"] == "pip"
    assert facts["records_dependency"] is False


def test_the_pin_is_compatible_minor_and_read_from_the_proven_fixture(user_repo: RepoBuilder) -> None:
    """One place holds the version this repo has actually proven. Detection
    reads it there rather than repeating it, so a bump cannot half-land."""
    facts = user_repo("src").facts()

    assert facts["tach_requirement"].startswith("tach~=0.")
    assert facts["tach_requirement"] == _fixture_pin()


def test_a_repo_with_no_pyproject_is_refused(user_repo: RepoBuilder) -> None:
    """Every later step reads the layout from ``pyproject.toml``. Guessing
    without one would mean configuring the wrong thing silently."""
    repo = user_repo("src")
    (repo.root / "pyproject.toml").unlink()

    result = repo.detect()

    assert not result.passed
    assert result.mentions("pyproject.toml")


def test_an_ambiguous_root_package_is_refused(user_repo: RepoBuilder) -> None:
    """Several distributions in one repo is out of scope, and picking one at
    random would configure the rule for half the codebase."""
    repo = user_repo("src", files={"src/acme_other/__init__.py": '"""Another."""\n'})
    repo.write("pyproject.toml", '[project]\nname = "unrelated-name"\nversion = "0.1.0"\n')

    result = repo.detect()

    assert not result.passed
    assert result.mentions("acme_widgets")
    assert result.mentions("acme_other")


def _fixture_pin() -> str:
    """The pin as the fixture states it, read independently of the script."""
    with (FIXTURE_PROJECT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    pins = [
        requirement
        for requirement in config["project"]["optional-dependencies"]["dev"]
        if requirement.startswith("tach")
    ]
    assert len(pins) == 1, "the fixture no longer pins exactly one tach version"
    return pins[0]


def test_detection_leaves_the_repo_alone(user_repo: RepoBuilder) -> None:
    """Detection is a read. Nothing is written before the user has been told
    what was found."""
    repo: UserRepo = user_repo("src")
    before = sorted(path.name for path in repo.root.rglob("*"))

    repo.facts()

    assert sorted(path.name for path in repo.root.rglob("*")) == before


def test_a_packages_tier_is_not_mistaken_for_the_distribution_package(
    user_repo: RepoBuilder,
) -> None:
    """The two features collide if ``packages/`` is left in the running as a
    root package: a repo with both stops dead as "ambiguous", when in fact it is
    exactly the repo the packages-tier support exists for."""
    repo = user_repo(
        "src",
        name="acme-suite",
        package="acme_core",
        files={
            "src/packages/__init__.py": '"""Existing package tier."""\n',
            "src/packages/billing/__init__.py": '"""Existing package."""\n',
        },
    )

    facts = repo.facts()

    assert facts["root_package"] == "acme_core"
    assert facts["package_tier"] == "src/packages"


def test_the_check_commands_reach_the_environment_tach_was_installed_into(
    user_repo: RepoBuilder,
) -> None:
    """``uv add`` puts tach in the project's environment, not on PATH. A bare
    ``tach check`` would then fail for a reason that looks exactly like the
    violation the proof step is waiting to see."""
    facts = user_repo("src", files={"uv.lock": "version = 1\n"}).facts()

    assert facts["check_command"] == "uv run tach check"
    assert facts["cycle_command"] == "uv run python scripts/check_cycles.py"


def test_pip_repos_get_plain_commands(user_repo: RepoBuilder) -> None:
    facts = user_repo("src").facts()

    assert facts["check_command"] == "tach check"


def test_the_pip_case_is_told_where_to_write_the_pin(user_repo: RepoBuilder) -> None:
    facts = user_repo("src").facts()

    assert facts["dependency_file"] == "pyproject.toml"
    assert facts["dependency_target"] == "[project.optional-dependencies] dev"


def test_a_requirements_file_is_preferred_when_the_repo_keeps_one(
    user_repo: RepoBuilder,
) -> None:
    facts = user_repo("src", files={"requirements-dev.txt": "pytest\n"}).facts()

    assert facts["dependency_file"] == "requirements-dev.txt"
    assert facts["dependency_target"] == "one requirement per line"
