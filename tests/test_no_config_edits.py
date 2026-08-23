"""The property the whole tool choice rests on: growing the project never means
editing the linter. These tests add code the config has never heard of, and
assert the rule bites anyway -- with ``tach.toml`` left untouched."""

from __future__ import annotations

from conftest import Project, config_untouched

NEW_PACKAGE_INIT = '''"""A package added after the config was written."""

from ._internal._engine import search

__all__ = ["search"]
'''

NEW_PACKAGE_ENGINE = '''"""Private to :mod:`myproject.search`."""


def search(term: str) -> list[str]:
    return [term]
'''


def test_a_new_package_is_enforced_without_touching_the_config(project: Project) -> None:
    with config_untouched(project):
        project.write("src/myproject/search/__init__.py", NEW_PACKAGE_INIT)
        project.write("src/myproject/search/_internal/__init__.py", '"""Private."""\n')
        project.write("src/myproject/search/_internal/_engine.py", NEW_PACKAGE_ENGINE)
        assert project.check().passed

        project.append(
            "src/myproject/app.py",
            "from myproject.search._internal._engine import search  # noqa: F401",
        )
        result = project.check()

        assert not result.passed
        assert result.mentions("myproject.search._internal._engine.search")


def test_a_new_private_folder_is_enforced_without_touching_the_config(project: Project) -> None:
    with config_untouched(project):
        project.write("src/myproject/billing/_rounding/__init__.py", '"""Private."""\n')
        project.write(
            "src/myproject/billing/_rounding/_banker.py",
            "def round_half_even(cents: int) -> int:\n    return cents\n",
        )
        assert project.check().passed

        project.append(
            "src/myproject/app.py",
            "from myproject.billing._rounding._banker import round_half_even  # noqa: F401",
        )
        result = project.check()

        assert not result.passed
        assert result.mentions("myproject.billing._rounding._banker.round_half_even")


def test_loose_root_modules_need_no_interface_of_their_own(project: Project) -> None:
    """Application code at the root package level is the unconstrained tier:
    adopting the rule does not open with a list of complaints about code that is
    fine."""
    with config_untouched(project):
        project.write(
            "src/myproject/utils.py",
            '"""A loose module with no interface, no __all__ and a private helper."""\n\n\n'
            "def _shout(text: str) -> str:\n    return text.upper()\n\n\n"
            "def shout(text: str) -> str:\n    return _shout(text)\n",
        )
        project.append("src/myproject/app.py", "from myproject.utils import shout  # noqa: F401")

        assert project.check().passed
