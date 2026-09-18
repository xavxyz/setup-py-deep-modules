---
name: setup-py-deep-modules
description: Wire tach into a Python repo so each package hides its implementation behind a small public interface, reachable only through names without a leading underscore.
disable-model-invocation: true
---

# Setup Py Deep Modules

Someone arriving at `payments/` — a person or an agent — should learn everything the package offers by reading **one** file, and should be able to trust that reading. Python gives you no way to make that true: a leading underscore and a docstring are advisory, so over time they are ignored, every file becomes load-bearing for every other, and the cost of understanding any single package grows without limit.

The idea being enforced here is the **deep module**: a lot of behaviour behind a small interface. A module's **interface** is everything a caller must know to use it; its **depth** is the ratio of behaviour provided to the size of that interface. Deep is a small surface with a lot behind it; shallow is an interface nearly as large as its implementation, which hides nothing and buys nothing. The term is John Ousterhout's, from *A Philosophy of Software Design* (2018).

That paragraph is all the vocabulary this skill needs. If the `codebase-design` skill is installed, call it and use its language throughout.

[tach](https://github.com/tach-org/tach) makes the boundary mechanical: a package's public surface is every name that does **not** start with an underscore, and `tach check` fails on any import reaching past it.

## The shape this enforces

```
src/myproject/
  app.py            ← app-tier code: unconstrained itself, still bound by every interface
  billing/
    __init__.py     ← THE public interface: named re-exports + __all__
    quote.py        ← an additional entry point (public: no leading underscore)
    _internal/      ← implementation: private, free to import itself
      _totals.py
tests/              ← at the repo root; goes through the interfaces like any other caller
scripts/
  check_cycles.py   ← rejects import cycles between packages
```

That is the fixture CI proves on every push, and the example step 4 offers — so what a user gets is what is proven.

Four rules `tach check` enforces:

1. **Public means no underscore.** From outside, `myproject.billing` and `myproject.billing.quote`, never `myproject.billing._internal`. Adding a package, or a private folder inside one, needs no edit to the config.
2. **Freedom inside.** A package's own modules import each other however they like. The rule governs the boundary, not the implementation behind it.
3. **Tests too.** A top-level `tests/` is code outside every package, so the same rule already forces it through the public surfaces.
4. **`__init__.py` is the interface.** Named re-exports listed in `__all__`, which keeps the surface enumerable — the one thing this whole exercise buys.

And one it cannot: **no cycles between packages**, caught by `scripts/check_cycles.py`. Tach's `forbid_circular_dependencies` only sees dependencies *declared* in `tach.toml`, and the generic rule declares none; the script reads the real graph from `tach map`, and needs no per-package config either.

Layering — *which* packages may depend on which — ships as a commented stub in the config.

## Steps

One script does the mechanical half. Run everything from the root of the user's repo.

The script ships inside this skill, in `scripts/` beside this file, along with the `fixture/` it renders everything from. Set `SETUP` to its absolute path, resolved from wherever you read this SKILL.md. Do **not** reach for `${CLAUDE_PLUGIN_ROOT}`: it is set only for plugin installs, and expands to nothing when the skill is installed on its own, which silently turns every command below into a path that does not exist.

```sh
SETUP="<the directory holding this SKILL.md>/scripts/setup_deep_modules.py"
python3 "$SETUP" --help          # confirm the path before relying on it
```

### 1. Detect

```sh
python3 "$SETUP" detect
```

Facts as JSON. Use the reported `install_command`, `check_command` and `cycle_command` verbatim from here on: `uv add` and friends put tach in the project's environment rather than on your PATH, and a bare `tach check` then fails for a reason that looks exactly like the failure step 5 is waiting for.

Tell the user the layout, the package manager, and where packages will live. A non-zero exit is a question for them — no `pyproject.toml`, or several candidate root packages — so relay it rather than picking.

**Done when:** you can name the root package, the source roots and the package manager.

### 2. Install

Run `install_command`. Where `records_dependency` is false — the pip case — also write `tach_requirement` into `dependency_file`, under `dependency_target`: a pin nobody records is not a pin.

Step 3 writes the config directly, which is the point of it. `tach mod` is interactive, and `tach sync` writes down the dependencies that happen to exist today, cementing the current structure as the rule.

**Done when:** `check_command` runs and reports on the repo, rather than reporting a missing command.

### 3. Configure

```sh
python3 "$SETUP" configure
```

Writes `tach.toml` and `scripts/check_cycles.py`, and appends a `tach check` hook to a `.pre-commit-config.yaml` that already exists. Read its output and act on it: it refuses to overwrite files it did not write, and names each one it left alone.

For CI, say in prose where their pipeline should run `check_command` and `cycle_command`. Their workflow is theirs to edit.

**Done when:** `tach.toml` exists and you have relayed every refusal.

### 4. Offer the worked example

```sh
python3 "$SETUP" scaffold        # only when they want it, or step 5 asks for it
```

An example package that delegates to `_internal/` rather than passing through — the part worth copying. Nothing in `tach.toml`, in `scripts/check_cycles.py`, or in their CI refers to it, so on a repo that already has packages it is a new domain concept sitting next to the real ones, and it is theirs to want.

**Offer it; do not run it by default.** Describe what it is and let them answer. Step 6 documents the same shape in prose either way.

**Done when:** they have taken it or turned it down — and if they took it, you have relayed the script's line about copying its shape or deleting it.

### 5. Prove: red, then green

A misconfigured `tach.toml` passes exactly as quietly as a correct one, so the whole setup is worth nothing until you have watched the check go **red** on a real violation.

Any private name in any package is a valid violation, so use one the repo already has. That is the stronger proof: it exercises a boundary the project actually has, rather than one this skill just wrote and therefore knows to be well-formed.

```sh
python3 "$SETUP" find-violation
```

JSON: an `import_line`, the `target_file` to put it in, and the `expected_mention` the report should come back with. It searches every package at the tier, and the loose modules beside them. Where `found` is false the repo keeps nothing behind a public surface yet — the greenfield case the example package is really for — so run step 4's `scaffold` and ask again.

```sh
<check_command>          # green
echo "<import_line>" >> <target_file>
<check_command>          # red, naming <expected_mention>
# revert the line
<check_command>          # green again
<cycle_command>
```

Track your own import by name through the cycle rather than the exit code. **On a repo that was not written to this rule, the very first `check_command` may already be red**, and often is: interface violations and cycles that were free until today. That is a finding, not a fault, and not a reason to stop — it is what separates "the checker works" from "the checker happens to be failing". Report those pre-existing violations as the real debt they are, and leave fixing them to a separate piece of work.

If red never arrives, stop here and say so plainly. The usual causes are wrong source roots, tach not on the path you invoked, or an edited module outside the configured tier.

**Done when:** you have seen the check name your import, and go green again once it is gone.

### 6. Document

```sh
python3 "$SETUP" document
```

Writes the convention doc inside the distribution package, and a one-line pointer into `CLAUDE.md` or `AGENTS.md`. If it refuses because a README is already there, fold the convention into that file by hand.

**Done when:** the doc and the pointer both exist.

### Report

What was detected, what was installed and written, **that you watched the check go red on a violation and green again afterwards**, any pre-existing violations, the two check commands, and — if they took it — that the example package is theirs to copy or delete.

Then check the working tree for this skill's own install files: `.agents/skills/setup-py-deep-modules/`, a `.claude/skills/setup-py-deep-modules` link, and a `skills-lock.json` pinning this skill. A project-level install leaves them there, and nothing about them belongs to the target repository. If any are present, name them and tell the user to leave them out of the commit. Do not delete them or add them to `.gitignore`: this skill did not write them, so they are not its to remove.
