"""Use Claude's web search tool to find a restaurant's menu page.

Replaces scraping Yelp's business page for a website link -- instead we ask
Claude to search the web directly for the restaurant's menu, which also
finds menus hosted on delivery apps (DoorDash, Uber Eats, Grubhub) when the
restaurant has no usable website of its own.
"""

import re

import anthropic

from . import config

URL_PATTERN = re.compile(r"https?://[^\s)\]}\"'<>]+")

_client = None


def _get_client():
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env "
                "and fill it in."
            )
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


SEARCH_PROMPT = """Search the web to find the best URL for the online menu \
of this restaurant:

Name: {name}
Address: {address}

Prefer the restaurant's own website menu page. A menu page on a delivery \
app (DoorDash, Uber Eats, Grubhub) is acceptable if you can't find one on \
the restaurant's own site.

Once you've decided on the best URL, give your final answer as a line \
containing ONLY that URL and nothing else -- no commentary before or after \
it on that line. If you can't find a usable menu page, give a final \
answer of exactly: NONE"""


def find_menu_url(restaurant_name: str, address: str) -> str:
    """Return a URL likely to show this restaurant's menu, or "" if none found."""
    client = _get_client()

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[
            {
                "role": "user",
                "content": SEARCH_PROMPT.format(
                    name=restaurant_name, address=address
                ),
            }
        ],
    )

    # Claude may narrate its search in earlier text blocks and add
    # commentary alongside the final answer, so pull the last URL out of
    # the last text block rather than assuming a clean one-line answer.
    text_blocks = [b.text for b in response.content if b.type == "text"]
    final_text = text_blocks[-1].strip() if text_blocks else ""

    if not final_text or final_text.strip().upper() == "NONE":
        return ""

    urls = URL_PATTERN.findall(final_text)
    if not urls:
        return ""
    return urls[-1].rstrip(".,;:")
