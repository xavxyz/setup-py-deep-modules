---
name: setup-py-deep-modules
description: Wire tach into a Python repo so each package hides its implementation behind a small public interface, reachable only through names without a leading underscore. User-invoked.
disable-model-invocation: true
---

# Setup Py Deep Modules

Someone arriving at `payments/` — a person or an agent — should learn everything the package offers by reading **one** file, and should be able to trust that reading. Python gives you no way to make that true: a leading underscore and a docstring are advisory, nothing fails when they are ignored, so over time they are ignored. Callers reach into internals, every file becomes load-bearing for every other, and the cost of understanding any single package grows without limit.

The idea being enforced here is the **deep module**: a lot of behaviour behind a small interface. A module's **interface** is everything a caller must know to use it; its **depth** is the ratio of the behaviour it provides to the size of that interface. A deep module is one where that ratio is high — a small surface, a lot behind it. A shallow one has an interface nearly as large as its implementation, so it hides nothing and buys nothing. The term is John Ousterhout's, from *A Philosophy of Software Design* (2018).

That paragraph is all the vocabulary this skill needs. If the `codebase-design` skill is installed, call it and use its language throughout.

That boundary is made mechanical with [tach](https://github.com/tach-org/tach): a package's public surface is every name that does **not** start with an underscore, and `tach check` fails on any import that reaches past it.

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

That shape is committed in this repo under `fixture/`, checked by CI, and is the example the skill scaffolds — so what you copy is what is proven.

Five rules, the first four checked by `tach check`:

1. **Public means no underscore.** Code outside a package may import `myproject.billing` and `myproject.billing.quote`, never `myproject.billing._internal` or anything inside it. The rule is generic: adding a package, or a private folder inside one, never means editing the config.
2. **Freedom inside.** A package's own modules import each other however they like. The rule constrains what crosses the package boundary, not how the implementation behind it is arranged.
3. **Tests go through the interface too.** Tests live at the repo root, which makes them code outside every package, so the same rule already forces them through the public surface. A passing suite is evidence the interface is usable.
4. **`__init__.py` is the interface.** Re-export explicit names and list them in `__all__`. Keep the surface enumerable: `from ._internal import *` makes it unenumerable, which is the one thing this whole exercise is buying.
5. **No cycles between packages.** Checked by `python scripts/check_cycles.py`, not by `tach check`: tach's `forbid_circular_dependencies` only looks at dependencies *declared* in `tach.toml`, and the generic rule declares none. The script reads the real import graph from `tach map` instead, and needs no per-package configuration either.

Layering — *which* packages may depend on which — is a different concern, and ships as a commented stub in the config for you to fill in.

## Running this skill

Six steps, in order. The mechanical parts — reading the layout, rendering the
config, copying the example, writing the doc — are one script, so they come out
the same every run:

```sh
SETUP="${CLAUDE_PLUGIN_ROOT}/skills/setup-py-deep-modules/scripts/setup_deep_modules.py"
```

Run every command from the root of the user's repo, with a Python 3.11 or newer
interpreter. Everything the script writes is derived from `fixture/` in this
plugin, which CI proves on every push — so what a user gets is what is proven.

### 1. Detect

```sh
python3 "$SETUP" detect
```

JSON: the layout (src or flat), the root package, the source roots, the package
tier and its module glob, the package manager, the exact install command, the
`check_command` and `cycle_command` to use from step 5 onwards, and the tach
pin. Read it, then tell the user in a sentence what you found — the
layout, the package manager, and where packages will live.

If it exits non-zero it has found something it must not guess at: no
`pyproject.toml`, or several candidate root packages. Relay the message and ask
the user, rather than picking for them.

An existing `packages/` directory shows up as the package tier. That is
deliberate: a repo with that convention keeps it.

### 2. Install

Run the `install_command` from step 1 verbatim. It carries a compatible-minor
pin (`tach~=0.x.0`), so patches flow and a breaking minor does not.

If `records_dependency` is false — the pip case — the install records nothing,
so the pin is yours to write down: add `tach_requirement` to the reported
`dependency_file`, under `dependency_target`, before or after installing. A pin
nobody records is not a pin.

**Do not run `tach mod` or `tach sync`.** `mod` is interactive and you cannot
drive it. `sync` writes down the dependencies that happen to exist today,
cementing the current structure as the rule — the opposite of what is being
installed here.

### 3. Configure

```sh
python3 "$SETUP" configure
```

Writes `tach.toml` (the generic rule, rendered for this repo's roots and package
tier) and `scripts/check_cycles.py`. It refuses to overwrite an existing
`tach.toml`: if it does, read that file, discuss it with the user, and re-run
with `--force` only if they agree.

The output ends with what happened about pre-commit. A repo that already has a
`.pre-commit-config.yaml` gets a `tach check` hook appended to it; read the file
back, and if it groups its hooks deliberately, move the block to where it
belongs. A repo without one does not get one — pre-commit is a tool the user has
not chosen.

Do not write a CI workflow either. Explain in prose instead: their CI needs to
install the dev dependencies and run the two commands from step 1
(`check_command` and `cycle_command`), wherever it already runs their linters.

### 4. Scaffold

```sh
python3 "$SETUP" scaffold
```

Copies a worked example into the package tier: a public surface in
`__init__.py`, a further entry point in `quote.py`, and the behaviour behind
both in `_internal/`. It delegates rather than passing through, which is the
part worth copying.

Tell the user it is a starter: copy its shape, then `rm -rf` it. Nothing in
their repo imports it, so it deletes cleanly.

### 5. Prove

Nothing so far is evidence. A misconfigured `tach.toml` passes just as quietly
as a correct one, so **this step is the completion criterion: you must see the
check fail on a real violation, and you must not report success without it.**

Use the `check_command` from step 1 — after `uv add`, `poetry add` or `pdm add`,
tach lives in the project's environment and not on your PATH, and a "command not
found" is easily misread as the failure this step is waiting for.

```sh
uv run tach check               # 1. passes  (or the detected check_command)
```

If this first run *fails*, the repo has boundary violations already. That is a
real finding, not an error — report them to the user as existing debt to fix,
and carry on with the cycle below, watching for the specific import you add
rather than for the overall exit code.

```sh
# 2. must fail, naming the import
echo "from <tier>.billing._internal._totals import total_due  # noqa: F401" >> <a module outside billing>
uv run tach check
```

Confirm the report names that import. Then revert it and confirm the check
returns to where it was in step 1. Also run the `cycle_command`:

```sh
uv run python scripts/check_cycles.py
```

If step 2 does not fail, stop. Do not document anything, and do not tell the
user it works. Investigate: usually the source roots are wrong, tach is not
actually on the path you invoked, or the module you edited is not covered by the
config.

### 6. Document

```sh
python3 "$SETUP" document
```

Writes the convention doc inside the distribution package — where a reader
meets it rather than having to search for it — and adds a one-line
pointer to `CLAUDE.md`, or `AGENTS.md`, creating `AGENTS.md` if the repo has
neither. It refuses to overwrite an existing README; if so, fold the convention
into that file by hand instead.

### Finally

Report to the user: what was detected, what was installed and written, **that
you watched the check fail on a violation and pass again afterwards**, any
pre-existing violations you found, how to run the check, and that the example
package is theirs to copy or delete.
