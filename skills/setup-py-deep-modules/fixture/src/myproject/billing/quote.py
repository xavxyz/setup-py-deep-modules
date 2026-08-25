"""A second public entry point, alongside ``__init__.py``.

A package may expose more than one public module. What makes this one public is
only that its name does not start with an underscore -- and being inside the
package, it may use ``_internal`` freely, which no outside module can.
"""

from ._internal._invoice import Invoice, LineItem
from ._internal._tax import rate_for
from ._internal._totals import total_due


def estimate(jurisdiction: str, unit_price_cents: int, quantity: int) -> int:
    """Return what a single-line invoice would cost, without raising one."""
    invoice = Invoice(
        jurisdiction=jurisdiction,
        items=(LineItem(description="Estimate", unit_price_cents=unit_price_cents, quantity=quantity),),
    )
    return total_due(invoice)


def taxed(jurisdiction: str) -> bool:
    """Whether ``jurisdiction`` attracts any tax at all."""
    return rate_for(jurisdiction) > 0
