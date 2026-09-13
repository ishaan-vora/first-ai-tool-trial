"""Use Claude to find menu items matching a free-text food description."""

import json
import re

import anthropic

from . import config

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


PROMPT_TEMPLATE = """A customer is looking for a dish matching this \
description: "{food_query}"

Treat every distinct food/ingredient component explicitly named in that \
description as REQUIRED. A menu item only qualifies if its name or \
description indicates it contains ALL of those required components -- \
extra ingredients beyond what's required are fine. For example, if the \
customer asked for "pasta with shrimp": a dish described as "pasta with \
shrimp and mussels" qualifies (it has both required components, plus an \
extra one), but "pasta with chicken" does not qualify (it's missing \
shrimp), and "shrimp cocktail" does not qualify (it's missing pasta). \
Reasonable synonyms count (e.g. "prawns" for "shrimp"), but do not \
include an item that is missing any required component.

Below is raw text scraped from the website of a restaurant called \
"{restaurant_name}". It may include navigation clutter, descriptions, and \
prices, and may be incomplete or messy.

---
{menu_text}
---

Return ONLY a JSON array (no markdown fences, no commentary) of menu items \
from this text that contain ALL required components per the rule above. \
Each element must look like:
{{"item_name": "<name as written on the menu>", "price": "<price as \
written, or null if not shown>"}}

If nothing qualifies, return []."""


def _parse_json_array(text: str) -> list:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return []


def find_matching_items(restaurant_name: str, menu_text: str, food_query: str) -> list:
    """Return a list of {item_name, price} dicts matching food_query."""
    if not menu_text.strip():
        return []

    client = _get_client()
    prompt = PROMPT_TEMPLATE.format(
        food_query=food_query,
        restaurant_name=restaurant_name,
        menu_text=menu_text,
    )

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    items = _parse_json_array(text)

    cleaned = []
    for item in items:
        if isinstance(item, dict) and item.get("item_name"):
            cleaned.append(
                {
                    "item_name": str(item["item_name"]),
                    "price": item.get("price"),
                }
            )
    return cleaned
