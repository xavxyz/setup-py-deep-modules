"""Exercises one package's interface being consumed through another's."""

from myproject.app import demo
from myproject.billing import Invoice, LineItem
from myproject.notifications import invoice_ready


def test_invoice_ready_names_the_item_count_and_total():
    invoice = Invoice(
        jurisdiction="FR",
        items=(LineItem(description="Consulting", unit_price_cents=25_000, quantity=3),),
    )
    assert invoice_ready(invoice) == "Your invoice for 1 item is ready. Total due: 900.00 EUR."


def test_demo_wires_the_two_packages_together():
    assert demo().endswith("900.00 EUR.")
