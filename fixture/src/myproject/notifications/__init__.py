"""Customer-facing invoice messages.

Consumes :mod:`myproject.billing` through its public surface only — the same
rule that applies to every other consumer applies here.
"""

from ._internal._templates import invoice_ready

__all__ = ["invoice_ready"]
