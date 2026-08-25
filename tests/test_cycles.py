"""Cycles between packages.

``forbid_circular_dependencies`` turned out to check the dependency graph
*declared* in ``tach.toml`` via ``depends_on``. The generic config declares
none -- that is the whole point of it -- so on its own the setting never sees a
cycle the real imports form. ``scripts/check_cycles.py`` closes the gap: it
reads the real graph from ``tach map``, collapses it to the package tier, and
fails on any cycle. It needs no per-package configuration either, so the
no-config-edits property survives.

The tach limitation is pinned by a test of its own, so the scheduled CI run
tells us if a release ever removes the need for the extra command.
"""

from __future__ import annotations

from conftest import Project, config_untouched

CYCLIC_IMPORT = "from myproject.notifications import invoice_ready  # noqa: F401"


def test_the_clean_fixture_has_no_cycles(project: Project) -> None:
    assert project.check_cycles().passed


def test_a_cycle_between_two_packages_is_rejected(project: Project) -> None:
    with config_untouched(project):
        project.append("src/myproject/billing/_internal/_tax.py", CYCLIC_IMPORT)

        result = project.check_cycles()

        assert not result.passed
        assert result.mentions("Circular dependency")
        assert result.mentions("myproject.billing")
        assert result.mentions("myproject.notifications")


def test_an_indirect_cycle_through_three_packages_is_rejected(project: Project) -> None:
    """billing -> audit -> notifications -> billing.

    No two of these import each other directly. Catching only the mutual case
    would miss the shape that actually shows up in a codebase that has drifted.
    """
    with config_untouched(project):
        project.write(
            "src/myproject/audit/__init__.py",
            '"""Audit trail."""\n\nfrom ._internal._log import record\n\n__all__ = ["record"]\n',
        )
        project.write("src/myproject/audit/_internal/__init__.py", '"""Private."""\n')
        project.write(
            "src/myproject/audit/_internal/_log.py",
            "from myproject.notifications import invoice_ready  # noqa: F401\n\n\n"
            "def record(event: str) -> str:\n    return event\n",
        )
        # notifications -> billing already exists in the clean fixture; this
        # closes the loop with billing -> audit.
        project.append(
            "src/myproject/billing/_internal/_tax.py",
            "from myproject.audit import record  # noqa: F401",
        )

        result = project.check_cycles()

        assert not result.passed
        assert result.mentions("myproject.audit")
        assert result.mentions("myproject.billing")
        assert result.mentions("myproject.notifications")


def test_a_package_depending_on_another_is_not_a_cycle(project: Project) -> None:
    """notifications -> billing is a plain dependency in the clean fixture, and
    must not be mistaken for a cycle."""
    result = project.check_cycles()

    assert result.passed
    assert not result.mentions("Circular dependency")


def test_loose_modules_using_two_packages_are_not_a_cycle(project: Project) -> None:
    """``app.py`` imports both packages, but belongs to neither, so it cannot be
    a node in a cycle between them."""
    project.append(
        "src/myproject/app.py",
        "from myproject.billing.quote import estimate  # noqa: F401",
    )

    assert project.check_cycles().passed


def test_the_globbed_config_alone_does_not_see_a_real_cycle(project: Project) -> None:
    """Pins the tach behaviour that makes ``check_cycles.py`` necessary.

    If this test starts failing, tach has begun checking cycles against real
    imports under a globbed module, and the script can go away.
    """
    project.append("src/myproject/billing/_internal/_tax.py", CYCLIC_IMPORT)

    assert project.check().passed
