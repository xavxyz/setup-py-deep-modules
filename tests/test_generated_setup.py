"""The same proof the fixture gets, against a repo the skill has just set up.

The fixture proves the rule works in a project written to suit it. What matters
to a user is whether it works in a project that was not: a repo with its own
name, its own layout and no knowledge of any of this, handed to ``configure``
and ``scaffold`` and then subjected to the identical pass/fail/pass cycle.

Step two is the load-bearing one. A config that does not fail on a real
violation is worthless, so these tests are the thing that says the skill's
output is worth shipping.
"""

from __future__ import annotations

from conftest import RepoBuilder, UserRepo, config_untouched

DEEP_IMPORT = "from acme_widgets.billing._internal._totals import total_due  # noqa: F401"


def _set_up(repo: UserRepo) -> UserRepo:
    """Run the two steps that write files, as the skill runs them."""
    configured = repo.configure()
    assert configured.passed, configured.output
    scaffolded = repo.scaffold()
    assert scaffolded.passed, scaffolded.output
    return repo


def test_the_proof_cycle_in_a_src_layout_repo(user_repo: RepoBuilder) -> None:
    repo = _set_up(user_repo("src"))

    assert repo.check().passed

    repo.append("src/acme_widgets/app.py", DEEP_IMPORT)
    violated = repo.check()
    assert not violated.passed
    assert violated.mentions("acme_widgets.billing._internal._totals.total_due")

    repo.remove("src/acme_widgets/app.py", DEEP_IMPORT)
    assert repo.check().passed


def test_the_proof_cycle_in_a_flat_layout_repo(user_repo: RepoBuilder) -> None:
    """A flat-layout repo adopts the rule without restructuring: the source root
    is the repo itself, which is also where its tests already live."""
    repo = _set_up(user_repo("flat"))

    assert repo.check().passed

    repo.append("acme_widgets/app.py", DEEP_IMPORT)
    violated = repo.check()
    assert not violated.passed
    assert violated.mentions("acme_widgets.billing._internal._totals.total_due")

    repo.remove("acme_widgets/app.py", DEEP_IMPORT)
    assert repo.check().passed


def test_a_top_level_test_is_bound_by_the_rule_too(user_repo: RepoBuilder) -> None:
    """Easy to get silently wrong: tach's default ``exclude`` list contains
    ``**/tests``, so a default config would pass this vacuously."""
    repo = _set_up(user_repo("src"))

    repo.append("tests/test_app.py", DEEP_IMPORT)

    result = repo.check()
    assert not result.passed
    assert result.mentions("tests/test_app.py")


def test_the_repos_own_loose_modules_raise_no_complaints(user_repo: RepoBuilder) -> None:
    """Adopting the rule must not open with a list of grievances about code that
    is fine. Loose modules at the root package level are the unconstrained tier."""
    repo = _set_up(
        user_repo(
            "src",
            files={
                "src/acme_widgets/utils.py": "def _shout(text: str) -> str:\n"
                "    return text.upper()\n\n\n"
                "def shout(text: str) -> str:\n    return _shout(text)\n",
            },
        )
    )
    repo.append("src/acme_widgets/app.py", "from acme_widgets.utils import shout  # noqa: F401")

    assert repo.check().passed


def test_growing_the_repo_afterwards_needs_no_edit_to_the_config(user_repo: RepoBuilder) -> None:
    """The property the tool choice rests on, checked against a generated config
    rather than the hand-written fixture one."""
    repo = _set_up(user_repo("src"))

    with config_untouched(repo):
        repo.write(
            "src/acme_widgets/search/__init__.py",
            '"""Added after the config was written."""\n\n'
            "from ._internal._engine import search\n\n"
            '__all__ = ["search"]\n',
        )
        repo.write("src/acme_widgets/search/_internal/__init__.py", '"""Private."""\n')
        repo.write(
            "src/acme_widgets/search/_internal/_engine.py",
            "def search(term: str) -> list[str]:\n    return [term]\n",
        )
        assert repo.check().passed

        repo.append(
            "src/acme_widgets/app.py",
            "from acme_widgets.search._internal._engine import search  # noqa: F401",
        )
        result = repo.check()

        assert not result.passed
        assert result.mentions("acme_widgets.search._internal._engine.search")


def test_an_existing_packages_directory_is_configured_in_place(user_repo: RepoBuilder) -> None:
    repo = _set_up(
        user_repo(
            "src",
            files={
                "src/packages/__init__.py": '"""Existing package tier."""\n',
                "src/packages/orders/__init__.py": '"""Existing package."""\n\n'
                "from ._internal._book import place\n\n"
                '__all__ = ["place"]\n',
                "src/packages/orders/_internal/__init__.py": '"""Private."""\n',
                "src/packages/orders/_internal/_book.py": "def place(item: str) -> str:\n"
                "    return item\n",
            },
        )
    )

    assert repo.exists("src/packages/billing/__init__.py")
    assert not repo.exists("src/acme_widgets/billing")
    assert repo.check().passed

    repo.append(
        "src/acme_widgets/app.py",
        "from packages.orders._internal._book import place  # noqa: F401",
    )
    result = repo.check()
    assert not result.passed
    assert result.mentions("packages.orders._internal._book.place")


def test_cycles_between_packages_are_rejected_in_the_users_repo(user_repo: RepoBuilder) -> None:
    """``tach check`` cannot do this one -- see ``fixture/README.md`` -- so the
    skill copies the script that can."""
    repo = _set_up(user_repo("src"))

    assert repo.check_cycles().passed

    repo.write(
        "src/acme_widgets/notifications/__init__.py",
        "from acme_widgets.billing import total_due  # noqa: F401\n",
    )
    repo.append(
        "src/acme_widgets/billing/_internal/_tax.py",
        "from acme_widgets.notifications import total_due  # noqa: F401",
    )

    result = repo.check_cycles()
    assert not result.passed
    assert result.mentions("acme_widgets.billing")
    assert result.mentions("acme_widgets.notifications")
