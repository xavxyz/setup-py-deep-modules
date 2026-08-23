"""A package's further entry points are public too, on the same rule: their names
do not start with an underscore."""

from myproject.billing.quote import estimate, taxed


def test_estimate_prices_a_line_without_raising_an_invoice():
    assert estimate("FR", unit_price_cents=25_000, quantity=3) == 90_000


def test_taxed_distinguishes_known_from_unknown_jurisdictions():
    assert taxed("FR") is True
    assert taxed("ZZ") is False
