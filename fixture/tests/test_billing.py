"""Top-level tests are code outside every package, so the interface rule already
forces them through the public surface. No dedicated contract is needed."""

from myproject.billing import Invoice, LineItem, format_amount, total_due


def _invoice(jurisdiction: str) -> Invoice:
    return Invoice(
        jurisdiction=jurisdiction,
        items=(
            LineItem(description="Consulting", unit_price_cents=25_000, quantity=3),
            LineItem(description="Expenses", unit_price_cents=1_234),
        ),
    )


def test_total_due_adds_tax_for_a_known_jurisdiction():
    assert total_due(_invoice("FR")) == 91_481


def test_total_due_is_the_subtotal_for_an_unknown_jurisdiction():
    assert total_due(_invoice("ZZ")) == 76_234


def test_format_amount_renders_whole_and_fractional_units():
    assert format_amount(91_481) == "914.81"
