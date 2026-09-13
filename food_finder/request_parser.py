"""Use Claude to parse a plain-language search request into structured fields."""

import json
import re

from . import anthropic_client, config

REQUIRED_FIELDS = ("address", "radius_miles", "food_query")

FIELD_LABELS = {
    "address": "an address or area to search near",
    "radius_miles": "a search radius in miles",
    "food_query": "what food or dish you're looking for",
}

PARSE_PROMPT = """A user is describing what they want from a restaurant \
menu search tool. Extract structured fields from everything they've said \
so far (this may include a follow-up clarification appended after the \
original request):

---
{raw_text}
---

Extract these fields:
- "address": the address or area to search near, as a plain string (or null if not mentioned anywhere)
- "radius_miles": how far to search, in miles, as a number. Convert other \
units (km, meters) to miles. If only a vague relative term is given (e.g. \
"walking distance", "nearby") with no specific number anywhere, use null.
- "food_query": a description of the food/dish they're looking for, as a \
plain string (or null if not mentioned anywhere)
- "max_price": a maximum price per menu item in US dollars, as a number \
(or null if no budget was mentioned)
- "open_now": true only if they explicitly want restaurants that are \
currently open right now; false otherwise (false is the default)

Respond with ONLY a JSON object, no commentary, in exactly this shape:
{{"address": <string or null>, "radius_miles": <number or null>, \
"food_query": <string or null>, "max_price": <number or null>, \
"open_now": <true or false>}}"""


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {}


def _str_or_none(value):
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def _num_or_none(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def parse_request(raw_text: str) -> dict:
    """Extract address/radius_miles/food_query/max_price/open_now from free text."""
    client = anthropic_client.get_client()

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=512,
        messages=[
            {"role": "user", "content": PARSE_PROMPT.format(raw_text=raw_text)}
        ],
    )

    text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    parsed = _parse_json_object(text)

    return {
        "address": _str_or_none(parsed.get("address")),
        "radius_miles": _num_or_none(parsed.get("radius_miles")),
        "food_query": _str_or_none(parsed.get("food_query")),
        "max_price": _num_or_none(parsed.get("max_price")),
        "open_now": parsed.get("open_now") is True,
    }


def missing_required_fields(parsed: dict) -> list:
    return [f for f in REQUIRED_FIELDS if not parsed.get(f)]
