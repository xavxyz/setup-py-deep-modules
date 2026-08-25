"""The data the public surface hands back and forth."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LineItem:
    """One priced row on an invoice."""

    description: str
    unit_price_cents: int
    quantity: int = 1


@dataclass(frozen=True)
class Invoice:
    """A set of line items billed to one jurisdiction."""

    jurisdiction: str
    items: tuple[LineItem, ...]
