# setup-py-deep-modules

> [!IMPORTANT]
> **This repo is an experiment.** Matt Pocock's `/setup-ts-deep-modules` is an
> excellent idea for TypeScript. The question here is whether it ports to
> Python, where the mechanism it relies on does not exist. Some of the answers
> below are deliberate departures from the original, for reasons given. Treat
> the whole thing as a hypothesis under test rather than settled practice.

A Python package hides nothing. Every module can reach into every other
module's internals, so nothing can change without breaking something
elsewhere. The cost falls hardest on discovery: to work on `payments/`, you —
or an agent — must read the entire package, because nothing tells you which
parts are public and which are implementation detail you should not touch. The
conventions Python offers, a leading underscore and a docstring, are advisory.
Nothing fails when they are ignored, so over time they are ignored.

The idea being enforced against that is the **deep module**: a lot of
behaviour behind a small interface. A module's *interface* is everything a
caller must know to use it; its *depth* is the ratio of behaviour provided to
the size of that interface. Deep is good — a small surface, a lot behind it. A
shallow module has an interface nearly as large as its implementation, so it
hides nothing and buys nothing.

**"Deep module" is John Ousterhout's**, from
*[A Philosophy of Software Design](https://web.stanford.edu/~ouster/cgi-bin/book.php)*
(2018). It is a software design principle, not a TypeScript concept.
[Matt Pocock](https://github.com/mattpocock) applied it to TypeScript in
[`/setup-ts-deep-modules`](https://github.com/mattpocock/skills/tree/main/skills/in-progress/setup-ts-deep-modules),
wiring dependency-cruiser into a repo so a package can only be imported through
its entry points. This repo is a port of that idea to Python, using
[tach](https://github.com/tach-org/tach).

Run the skill once, and the public surface of every package will be exactly the
names that do not start with an underscore — checked by a tool, not by
willpower. An agent will then be able to understand a package by reading one
file, and to trust that reading, because `tach check` fails if anything reaches
past it.

## Install

One command, in Claude Code:

```
/plugin marketplace add xavxyz/setup-py-deep-modules
```

That adds the marketplace and offers the plugin for install. Then, in your
Python repo:

```
/setup-py-deep-modules
```

> [!NOTE]
> **Status.** The plugin installs and the skill is invocable, but its steps are
> not wired up yet: invoked today, it explains what it will do and stops. The
> shape and the config below are settled; the automation is what is still
> landing.

## What your repo looks like afterwards

```
src/myproject/
  app.py                      application code (tach's "<root>" module)
  billing/
    __init__.py               the public surface: named re-exports + __all__
    quote.py                  an additional entry point — no leading underscore
    _internal/                everything else, unreachable from outside
      _invoice.py
      _money.py
      _tax.py
      _totals.py
  notifications/
    __init__.py               uses billing through its public surface only
    _internal/_templates.py
tests/                        top-level, and bound by the same rule
scripts/check_cycles.py       rejects import cycles between packages
tach.toml
```

`billing/__init__.py` is the whole of what a caller needs to read — plus
`quote.py`, if the package wants a second entry point. Inside `_internal/`,
the modules import each other however they like; the rule constrains what
crosses the package boundary, not how the implementation behind it is arranged.

```python
"""Invoice pricing."""

from ._internal._invoice import Invoice, LineItem
from ._internal._money import format_cents as format_amount
from ._internal._totals import total_due

__all__ = ["Invoice", "LineItem", "format_amount", "total_due"]
```

`app.py` reaches it through that surface, like anyone else:

```python
from myproject.billing import Invoice, LineItem   # fine
from myproject.billing._internal._tax import rate_for  # fails tach check
```

The rule is generic, so adding a package — or a private folder inside an
existing one — never means editing the config. The decision-carrying part of
`tach.toml`:

```toml
source_roots = ["src", "tests"]

# tach's default exclude list contains "**/tests". Restating the list without
# it is what puts the top-level test suite under the same rule as any other
# consumer.
exclude = ["**/*__pycache__", "**/*egg-info", "**/docs", "**/venv", "**/.venv"]

# Covers dependencies *declared* below via `depends_on`, which the generic rule
# deliberately does not use — so this starts holding once you fill in the
# layering stub. Cycles between the real imports are caught by
# `scripts/check_cycles.py`, which reads the actual graph from `tach map`.
forbid_circular_dependencies = true

# Code outside every package — the top-level tests, and loose modules sitting
# at the root package level — belongs to tach's "<root>" module. Declared with
# no `depends_on`, so it may use any package while still being bound by every
# package's interface.
root_module = "allow"

# Every immediate subpackage of the root package is a deep module.
[[modules]]
path = "myproject.*"

[[modules]]
path = "<root>"

# No `from` key, so every module adopts this interface. A name is importable
# from outside its package only if every segment of its path starts with
# something other than "_".
[[interfaces]]
expose = ["[^_][^.]*(\\.[^_][^.]*)*"]
```

Layering — *which* packages may depend on which — is a separate concern, and
ships as a commented stub for you to fill in.

## Running the check

```sh
tach check
python scripts/check_cycles.py
```

Clean exit means every import in the repo goes through a public surface. A
violation is reported by name, pointing at the offending import. The skill
wires the check into `.pre-commit-config.yaml` if you already have one, and
explains CI wiring in prose rather than writing a workflow into your repo.

The second command is there because tach's `forbid_circular_dependencies` only
looks at dependencies *declared* in `tach.toml`, and the generic rule
deliberately declares none — so it never sees a cycle the real imports form.
`check_cycles.py` reads the real graph from `tach map` instead, and, like the
interface rule, needs no per-package configuration: your packages are whatever
the directory listing says they are.

## Two deliberate divergences from the TypeScript original

If you arrive from `/setup-ts-deep-modules`, these will look like bugs. They
are not.

**1. Tests live at the repo root, not inside each package.** The TypeScript
skill has a dedicated rule forcing tests through the entry points. Here that
rule does not exist, and does not need to — a top-level `tests/` directory is
code *outside* every package, so the interface rule already forces it through
the public surface. The idiomatic Python layout removes a rule rather than
weakening one, and a passing suite becomes evidence the interface is usable.

**2. `__init__.py` is embraced as the interface, rather than barrels being
discouraged.** The TypeScript objection to barrel files is a bundler
objection: they defeat tree-shaking and drag unrelated code into every
importer. Neither cost exists in Python, where `__init__.py` executes on any
import into the package regardless. The one cost that *does* transfer is an
unbounded public surface — and that is addressed directly, by forbidding star
re-exports: `from ._internal import *` makes the surface unenumerable, which is
the one thing this whole exercise is buying. Explicit names and `__all__` keep
it readable in a single pass.

Both follow the same principle: port the *idea* — a small, enumerable,
mechanically-enforced public surface — not the *mechanism*. The mechanisms are
language-specific and do not survive the crossing. Path-depth matching is the
clearest case: dependency-cruiser can tell `packages/foo/client.ts` from
`packages/foo/lib/impl.ts` by depth, while Python sees `packages.foo.client`
and `packages.foo.lib` at the same dotted depth, with a module and a subpackage
indistinguishable. Hence the underscore rule, which is the convention Python
already has — made binding.

## Licence

MIT. See [LICENSE](./LICENSE).
