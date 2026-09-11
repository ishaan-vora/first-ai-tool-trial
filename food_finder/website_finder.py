"""Best-effort discovery of a restaurant's own website from its Yelp page.

The Yelp Fusion API does not expose a restaurant's website. Yelp's public
business pages link to it through a redirect link (``/biz_redir/...?url=...``).
This is inherently fragile -- Yelp's markup can change, some pages block
scraping, and some businesses simply have no website on file -- so every
failure here is swallowed and just means "no website found" rather than a
hard error.
"""

from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from . import config


def find_website(yelp_url: str) -> str:
    """Return the restaurant's own website URL, or "" if it can't be found."""
    if not yelp_url:
        return ""

    try:
        resp = requests.get(
            yelp_url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            return ""
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/biz_redir/" not in href:
            continue
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        target = qs.get("url")
        if target:
            return target[0]

    return ""
