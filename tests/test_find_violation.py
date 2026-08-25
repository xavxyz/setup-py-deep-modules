"""The proof cycle run against a private name the repo already has.

Step 5 is the load-bearing step: a ``tach.toml`` that does not go red on a real
violation is worth nothing. ``find-violation`` is what lets that step run
without depositing an example package first -- and a boundary the project
already has is the stronger proof, since it is one the skill did not create and
therefore does not know to be well-formed.
"""

from __future__ import annotations

from conftest import RepoBuilder

#: A package with a private helper behind a public function, which is the shape
#: any real repo already has somewhere.
PACKAGE_WITH_A_PRIVATE_FUNCTION = {
    "src/acme_widgets/services/__init__.py": (
        '"""Services."""\n\nfrom .export_csv import write_csv\n\n__all__ = ["write_csv"]\n'
    ),
    "src/acme_widgets/services/export_csv.py": (
        '"""Export rows as CSV."""\n\n\n'
        "def _safe_filename(name: str) -> str:\n"
        '    return name.replace("/", "_")\n\n\n'
        "def write_csv(name: str) -> str:\n"
        "    return _safe_filename(name)\n"
    ),
}


def test_the_proof_cycle_against_an_existing_private_name(user_repo: RepoBuilder) -> None:
    """The whole of step 5, with no scaffold anywhere in it."""
    repo = user_repo("src", files=PACKAGE_WITH_A_PRIVATE_FUNCTION)
    configured = repo.configure()
    assert configured.passed, configured.output

    violation = repo.violation()
    assert violation["found"], violation

    assert repo.check().passed

    repo.append(violation["target_file"], violation["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output
    assert violated.mentions(violation["expected_mention"]), violated.output

    repo.remove(violation["target_file"], violation["import_line"])
    assert repo.check().passed


#: The shape the convention doc teaches: implementation behind ``_internal/``.
PACKAGE_WITH_A_PRIVATE_MODULE = {
    "src/acme_widgets/pricing/__init__.py": (
        '"""Pricing."""\n\nfrom ._internal._totals import total_due\n\n'
        '__all__ = ["total_due"]\n'
    ),
    "src/acme_widgets/pricing/_internal/__init__.py": '"""Implementation."""\n',
    "src/acme_widgets/pricing/_internal/_totals.py": (
        '"""Totals."""\n\n\ndef total_due(cents: int) -> int:\n    return cents\n'
    ),
}


def test_a_private_module_is_preferred_over_a_private_name(user_repo: RepoBuilder) -> None:
    """Both are violations; the ``_internal`` one is the shape worth showing."""
    repo = user_repo(
        "src", files={**PACKAGE_WITH_A_PRIVATE_FUNCTION, **PACKAGE_WITH_A_PRIVATE_MODULE}
    )
    assert repo.configure().passed

    violation = repo.violation()
    assert violation["expected_mention"] == "acme_widgets.pricing._internal._totals.total_due"

    repo.append(violation["target_file"], violation["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output
    assert violated.mentions(violation["expected_mention"]), violated.output


def test_a_repo_with_no_private_names_is_told_to_scaffold(user_repo: RepoBuilder) -> None:
    """The greenfield case, which is what the example package is really for."""
    repo = user_repo("src")
    assert repo.configure().passed

    violation = repo.violation()
    assert not violation["found"]
    assert "scaffold" in violation["next_step"]

    assert repo.scaffold().passed
    after = repo.violation()
    assert after["found"], after

    repo.append(after["target_file"], after["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output
    assert violated.mentions(after["expected_mention"]), violated.output


def test_the_import_never_lands_inside_the_package_it_violates(
    user_repo: RepoBuilder,
) -> None:
    """A private import from within its own package is legal, so a target inside
    it would make the check stay green and read as a broken setup."""
    repo = user_repo("flat", files={
        path.replace("src/", ""): contents
        for path, contents in PACKAGE_WITH_A_PRIVATE_MODULE.items()
    })
    assert repo.configure().passed

    violation = repo.violation()
    assert violation["found"], violation
    assert not violation["target_file"].startswith("acme_widgets/pricing/")

    repo.append(violation["target_file"], violation["import_line"])
    assert not repo.check().passed
