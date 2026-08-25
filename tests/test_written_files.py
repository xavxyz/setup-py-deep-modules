"""What the skill writes, and -- as often matters more -- what it refuses to write.

The rule these tests circle is that the skill is a guest in someone else's repo.
It may add the boundary and the documentation for it; it may not introduce a
tool the user did not choose, and it may not overwrite work it did not author.
"""

from __future__ import annotations

import shutil

from conftest import RepoBuilder, UserRepo

PRE_COMMIT = """repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
"""

EXISTING_CLAUDE_MD = "# House rules\n\nRun the tests before you claim to be done.\n"


def test_configure_writes_a_config_and_the_cycle_check(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src")

    result = repo.configure()

    assert result.passed
    assert repo.exists("tach.toml")
    assert repo.exists("scripts/check_cycles.py")


def test_the_config_is_rendered_for_this_repo(user_repo: RepoBuilder) -> None:
    """Whether the rule *works* is proven by running it, in test_generated_setup.
    The only thing worth reading out of the file is that the fixture's name did
    not come along with it."""
    repo: UserRepo = user_repo("src")

    repo.configure()

    config = repo.read("tach.toml")
    assert 'path = "acme_widgets.*"' in config
    assert "myproject" not in config


def test_the_layering_stub_survives_into_the_users_config(user_repo: RepoBuilder) -> None:
    """Commented-out config has no behaviour to observe, so its presence is the
    whole of the feature: a user constrains which packages may depend on which
    later, without going and researching how."""
    repo: UserRepo = user_repo("src")

    repo.configure()

    config = repo.read("tach.toml")
    assert "# [[layers]]" in config


def test_configure_refuses_to_overwrite_an_existing_config(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src", files={"tach.toml": "# hand-written\n"})

    result = repo.configure()

    assert not result.passed
    assert repo.read("tach.toml") == "# hand-written\n"
    assert result.mentions("tach.toml")


def test_configure_extends_an_existing_pre_commit_config(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src", files={".pre-commit-config.yaml": PRE_COMMIT})

    repo.configure()

    config = repo.read(".pre-commit-config.yaml")
    assert config.startswith(PRE_COMMIT)
    assert "id: tach" in config
    assert "entry: tach check" in config


def test_the_hook_runs_tach_where_the_package_manager_put_it(
    user_repo: RepoBuilder,
) -> None:
    """`language: system` runs the entry as typed, so a uv project needs the same
    `uv run` prefix here that the proof step uses."""
    repo: UserRepo = user_repo(
        "src", files={".pre-commit-config.yaml": PRE_COMMIT, "uv.lock": "version = 1\n"}
    )

    repo.configure()

    assert "entry: uv run tach check" in repo.read(".pre-commit-config.yaml")


def test_configure_does_not_add_the_hook_twice(user_repo: RepoBuilder) -> None:
    """Re-running the skill must not stack up hooks in a file the user reads."""
    repo: UserRepo = user_repo("src", files={".pre-commit-config.yaml": PRE_COMMIT})

    repo.configure()
    repo.configure("--force")

    assert repo.read(".pre-commit-config.yaml").count("id: tach") == 1


def test_configure_leaves_an_unfamiliar_pre_commit_config_alone(user_repo: RepoBuilder) -> None:
    """No `repos:` list means the file is not shaped the way the append assumes,
    and guessing at someone's working pre-commit setup is how it stops working."""
    odd = "# a config with no repos list yet\n"
    repo: UserRepo = user_repo("src", files={".pre-commit-config.yaml": odd})

    result = repo.configure()

    assert repo.read(".pre-commit-config.yaml") == odd
    assert result.mentions("by hand")


def test_configure_never_introduces_pre_commit(user_repo: RepoBuilder) -> None:
    """A user without pre-commit has not chosen pre-commit."""
    repo: UserRepo = user_repo("src")

    repo.configure()

    assert not repo.exists(".pre-commit-config.yaml")


def test_the_setup_introduces_no_task_runner_or_test_framework(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src")
    before = {path.name for path in repo.root.rglob("*") if path.is_file()}

    repo.configure()
    repo.scaffold()
    repo.document()

    added = {path.name for path in repo.root.rglob("*") if path.is_file()} - before
    for unwanted in ("Makefile", "justfile", "noxfile.py", "tox.ini", "conftest.py"):
        assert unwanted not in added
    assert not (repo.root / ".github").exists()


def test_the_example_package_delegates_to_a_private_module(user_repo: RepoBuilder) -> None:
    """A pass-through example would teach the wrong shape: the point is depth,
    a small surface with the behaviour behind it."""
    repo: UserRepo = user_repo("src")

    repo.configure()
    repo.scaffold()

    interface = repo.read("src/acme_widgets/billing/__init__.py")
    assert "from ._internal" in interface
    assert "__all__" in interface
    assert repo.exists("src/acme_widgets/billing/_internal/_totals.py")


def test_the_example_can_be_deleted_cleanly(user_repo: RepoBuilder) -> None:
    """Nothing else is made to depend on it, so it never becomes dead code the
    user is stuck with."""
    repo: UserRepo = user_repo("src")
    repo.configure()
    repo.scaffold()

    shutil.rmtree(repo.root / "src/acme_widgets/billing")

    assert repo.check().passed


def test_scaffold_refuses_to_overwrite_an_existing_package(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo(
        "src", files={"src/acme_widgets/billing/__init__.py": '"""Mine."""\n'}
    )
    repo.configure()

    result = repo.scaffold()

    assert not result.passed
    assert repo.read("src/acme_widgets/billing/__init__.py") == '"""Mine."""\n'


def test_scaffold_says_the_example_is_a_starter_to_copy_or_delete(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src")
    repo.configure()

    result = repo.scaffold()

    assert result.mentions("delete")


def test_the_convention_doc_lands_next_to_the_code_it_governs(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src")
    repo.configure()

    result = repo.document()

    assert result.passed
    assert repo.exists("src/acme_widgets/README.md")


def test_the_convention_doc_forbids_star_re_exports(user_repo: RepoBuilder) -> None:
    """The one rule tach does not check, so the only place it can be stated is
    the doc -- which makes leaving it out a silent hole."""
    repo: UserRepo = user_repo("src")
    repo.configure()
    repo.document()

    doc = repo.read("src/acme_widgets/README.md")
    assert "import *" in doc
    assert "__all__" in doc
    assert "tach check" in doc
    assert "starting with `_`" in doc


def test_the_convention_doc_is_written_for_this_repo(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src")
    repo.configure()
    repo.document()

    doc = repo.read("src/acme_widgets/README.md")
    assert "acme_widgets" in doc
    assert "myproject" not in doc


def test_a_pointer_is_added_to_an_existing_claude_md(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src", files={"CLAUDE.md": EXISTING_CLAUDE_MD})
    repo.configure()

    repo.document()

    pointer = repo.read("CLAUDE.md")
    assert pointer.startswith(EXISTING_CLAUDE_MD)
    assert "src/acme_widgets/README.md" in pointer
    assert not repo.exists("AGENTS.md")


def test_an_agents_file_is_created_when_the_repo_has_neither(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo("src")
    repo.configure()

    repo.document()

    assert repo.exists("AGENTS.md")
    assert "src/acme_widgets/README.md" in repo.read("AGENTS.md")
    assert not repo.exists("CLAUDE.md")


def test_the_pointer_is_not_added_twice(user_repo: RepoBuilder) -> None:
    """Re-running the skill in a repo it has already touched must not stack up
    duplicate lines in the file the next agent reads."""
    repo: UserRepo = user_repo("src", files={"AGENTS.md": "# Notes\n"})
    repo.configure()

    repo.document()
    repo.document()

    assert repo.read("AGENTS.md").count("src/acme_widgets/README.md") == 1


def test_document_refuses_to_overwrite_an_existing_package_readme(user_repo: RepoBuilder) -> None:
    repo: UserRepo = user_repo(
        "src", files={"src/acme_widgets/README.md": "# Mine\n"}
    )
    repo.configure()

    result = repo.document()

    assert not result.passed
    assert repo.read("src/acme_widgets/README.md") == "# Mine\n"


def test_the_convention_doc_stays_inside_the_distribution_package(
    user_repo: RepoBuilder,
) -> None:
    """Even where packages live elsewhere. The doc answers a question that occurs
    to a reader inside the distribution package, so that is where it waits."""
    repo: UserRepo = user_repo(
        "src",
        files={
            "src/packages/__init__.py": '"""Existing package tier."""\n',
            "src/packages/orders/__init__.py": '"""Existing package."""\n',
        },
    )
    repo.configure()

    repo.document()

    assert repo.exists("src/acme_widgets/README.md")
    assert "src/packages" in repo.read("src/acme_widgets/README.md")


def test_configure_leaves_a_modified_cycle_check_alone(user_repo: RepoBuilder) -> None:
    """Someone who has edited that script has a reason. Overwriting it silently
    would take the reason with it."""
    mine = "# mine, with a project-specific rule in it\n"
    repo: UserRepo = user_repo("src", files={"scripts/check_cycles.py": mine})

    result = repo.configure()

    assert repo.read("scripts/check_cycles.py") == mine
    assert result.mentions("differs")
