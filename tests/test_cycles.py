"""Cycles between packages.

``forbid_circular_dependencies`` turned out to check the dependency graph
*declared* in ``tach.toml``, not the one the imports actually form. Under the
generic globbed ``[[modules]]`` block nothing is declared, so on its own the
setting never fires. Materialising the graph first -- expanding the glob and
running ``tach sync`` against a scratch copy -- is what makes it fire, and needs
nothing from the user beyond the directory listing.

The limitation is pinned by a test of its own, so the scheduled CI run tells us
if a future tach release removes the need for the extra step.
"""

from __future__ import annotations

import re

from conftest import Project

GLOBBED_MODULE_BLOCK = '[[modules]]\npath = "myproject.*"\n'

CYCLIC_IMPORT = "from myproject.notifications import invoice_ready  # noqa: F401"


def _package_names(project: Project) -> list[str]:
    """The immediate subpackages of the root package -- the deep-module tier."""
    root = project.root / "src" / "myproject"
    return sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and not child.name.startswith("_") and (child / "__init__.py").exists()
    )


def _materialise_dependency_graph(project: Project) -> None:
    """Expand the globbed module into one block per package, then let tach sync
    fill in the dependencies it can see."""
    config = project.read("tach.toml")
    assert GLOBBED_MODULE_BLOCK in config, (
        "tach.toml no longer contains the globbed module block this expansion "
        "rewrites; update GLOBBED_MODULE_BLOCK to match."
    )
    expanded = "\n".join(
        f'[[modules]]\npath = "myproject.{name}"\n' for name in _package_names(project)
    )
    project.write("tach.toml", config.replace(GLOBBED_MODULE_BLOCK, expanded))
    assert project.sync().passed


def test_a_cycle_between_two_packages_fails_the_check(project: Project) -> None:
    project.append("src/myproject/billing/_internal/_tax.py", CYCLIC_IMPORT)
    _materialise_dependency_graph(project)

    result = project.check()

    assert not result.passed
    assert re.search(r"[Cc]ircular dependency", result.output)
    assert result.mentions("myproject.billing")
    assert result.mentions("myproject.notifications")


def test_the_acyclic_fixture_still_passes_once_the_graph_is_materialised(project: Project) -> None:
    _materialise_dependency_graph(project)

    assert project.check().passed


def test_the_globbed_config_alone_does_not_see_a_real_cycle(project: Project) -> None:
    """Pins the tach behaviour that forces the extra step above.

    If this test starts failing, tach has begun checking cycles against real
    imports and ``_materialise_dependency_graph`` can go away.
    """
    project.append("src/myproject/billing/_internal/_tax.py", CYCLIC_IMPORT)

    assert project.check().passed
