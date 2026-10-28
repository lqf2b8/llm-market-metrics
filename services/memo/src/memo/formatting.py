"""Display strings for the facts file. The memo may use these strings and nothing else, so
formatting lives in one place and the number check knows exactly what is allowed."""

from __future__ import annotations


def money(value: float) -> str:
    """$176.9M, $1.2B, $950K, $12. Amounts under 50 cents are $0, with no sign."""
    if abs(value) < 0.5:
        return "$0"
    sign = "-" if value < 0 else ""
    v = abs(value)
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= threshold:
            return f"{sign}${v / threshold:.1f}{suffix}"
    return f"{sign}${v:.0f}"


def signed_money(value: float) -> str:
    text = money(value)
    return text if text == "$0" or text.startswith("-") else "+" + text


def tokens(value: float) -> str:
    """188.0T, 950.2B tokens."""
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= threshold:
            return f"{value / threshold:.1f}{suffix}"
    return f"{value:,.0f}"


def pct(share: float | None) -> str | None:
    """A share (0.133) as 13.3%."""
    return None if share is None else f"{share * 100:.1f}%"


def signed_pct(change: float | None) -> str | None:
    """A change (0.112) as +11.2%."""
    return None if change is None else f"{change * 100:+.1f}%"


def points(diff: float | None) -> str | None:
    """A difference of two shares (0.004) as +0.4 pp."""
    return None if diff is None else f"{diff * 100:+.1f} pp"


def price(usd_per_mtok: float | None) -> str | None:
    return None if usd_per_mtok is None else f"${usd_per_mtok:.2f} per million tokens"
