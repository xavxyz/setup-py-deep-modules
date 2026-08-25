# The fixture

A small Python project whose only job is to prove that `tach.toml` in this
directory enforces the rule the plugin is built around: **private means a name
starting with `_`**. CI runs the proof on every push and on a schedule.

The same project is the copy-me example the skill scaffolds in a user's repo, so
it is written and maintained once and cannot drift from what users are told to
copy. That is literal: `skills/setup-py-deep-modules/scripts/setup_deep_modules.py`
reads this directory at runtime -- the `tach.toml` here is what it renders into a
user's repo, `billing/` is what it copies in, and `pyproject.toml` here is where
it reads the tach pin from. Editing the fixture edits the skill's output.

## The shape to copy

```
src/myproject/
  app.py                      loose application code -- no interface required
  billing/
    __init__.py               the public surface: named re-exports + __all__
    quote.py                  a further public entry point -- no leading _
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
```

`billing/__init__.py` is the whole of what a consumer -- human or agent -- needs
to read to use the package. Reaching past it fails `tach check`, so that reading
can be trusted.

A package may have more than one public entry point: `billing/quote.py` is public
for the same reason `__init__.py` is, namely that its name does not start with an
underscore. Being inside the package, it may use `_internal` freely -- the rule
governs crossing a boundary, not working within one.

## Running the proof

```sh
uv pip install -r pyproject.toml --extra dev
tach check                       # from this directory
python scripts/check_cycles.py   # no cycles between packages
pytest                           # the fixture's own tests, via the interfaces
```

The full pass/fail/pass proof lives in `../tests/`, and runs against throwaway
copies of this directory:

```sh
pytest tests -q     # from the repo root
```

## Two things about tach worth knowing before you edit the config

**Its default `exclude` list contains `**/tests`.** Leaving it at the default
means the top-level test suite is never looked at, and the config passes while
tests reach freely into package internals. `tach.toml` here restates the list
without that entry, which is what puts tests under the same rule as any other
consumer.

**`forbid_circular_dependencies` checks the graph declared in `tach.toml`, not
the one the imports actually form.** The generic rule declares no `depends_on`
at all -- that is the point of it -- so on its own the setting never sees a real
cycle. It is left set because it starts holding the moment you fill in the
layering stub, but it is not what rejects cycles today.

`scripts/check_cycles.py` is. It reads the real graph from `tach map`, collapses
it to the package tier and fails on any cycle, needing no per-package
configuration of its own -- so the no-config-edits property survives. Run it
alongside `tach check`; CI runs both.

`tests/test_cycles.py` pins the tach behaviour that makes the extra command
necessary, so the scheduled run tells us if a release removes the need for it.
