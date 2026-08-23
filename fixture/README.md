# The fixture

A small Python project whose only job is to prove that `tach.toml` in this
directory enforces the rule the plugin is built around: **private means a name
starting with `_`**. CI runs the proof on every push and on a schedule.

The same project is the copy-me example the skill scaffolds in a user's repo, so
it is written and maintained once and cannot drift from what users are told to
copy.

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
tach check     # from this directory
pytest         # the fixture's own tests, written against the interfaces
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
the one the imports actually form.** Under the generic globbed `[[modules]]`
block nothing is declared, so on its own the setting never fires. The proof
suite materialises the graph first -- expanding the glob and running `tach sync`
against a scratch copy -- which is what makes cycles fail. That step needs
nothing from the user beyond the directory listing, but it is a step, and
`tests/test_cycles.py` pins the tach behaviour that forces it so the scheduled
run tells us if a release removes the need.
