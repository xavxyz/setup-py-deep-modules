"""Proof that the shipped ``tach.toml`` enforces "private means a name starting
with an underscore", generically, on a project it has never seen configured."""

from __future__ import annotations

from conftest import Project

DEEP_IMPORT = "from myproject.billing._internal._totals import total_due as _raw  # noqa: F401"


def test_the_proof_cycle(project: Project) -> None:
    """Pass, fail, pass -- the same three steps the skill runs in a user's repo.

    Step two is the load-bearing one: a config that does not fail on a real
    violation is worthless, so observing the failure is the completion criterion.
    """
    assert project.check().passed

    project.append("src/myproject/app.py", DEEP_IMPORT)
    violated = project.check()
    assert not violated.passed
    assert violated.mentions("myproject.billing._internal._totals.total_due")
    assert violated.mentions("src/myproject/app.py")

    project.remove("src/myproject/app.py", DEEP_IMPORT)
    assert project.check().passed


def test_a_private_subpackage_is_not_reachable_by_its_own_init(project: Project) -> None:
    """The leak a literal port of the TypeScript depth rule would have left open."""
    project.append("src/myproject/app.py", "from myproject.billing import _internal  # noqa: F401")

    result = project.check()
    assert not result.passed
    assert result.mentions("myproject.billing._internal")


def test_the_public_surface_is_reachable_from_outside(project: Project) -> None:
    """Named re-exports through ``__init__.py`` are what a consumer may use."""
    project.append(
        "src/myproject/app.py",
        "from myproject.billing import total_due as _also_fine  # noqa: F401",
    )

    assert project.check().passed


def test_a_further_public_entry_point_is_reachable_from_outside(project: Project) -> None:
    """``__init__.py`` is not the only permitted entry point: any module whose
    name does not start with an underscore is public too."""
    project.append(
        "src/myproject/app.py",
        "from myproject.billing.quote import estimate  # noqa: F401",
    )

    assert project.check().passed


def test_a_public_module_may_still_use_its_own_packages_internals(project: Project) -> None:
    """The rule governs crossing a package boundary, not working inside one.

    ``billing/quote.py`` imports from ``billing/_internal/`` in the clean
    fixture; if that were forbidden, packages could have no implementation.
    """
    assert "from ._internal" in project.read("src/myproject/billing/quote.py")
    assert project.check().passed


def test_a_top_level_test_may_use_a_package_through_its_interface(project: Project) -> None:
    """Tests live at the repo root and are bound by the same rule as any consumer.

    This one is easy to get silently wrong: tach's default ``exclude`` list
    contains ``**/tests``, so an unconfigured project would pass this test
    vacuously, having never looked at the directory at all.
    """
    project.write(
        "tests/test_added_by_the_proof.py",
        "from myproject.billing import Invoice, total_due\n\n\n"
        "def test_uses_the_public_surface():\n"
        "    assert total_due(Invoice(jurisdiction='ZZ', items=())) == 0\n",
    )

    assert project.check().passed
    assert project.run_test_suite().passed


def test_a_top_level_test_may_not_reach_into_a_package(project: Project) -> None:
    project.append(
        "tests/test_billing.py",
        "from myproject.billing._internal._tax import rate_for  # noqa: F401",
    )

    result = project.check()
    assert not result.passed
    assert result.mentions("myproject.billing._internal._tax.rate_for")
    assert result.mentions("tests/test_billing.py")


def test_the_fixture_test_suite_passes(project: Project) -> None:
    """A passing suite written against the interfaces is evidence they are usable."""
    assert project.run_test_suite().passed
