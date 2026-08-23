---
name: setup-py-deep-modules
description: Wire tach into a Python repo so each package hides its implementation behind a small public interface, reachable only through names without a leading underscore. User-invoked.
disable-model-invocation: true
---

# Setup Py Deep Modules

Someone arriving at `payments/` — a person or an agent — should learn everything the package offers by reading **one** file, and should be able to trust that reading. Python gives you no way to make that true: a leading underscore and a docstring are advisory, nothing fails when they are ignored, so over time they are ignored. Callers reach into internals, every file becomes load-bearing for every other, and the cost of understanding any single package grows without limit.

The idea being enforced here is the **deep module**: a lot of behaviour behind a small interface. A module's **interface** is everything a caller must know to use it; its **depth** is the ratio of the behaviour it provides to the size of that interface. A deep module is one where that ratio is high — a small surface, a lot behind it. A shallow one has an interface nearly as large as its implementation, so it hides nothing and buys nothing. The term is John Ousterhout's, from *A Philosophy of Software Design* (2018).

That paragraph is all the vocabulary this skill needs. If the `codebase-design` skill is installed, call it and use its language throughout.

The plan is to make that boundary mechanical with [tach](https://github.com/tach-org/tach): a package's public surface is every name that does **not** start with an underscore, and `tach check` fails on any import that reaches past it. The mechanics are not wired up yet — see [What this skill will do](#what-this-skill-will-do) for what running it does today.

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

## What this skill will do

The steps below are the plan, not yet the implementation. Invoked today, this skill explains the plan and stops; the mechanics land next.

1. **Detect.** Root package, source root and layout (src or flat) from `pyproject.toml`; the package manager (uv / Poetry / PDM / pip).
2. **Install.** Add tach as a dev dependency with a compatible-minor pin, using the detected manager.
3. **Configure.** Write the generic `tach.toml` and `scripts/check_cycles.py`. Extend `.pre-commit-config.yaml` only if one already exists; explain CI wiring in prose rather than writing a workflow.
4. **Scaffold.** Create an example package that delegates to a private module, as a starter to copy or delete.
5. **Prove.** Run the check clean, add an import that reaches past an interface (it must fail), revert. Observing the failure is the completion criterion.
6. **Document.** Write the convention README next to the code it governs, and add a one-line pointer to `CLAUDE.md` or `AGENTS.md`.

Invoked today: report this plan to the user, say the steps are not wired up yet, and stop.
