"""What the skill writes, and -- as often matters more -- what it refuses to write.

The rule these tests circle is that the skill is a guest in someone else's repo.
It may add the boundary and the documentation for it; it may not introduce a
tool the user did not choose, and it may not overwrite work it did not author.
"""

from __future__ import annotations

from conftest import UserRepo

PRE_COMMIT = """repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
"""

EXISTING_CLAUDE_MD = "# House rules\n\nRun the tests before you claim to be done.\n"


def test_configure_writes_a_config_and_the_cycle_check(user_repo) -> None:
    repo: UserRepo = user_repo("src")

    result = repo.configure()

    assert result.passed
    assert repo.exists("tach.toml")
    assert repo.exists("scripts/check_cycles.py")


def test_the_config_names_the_repos_own_package_and_roots(user_repo) -> None:
    """The one thing worth reading out of the generated config: that it was
    rendered for *this* repo. Whether the rule works is proven by running it."""
    repo: UserRepo = user_repo("src")

    repo.configure()

    config = repo.read("tach.toml")
    assert 'path = "acme_widgets.*"' in config
    assert 'source_roots = ["src", "tests"]' in config
    assert "myproject" not in config


def test_the_layering_stub_survives_into_the_users_config(user_repo) -> None:
    """Layering ships commented out, so a user can constrain which packages may
    depend on which later without going and researching how."""
    repo: UserRepo = user_repo("src")

    repo.configure()

    config = repo.read("tach.toml")
    assert "# [[layers]]" in config


def test_configure_refuses_to_overwrite_an_existing_config(user_repo) -> None:
    repo: UserRepo = user_repo("src", files={"tach.toml": "# hand-written\n"})

    result = repo.configure()

    assert not result.passed
    assert repo.read("tach.toml") == "# hand-written\n"
    assert result.mentions("tach.toml")


def test_configure_prints_the_pre_commit_hook_when_the_repo_has_pre_commit(user_repo) -> None:
    repo: UserRepo = user_repo("src", files={".pre-commit-config.yaml": PRE_COMMIT})

    result = repo.configure()

    assert result.mentions("tach check")
    assert result.mentions(".pre-commit-config.yaml")
    # The edit itself is the agent's, because the shape of an existing file is a
    # judgement call; what the script guarantees is that it is never a rewrite.
    assert repo.read(".pre-commit-config.yaml") == PRE_COMMIT


def test_configure_never_introduces_pre_commit(user_repo) -> None:
    """A user without pre-commit has not chosen pre-commit."""
    repo: UserRepo = user_repo("src")

    repo.configure()

    assert not repo.exists(".pre-commit-config.yaml")


def test_the_setup_introduces_no_task_runner_or_test_framework(user_repo) -> None:
    repo: UserRepo = user_repo("src")
    before = {path.name for path in repo.root.rglob("*") if path.is_file()}

    repo.configure()
    repo.scaffold()
    repo.document()

    added = {path.name for path in repo.root.rglob("*") if path.is_file()} - before
    for unwanted in ("Makefile", "justfile", "noxfile.py", "tox.ini", "conftest.py"):
        assert unwanted not in added
    assert not (repo.root / ".github").exists()


def test_the_example_package_delegates_to_a_private_module(user_repo) -> None:
    """A pass-through example would teach the wrong shape: the point is depth,
    a small surface with the behaviour behind it."""
    repo: UserRepo = user_repo("src")

    repo.configure()
    repo.scaffold()

    interface = repo.read("src/acme_widgets/billing/__init__.py")
    assert "from ._internal" in interface
    assert "__all__" in interface
    assert repo.exists("src/acme_widgets/billing/_internal/_totals.py")


def test_the_example_can_be_deleted_cleanly(user_repo) -> None:
    """Nothing else is made to depend on it, so it never becomes dead code the
    user is stuck with."""
    import shutil

    repo: UserRepo = user_repo("src")
    repo.configure()
    repo.scaffold()

    shutil.rmtree(repo.root / "src/acme_widgets/billing")

    assert repo.check().passed


def test_scaffold_refuses_to_overwrite_an_existing_package(user_repo) -> None:
    repo: UserRepo = user_repo(
        "src", files={"src/acme_widgets/billing/__init__.py": '"""Mine."""\n'}
    )
    repo.configure()

    result = repo.scaffold()

    assert not result.passed
    assert repo.read("src/acme_widgets/billing/__init__.py") == '"""Mine."""\n'


def test_scaffold_says_the_example_is_a_starter_to_copy_or_delete(user_repo) -> None:
    repo: UserRepo = user_repo("src")
    repo.configure()

    result = repo.scaffold()

    assert result.mentions("delete")


def test_the_convention_doc_lands_next_to_the_code_it_governs(user_repo) -> None:
    repo: UserRepo = user_repo("src")
    repo.configure()

    result = repo.document()

    assert result.passed
    assert repo.exists("src/acme_widgets/README.md")


def test_the_convention_doc_forbids_star_re_exports(user_repo) -> None:
    """The one rule tach does not check, so the only place it can be stated is
    the doc -- which makes leaving it out a silent hole."""
    repo: UserRepo = user_repo("src")
    repo.configure()
    repo.document()

    doc = repo.read("src/acme_widgets/README.md")
    assert "import *" in doc
    assert "__all__" in doc
    assert "tach check" in doc
    assert "_" in doc


def test_the_convention_doc_is_written_for_this_repo(user_repo) -> None:
    repo: UserRepo = user_repo("src")
    repo.configure()
    repo.document()

    doc = repo.read("src/acme_widgets/README.md")
    assert "acme_widgets" in doc
    assert "myproject" not in doc


def test_a_pointer_is_added_to_an_existing_claude_md(user_repo) -> None:
    repo: UserRepo = user_repo("src", files={"CLAUDE.md": EXISTING_CLAUDE_MD})
    repo.configure()

    repo.document()

    pointer = repo.read("CLAUDE.md")
    assert pointer.startswith(EXISTING_CLAUDE_MD)
    assert "src/acme_widgets/README.md" in pointer
    assert not repo.exists("AGENTS.md")


def test_an_agents_file_is_created_when_the_repo_has_neither(user_repo) -> None:
    repo: UserRepo = user_repo("src")
    repo.configure()

    repo.document()

    assert repo.exists("AGENTS.md")
    assert "src/acme_widgets/README.md" in repo.read("AGENTS.md")
    assert not repo.exists("CLAUDE.md")


def test_the_pointer_is_not_added_twice(user_repo) -> None:
    """Re-running the skill in a repo it has already touched must not stack up
    duplicate lines in the file the next agent reads."""
    repo: UserRepo = user_repo("src", files={"AGENTS.md": "# Notes\n"})
    repo.configure()

    repo.document()
    repo.document()

    assert repo.read("AGENTS.md").count("src/acme_widgets/README.md") == 1


def test_document_refuses_to_overwrite_an_existing_package_readme(user_repo) -> None:
    repo: UserRepo = user_repo(
        "src", files={"src/acme_widgets/README.md": "# Mine\n"}
    )
    repo.configure()

    result = repo.document()

    assert not result.passed
    assert repo.read("src/acme_widgets/README.md") == "# Mine\n"
