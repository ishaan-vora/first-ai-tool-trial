"""Use Claude to interpret free-text follow-up commands.

Keeps the follow-up prompt tolerant of plain English ("can I see a few
more places nearby?") instead of requiring exact keywords. One cheap
Haiku call per follow-up -- small and bounded, unlike the main search
which can process many restaurants.
"""

import json
import re

from . import anthropic_client, config

ACTIONS = {
    "more_restaurants",
    "more_items",
    "sort_rating",
    "sort_distance",
    "quit",
    "unknown",
}

INTENT_PROMPT = """A user is interacting with a restaurant menu search \
tool and just typed this follow-up request:

"{command}"

Classify it into exactly one of these actions:
- "more_restaurants": they want to see more restaurants/places/results in the main list
- "more_items": they want to see more items in the "No Price Found" section
- "sort_rating": they want results sorted/ranked by rating instead of distance
- "sort_distance": they want results sorted by distance/proximity/closeness instead of rating
- "quit": they want to stop or exit
- "unknown": anything else, including requests this tool can't do (e.g. \
changing the food query, address, radius, or budget)

If they mentioned a specific number (e.g. "show 5 more restaurants"), \
extract it as an integer; otherwise use null.

Respond with ONLY a JSON object, no commentary, in exactly this shape:
{{"action": "<one of the actions above>", "count": <integer or null>}}"""


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


def classify_follow_up(command: str):
    """Return (action, count) for a free-text follow-up command.

    `action` is always one of ACTIONS; `count` is an int or None.
    """
    client = anthropic_client.get_client()

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=256,
        messages=[
            {"role": "user", "content": INTENT_PROMPT.format(command=command)}
        ],
    )

    text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    parsed = _parse_json_object(text)

    action = parsed.get("action")
    if action not in ACTIONS:
        action = "unknown"

    count = parsed.get("count")
    if not isinstance(count, int):
        count = None

    return action, count
