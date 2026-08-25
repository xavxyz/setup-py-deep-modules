#!/usr/bin/env python3
"""The mechanical half of ``/setup-py-deep-modules``.

The skill's judgement -- reading the repo, explaining what it found, running the
package manager, watching the check fail -- belongs to the agent. The parts with
one right answer belong here, so that they come out the same on every run and
can be tested: what the layout is, what goes in ``tach.toml``, where the example
package lands, and what the convention doc says.

Everything this writes is derived from ``fixture/`` in the plugin, which CI
proves on every push. Nothing is a second copy of it.

Usage, from the root of the repo being set up:

    python3 setup_deep_modules.py detect                 # facts, as JSON
    python3 setup_deep_modules.py configure              # tach.toml + cycle check
    python3 setup_deep_modules.py scaffold               # the copy-me example
    python3 setup_deep_modules.py document               # convention doc + pointer
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit(
        "Reading pyproject.toml needs Python 3.11 or newer. Re-run this script "
        "with a newer interpreter."
    )

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = PLUGIN_ROOT / "fixture"

#: Directories that never hold the distribution package, whatever they contain.
#: ``packages`` is here because a repo with that directory is using it as its
#: package tier, which is a thing this skill honours -- but it is not the
#: distribution package itself, and mistaking it for one stops detection dead.
NOT_PACKAGES = {
    "tests",
    "test",
    "docs",
    "doc",
    "examples",
    "scripts",
    "build",
    "dist",
    "packages",
}

#: The example package copied into a user's repo, and the module that proves it
#: delegates rather than passing through.
EXAMPLE_PACKAGE = "billing"

#: Everything that differs between package managers, in one place: how to add a
#: dev dependency, whether doing so records the pin, and how to reach a command
#: installed into the project's environment.
MANAGERS = {
    "uv": {"add": "uv add --dev", "records": True, "run": "uv run "},
    "poetry": {"add": "poetry add --group dev", "records": True, "run": "poetry run "},
    "pdm": {"add": "pdm add --dev", "records": True, "run": "pdm run "},
    "pip": {"add": "python -m pip install", "records": False, "run": ""},
}


class SkillError(Exception):
    """Base for the two reasons this script stops early."""


class NeedsADecision(SkillError):
    """The repo says something the skill must not guess at, or overwrite.

    Every one of these is a question for the user: an ambiguous root package, a
    missing ``pyproject.toml``, a file that is already there and was not written
    by this skill.
    """


class PluginBroken(SkillError):
    """The plugin's own fixture no longer matches what the script renders from it.

    Nothing to do with the user's repo: this says the plugin needs fixing before
    it can configure anything.
    """


@dataclass(frozen=True)
class Repo:
    """Everything the later steps need to know about the repo being set up.

    Serialised to JSON for the agent, and passed around in Python by the steps
    themselves, so the two can never disagree about what was detected.
    """

    layout: str
    root_package: str
    package_root: str
    source_roots: list[str]
    module_glob: str
    package_tier: str
    package_manager: str
    install_command: str
    records_dependency: bool
    dependency_file: str
    dependency_target: str
    check_command: str
    cycle_command: str
    tach_requirement: str
    has_pre_commit: bool
    agent_file: str


# --------------------------------------------------------------------------
# detect
# --------------------------------------------------------------------------


def detect(repo_root: Path) -> Repo:
    """Read the layout and tooling out of the repo, or refuse to guess."""
    config = _load_pyproject(repo_root)
    package_root = _find_package_root(repo_root, config)
    source_dir = package_root.parent
    layout = "flat" if source_dir == repo_root else "src"

    source_root = "." if layout == "flat" else _relative(source_dir, repo_root)
    source_roots = [source_root]
    if layout == "src" and (repo_root / "tests").is_dir():
        # Naming a directory that is not there makes tach fail outright, and in
        # a flat layout the tests already sit under the single source root.
        source_roots.append("tests")

    tier, glob = _package_tier(repo_root, package_root, source_dir)
    manager = _package_manager(repo_root, config)
    requirement = _tach_requirement()
    run = str(MANAGERS[manager]["run"])
    dependency_file = _dependency_file(repo_root, manager)

    return Repo(
        layout=layout,
        root_package=package_root.name,
        package_root=_relative(package_root, repo_root),
        source_roots=source_roots,
        module_glob=glob,
        package_tier=_relative(tier, repo_root),
        package_manager=manager,
        install_command=f'{MANAGERS[manager]["add"]} "{requirement}"',
        records_dependency=bool(MANAGERS[manager]["records"]),
        dependency_file=dependency_file,
        dependency_target=_dependency_target(dependency_file),
        check_command=f"{run}tach check",
        cycle_command=f"{run}python scripts/check_cycles.py",
        tach_requirement=requirement,
        has_pre_commit=(repo_root / ".pre-commit-config.yaml").is_file(),
        agent_file=_agent_file(repo_root),
    )


def _load_pyproject(repo_root: Path) -> dict:
    """The repo's ``pyproject.toml``, parsed. Every later step reads the layout
    out of it, so its absence is a stop rather than a default."""
    path = repo_root / "pyproject.toml"
    if not path.is_file():
        raise NeedsADecision(
            f"No pyproject.toml in {repo_root}. The layout is read from it, and "
            "guessing without one would configure the wrong thing silently."
        )
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _find_package_root(repo_root: Path, config: dict) -> Path:
    """The distribution package's directory: ``src/acme_widgets`` or ``acme_widgets``.

    Candidates come from the directories the build backend names as holding
    source, plus the two conventional ones. The distribution name decides
    between them; where it cannot, the caller is asked rather than guessed at.
    """
    candidates: dict[str, Path] = {}
    for source_dir in _declared_source_dirs(repo_root, config):
        for child in sorted(source_dir.iterdir()):
            if not (child / "__init__.py").is_file():
                continue
            if child.name in NOT_PACKAGES or child.name.startswith((".", "_")):
                continue
            candidates.setdefault(child.name, child)

    if not candidates:
        raise NeedsADecision(
            "Found no importable package under this repo's source directories. "
            "Point the skill at a repo whose package has an __init__.py."
        )
    if len(candidates) == 1:
        return next(iter(candidates.values()))

    expected = _module_name(config)
    if expected in candidates:
        return candidates[expected]
    raise NeedsADecision(
        "Several packages could be the distribution package: "
        + ", ".join(sorted(candidates))
        + ". Several distributions in one repo is out of scope for this skill; "
        "pick one and run it from a repo with a single root package."
    )


def _declared_source_dirs(repo_root: Path, config: dict) -> list[Path]:
    """Source directories the build backend names, then the conventional ones.

    Declared ones come first so that a repo saying ``where = ["lib"]`` is taken
    at its word rather than matched against a stray ``src``.
    """
    declared: list[str] = []
    declared += list(_dig(config, "tool", "setuptools", "packages", "find", "where") or [])
    declared += [
        value
        for key, value in (_dig(config, "tool", "setuptools", "package-dir") or {}).items()
        if key == ""
    ]

    for package in _dig(config, "tool", "poetry", "packages") or []:
        if isinstance(package, dict) and package.get("from"):
            declared.append(str(package["from"]))

    for entry in _dig(config, "tool", "hatch", "build", "targets", "wheel", "packages") or []:
        # Hatch names the package itself ("src/acme"), not the root above it.
        parent = str(Path(str(entry)).parent)
        declared.append(parent or ".")

    declared += ["src", "."]

    seen: list[Path] = []
    for entry in declared:
        path = (repo_root / entry).resolve()
        if path.is_dir() and path not in seen:
            seen.append(path)
    return seen


def _dig(config: dict, *keys: str):
    """Walk nested tables, giving up quietly at the first one that is not there.

    Build-backend config is four and five tables deep, and a chain of ``.get({})``
    calls hides which key was actually being looked for.
    """
    current = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _module_name(config: dict) -> str:
    """The name an importer would use for this distribution: ``a-b`` -> ``a_b``."""
    name = config.get("project", {}).get("name") or config.get("tool", {}).get(
        "poetry", {}
    ).get("name", "")
    return re.sub(r"[-_.]+", "_", str(name)).lower()


def _package_tier(repo_root: Path, package_root: Path, source_dir: Path) -> tuple[Path, str]:
    """Where deep modules live, and the glob that makes each one a tach module.

    Normally that is the root package's immediate subpackages. A repo that
    already keeps them in a ``packages/`` directory has a convention of its own,
    and the rule adopts it rather than competing with it.
    """
    for parent in (source_dir, package_root):
        existing = parent / "packages"
        if existing.is_dir():
            relative = existing.relative_to(source_dir)
            return existing, ".".join(relative.parts) + ".*"
    return package_root, f"{package_root.name}.*"


def _package_manager(repo_root: Path, config: dict) -> str:
    """Which tool owns this repo's dependencies.

    A lockfile is stronger evidence than a config table -- it is the file the
    tool actually maintains -- so it is checked first for each candidate.
    """
    tools = config.get("tool", {})
    for name, lockfile in (("uv", "uv.lock"), ("poetry", "poetry.lock"), ("pdm", "pdm.lock")):
        if (repo_root / lockfile).is_file() or name in tools:
            return name
    return "pip"


def _dependency_file(repo_root: Path, manager: str) -> str:
    """Where the pin has to be written down.

    Only meaningful for pip: ``pip install`` records nothing, and a pin nobody
    records is not a pin.
    """
    if MANAGERS[manager]["records"]:
        return "pyproject.toml"
    for candidate in ("requirements-dev.txt", "dev-requirements.txt"):
        if (repo_root / candidate).is_file():
            return candidate
    return "pyproject.toml"


def _dependency_target(dependency_file: str) -> str:
    """Where in that file the pin goes, spelled out rather than left implied."""
    if dependency_file.endswith(".txt"):
        return "one requirement per line"
    return "[project.optional-dependencies] dev"


def _tach_requirement() -> str:
    """The compatible-minor pin, read from the fixture CI proves on every push."""
    text = (FIXTURE / "pyproject.toml").read_text()
    for line in text.splitlines():
        stripped = line.strip().rstrip(",").strip('"')
        if stripped.startswith("tach~="):
            return stripped
    raise NeedsADecision("The plugin's fixture no longer pins tach; the plugin is broken.")


def _agent_file(repo_root: Path) -> str:
    """The instructions file the pointer goes in, creating ``AGENTS.md`` if neither."""
    for candidate in ("CLAUDE.md", "AGENTS.md"):
        if (repo_root / candidate).is_file():
            return candidate
    return "AGENTS.md"


def _relative(path: Path, repo_root: Path) -> str:
    """A path as the user would type it: relative to the repo root, or ``.``."""
    relative = path.resolve().relative_to(repo_root.resolve())
    return str(relative) if str(relative) != "." else "."


# --------------------------------------------------------------------------
# configure
# --------------------------------------------------------------------------


def configure(repo_root: Path, repo: Repo, force: bool = False) -> list[str]:
    """Write ``tach.toml`` and the cycle check, rendered for this repo.

    Both are derived from the fixture rather than written afresh: the fixture is
    what CI proves, so anything re-typed here would be a second, unproven copy.
    """
    report: list[str] = []
    config_path = repo_root / "tach.toml"
    if config_path.exists() and not force:
        raise NeedsADecision(
            f"{_relative(config_path, repo_root)} already exists. Read it, decide "
            "with the user what should happen to it, and re-run with --force to "
            "replace it. Nothing has been written."
        )
    config_path.write_text(render_config(repo))
    report.append(f"Wrote tach.toml for {repo.module_glob} over {repo.source_roots}.")

    script_path = repo_root / "scripts" / "check_cycles.py"
    source = (FIXTURE / "scripts" / "check_cycles.py").read_text()
    if script_path.exists() and script_path.read_text() != source and not force:
        report.append(
            f"Left {_relative(script_path, repo_root)} alone: it exists and differs "
            "from the one shipped with the plugin."
        )
    else:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(source)
        script_path.chmod(0o755)
        report.append("Wrote scripts/check_cycles.py (tach check cannot see real cycles).")

    report.append(_extend_pre_commit(repo_root, repo))
    return report


def render_config(repo: Repo) -> str:
    """The fixture's ``tach.toml``, with this repo's roots and package tier in it.

    Only two lines differ between one repo and another. Substituting them keeps
    the rule -- the interface regex, the exclusions, the layering stub, and the
    comments explaining all three -- identical to the proven original.
    """
    text = (FIXTURE / "tach.toml").read_text()
    roots = ", ".join(f'"{root}"' for root in repo.source_roots)

    text, roots_changed = re.subn(
        r"^source_roots = .*$", f"source_roots = [{roots}]", text, count=1, flags=re.M
    )
    text, glob_changed = re.subn(
        r'^path = "myproject\.\*"$', f'path = "{repo.module_glob}"', text, count=1, flags=re.M
    )
    if not (roots_changed and glob_changed):
        raise PluginBroken(
            "The plugin's fixture tach.toml no longer has the lines this renders."
        )
    return text


HOOK = """  - repo: local
    hooks:
      - id: tach
        name: tach check
        entry: {command}
        language: system
        pass_filenames: false
        types: [python]
