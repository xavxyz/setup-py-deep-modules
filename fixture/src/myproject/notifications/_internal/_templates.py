"""Message bodies."""

from myproject.billing import Invoice, format_amount, total_due


def invoice_ready(invoice: Invoice, currency: str = "EUR") -> str:
    """Return the notification body announcing ``invoice`` is ready to pay."""
    count = len(invoice.items)
    noun = "item" if count == 1 else "items"
    return (
        f"Your invoice for {count} {noun} is ready. "
        f"Total due: {format_amount(total_due(invoice))} {currency}."
    )
