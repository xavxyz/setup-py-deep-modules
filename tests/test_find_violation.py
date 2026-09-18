"""The proof cycle run against a private name the repo already has.

Step 5 is the load-bearing step: a ``tach.toml`` that does not go red on a real
violation is worth nothing. ``find-violation`` is what lets that step run
without depositing an example package first -- and a boundary the project
already has is the stronger proof, since it is one the skill did not create and
therefore does not know to be well-formed.
"""

from __future__ import annotations

import shutil

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

    clean = repo.check()
    assert clean.passed, clean.output

    repo.append(violation["target_file"], violation["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output
    assert violated.mentions(violation["expected_mention"]), violated.output

    repo.remove(violation["target_file"], violation["import_line"])
    reverted = repo.check()
    assert reverted.passed, reverted.output


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
    configured = repo.configure()
    assert configured.passed, configured.output

    violation = repo.violation()
    assert violation["expected_mention"] == "acme_widgets.pricing._internal._totals.total_due"

    repo.append(violation["target_file"], violation["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output
    assert violated.mentions(violation["expected_mention"]), violated.output


def test_a_greenfield_proof_leaves_no_scaffold_behind(user_repo: RepoBuilder) -> None:
    """The greenfield case: a proof scaffold is written only to give the proof
    something to go red on, so like the appended import it is removed once the
    check is green again -- and the check stays green with it gone."""
    repo = user_repo("src")
    configured = repo.configure()
    assert configured.passed, configured.output

    violation = repo.violation()
    assert not violation["found"]
    assert "scaffold" in violation["next_step"]
    removal = "rm -rf src/acme_widgets/billing"
    assert removal in violation["next_step"], violation["next_step"]

    scaffolded = repo.scaffold()
    assert scaffolded.passed, scaffolded.output
    after = repo.violation()
    assert after["found"], after

    repo.append(after["target_file"], after["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output
    assert violated.mentions(after["expected_mention"]), violated.output

    repo.remove(after["target_file"], after["import_line"])
    reverted = repo.check()
    assert reverted.passed, reverted.output

    shutil.rmtree(repo.root / removal.removeprefix("rm -rf "))
    assert not repo.exists("src/acme_widgets/billing")
    removed = repo.check()
    assert removed.passed, removed.output
    cycles = repo.check_cycles()
    assert cycles.passed, cycles.output


def test_the_proof_scaffold_never_takes_the_name_of_a_real_package(
    user_repo: RepoBuilder,
) -> None:
    """The removal ``next_step`` names is an ``rm -rf``, so it must point at the
    directory ``scaffold`` will write -- never at a package the repo already has."""
    repo = user_repo("src", files={
        "src/acme_widgets/billing/__init__.py": '"""Billing, written by the user."""\n',
    })
    configured = repo.configure()
    assert configured.passed, configured.output

    violation = repo.violation()
    assert not violation["found"]
    assert "rm -rf src/acme_widgets/billing." not in violation["next_step"]
    assert "rm -rf src/acme_widgets/billing " not in violation["next_step"]

    name = violation["next_step"].split("scaffold --name ")[1].split("`")[0]
    scaffolded = repo.scaffold("--name", name)
    assert scaffolded.passed, scaffolded.output
    assert f"rm -rf src/acme_widgets/{name}." in violation["next_step"]
    assert repo.exists("src/acme_widgets/billing/__init__.py")


def test_the_import_never_lands_inside_the_package_it_violates(
    user_repo: RepoBuilder,
) -> None:
    """A private import from within its own package is legal, so a target inside
    it would make the check stay green and read as a broken setup."""
    repo = user_repo("flat", files={
        path.replace("src/", ""): contents
        for path, contents in PACKAGE_WITH_A_PRIVATE_MODULE.items()
    })
    configured = repo.configure()
    assert configured.passed, configured.output

    violation = repo.violation()
    assert violation["found"], violation
    assert not violation["target_file"].startswith("acme_widgets/pricing/")

    repo.append(violation["target_file"], violation["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output


def test_the_proof_works_when_the_tier_sits_beside_the_root_package(
    user_repo: RepoBuilder,
) -> None:
    """A repo keeping its packages in ``src/packages/`` puts the violating
    import in a module the tier does not contain, so the target has to be a
    file tach still checks -- which is what ``root_module = "allow"`` buys."""
    repo = user_repo("src", files={
        "src/packages/__init__.py": '"""Existing package tier."""\n',
        "src/packages/pricing/__init__.py": (
            '"""Pricing."""\n\nfrom ._internal._totals import total_due\n\n'
            '__all__ = ["total_due"]\n'
        ),
        "src/packages/pricing/_internal/__init__.py": '"""Implementation."""\n',
        "src/packages/pricing/_internal/_totals.py": (
            '"""Totals."""\n\n\ndef total_due(cents: int) -> int:\n    return cents\n'
        ),
    })
    configured = repo.configure()
    assert configured.passed, configured.output

    violation = repo.violation()
    assert violation["expected_mention"] == "packages.pricing._internal._totals.total_due"

    repo.append(violation["target_file"], violation["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output
    assert violated.mentions(violation["expected_mention"]), violated.output


def test_a_private_name_in_a_loose_module_counts(user_repo: RepoBuilder) -> None:
    """The tier's glob makes a loose ``helpers.py`` a tach module like any
    package, and tach guards its private names the same way. Skipping those
    reported "nothing to prove it on" at a repo that had a violation to hand."""
    repo = user_repo("src", files={
        "src/acme_widgets/helpers.py": (
            '"""Helpers."""\n\n\ndef _shorten(text: str) -> str:\n    return text[:8]\n'
        ),
    })
    configured = repo.configure()
    assert configured.passed, configured.output

    violation = repo.violation()
    assert violation["found"], violation
    assert violation["expected_mention"] == "acme_widgets.helpers._shorten"
    assert violation["target_file"] != "src/acme_widgets/helpers.py"

    repo.append(violation["target_file"], violation["import_line"])
    violated = repo.check()
    assert not violated.passed, violated.output
    assert violated.mentions(violation["expected_mention"]), violated.output


def test_the_import_goes_in_a_loose_module_rather_than_an_init(
    user_repo: RepoBuilder,
) -> None:
    """``__init__.py`` is the worse place to leave a stray line behind if the
    cycle is interrupted, so a loose module at the app tier wins where there is
    one. Both are checked by tach, so this is about tidiness, not correctness."""
    repo = user_repo("src", files=PACKAGE_WITH_A_PRIVATE_MODULE)
    configured = repo.configure()
    assert configured.passed, configured.output

    assert repo.violation()["target_file"] == "src/acme_widgets/app.py"
