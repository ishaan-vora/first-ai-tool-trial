"""Best-effort parsing of scraped price text into a comparable number."""

import re

_PRICE_PATTERN = re.compile(r"(\d+(?:\.\d{1,2})?)")


def parse_price(price_text) -> float:
    """Parse a price string like "$14.99" or "$12 - $15" into a float.

    For a range, returns the lower bound. Returns None if no number could
    be found (e.g. the price text is missing, or something unparseable
    like "MP" for market price).
    """
    if not price_text:
        return None
    match = _PRICE_PATTERN.search(str(price_text).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None