"""


def _extend_pre_commit(repo_root: Path, repo: Repo) -> str:
    """Add the check to an existing pre-commit config, and only an existing one.

    A repo without pre-commit has not chosen pre-commit, and arriving with it
    uninvited is how a setup skill becomes something people undo. Where the file
    is there, the hook is appended rather than spliced into the middle: the end
    of the ``repos:`` list is the one position that needs no understanding of
    what the rest of the file is doing.
    """
    path = repo_root / ".pre-commit-config.yaml"
    if not path.is_file():
        return (
            "No .pre-commit-config.yaml here, so none was created: pre-commit is a "
            "tool the user has not chosen. Explain CI wiring in prose instead."
        )

    existing = path.read_text()
    if "id: tach" in existing:
        return ".pre-commit-config.yaml already runs tach; left as it was."
    if not re.search(r"^repos:", existing, flags=re.M):
        return (
            ".pre-commit-config.yaml has no top-level `repos:` list, so it was "
            "left alone. Add this hook by hand, matching the file's own shape:\n"
            + HOOK.format(command=repo.check_command)
        )

    separator = "" if existing.endswith("\n") else "\n"
    path.write_text(existing + separator + HOOK.format(command=repo.check_command))
    return (
        "Added a `tach check` hook to the end of .pre-commit-config.yaml. Read it "
        "back: if the file groups its hooks deliberately, move the block to where "
        "it belongs."
    )


# --------------------------------------------------------------------------
# scaffold
# --------------------------------------------------------------------------


def scaffold(repo_root: Path, repo: Repo, name: str = EXAMPLE_PACKAGE) -> list[str]:
    """Copy the example package into the repo's package tier.

    It is the fixture's package verbatim -- the one CI proves -- and it uses
    relative imports throughout, so it carries nothing of the fixture's name
    with it and nothing in the user's repo comes to depend on it.
    """
    destination = repo_root / repo.package_tier / name
    if destination.exists():
        raise NeedsADecision(
            f"{_relative(destination, repo_root)} already exists. Pass a different "
            "--name, or delete it first. Nothing has been written."
        )
    shutil.copytree(
        FIXTURE / "src" / "myproject" / EXAMPLE_PACKAGE,
        destination,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    tier = _relative(destination, repo_root)
    return [
        f"Scaffolded {tier} as a worked example: a public surface in __init__.py, "
        "a further entry point in quote.py, and the implementation in _internal/.",
        f"It is a starter, not furniture. Copy its shape for your own packages, "
        f"then delete it: rm -rf {tier}. Nothing else imports it.",
    ]


# --------------------------------------------------------------------------
# document
# --------------------------------------------------------------------------


def document(repo_root: Path, repo: Repo, force: bool = False) -> list[str]:
    """Write the convention doc, and point the repo's agent file at it."""
    report: list[str] = []
    # Inside the distribution package: the directory a reader is already in
    # when the question occurs to them. Where a repo keeps its packages
    # elsewhere, the doc says so rather than following them out.
    doc_path = repo_root / repo.package_root / "README.md"
    if doc_path.exists() and not force:
        raise NeedsADecision(
            f"{_relative(doc_path, repo_root)} already exists. Fold the convention "
            "into it by hand, or re-run with --force to replace it. Nothing has "
            "been written."
        )
    doc_path.write_text(render_conventions(repo))
    report.append(
        f"Wrote {_relative(doc_path, repo_root)}: the convention, next to the code "
        "it governs, where a reader meets it rather than having to search for it."
    )

    report.append(_add_pointer(repo_root, repo, _relative(doc_path, repo_root)))
    return report


def render_conventions(repo: Repo) -> str:
    """The convention doc, written about this repo rather than about an example."""
    template = (PLUGIN_ROOT / "skills" / "setup-py-deep-modules" / "assets" / "conventions.md")
    substitutions = {
        "ROOT_PACKAGE": repo.root_package,
        "TIER_IMPORT": _tier_import(repo),
        "PACKAGE_TIER": repo.package_tier,
        "EXAMPLE": EXAMPLE_PACKAGE,
        "CHECK_COMMAND": repo.check_command,
        "CYCLE_COMMAND": repo.cycle_command,
    }
    text = template.read_text()
    for placeholder, value in substitutions.items():
        text = text.replace("{{" + placeholder + "}}", value)
    return text


def _tier_import(repo: Repo) -> str:
    """The dotted prefix an outsider uses to reach a package: ``acme_widgets.``."""
    return repo.module_glob[: -len("*")]


def _add_pointer(repo_root: Path, repo: Repo, doc_path: str) -> str:
    """Put a one-line pointer in the file the next agent reads.

    Appended, never rewritten, and never twice: re-running the skill in a repo it
    has already touched must not stack up duplicates.
    """
    path = repo_root / repo.agent_file
    pointer = (
        f"- Package boundaries are enforced: read `{doc_path}` before adding or "
        "importing a package. `tach check` fails on imports that reach past a "
        "package's public surface.\n"
    )
    if path.is_file():
        existing = path.read_text()
        if doc_path in existing:
            return f"{repo.agent_file} already points at the convention; left as it was."
        separator = "" if existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n"
        path.write_text(existing + separator + pointer)
        return f"Added a one-line pointer to {repo.agent_file}."
    path.write_text(f"# Agent instructions\n\n{pointer}")
    return f"Created {repo.agent_file} with a pointer to the convention."


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _report(lines: list[str]) -> None:
    """One blank line between findings, so a step's output reads as a list."""
    print("\n\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    """Run one step against one repo, and say what it did or why it did not."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="the repo to set up (default: the working directory)",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("detect", help="report the layout and tooling, as JSON")

    configure_parser = subcommands.add_parser(
        "configure", help="write tach.toml and scripts/check_cycles.py"
    )
    configure_parser.add_argument(
        "--force", action="store_true", help="replace an existing tach.toml"
    )

    scaffold_parser = subcommands.add_parser("scaffold", help="copy in the example package")
    scaffold_parser.add_argument(
        "--name", default=EXAMPLE_PACKAGE, help=f"name for the example (default: {EXAMPLE_PACKAGE})"
    )

    document_parser = subcommands.add_parser(
        "document", help="write the convention doc and the agent-file pointer"
    )
    document_parser.add_argument(
        "--force", action="store_true", help="replace an existing convention doc"
    )

    arguments = parser.parse_args(argv)
    repo_root = arguments.repo.resolve()

    try:
        if arguments.command == "detect":
            print(json.dumps(asdict(detect(repo_root)), indent=2))
        elif arguments.command == "configure":
            _report(configure(repo_root, detect(repo_root), force=arguments.force))
        elif arguments.command == "scaffold":
            _report(scaffold(repo_root, detect(repo_root), name=arguments.name))
        elif arguments.command == "document":
            _report(document(repo_root, detect(repo_root), force=arguments.force))
    except SkillError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
