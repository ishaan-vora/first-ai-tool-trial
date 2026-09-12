import os

from dotenv import load_dotenv

load_dotenv()

YELP_API_KEY = os.environ.get("YELP_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

USER_AGENT = (
    "Mozilla/5.0 (compatible; FoodFinderBot/1.0; "
    "personal menu-search tool; +https://github.com/)"
)

REQUEST_TIMEOUT_SECONDS = 10
YELP_MAX_RADIUS_METERS = 40000  # Yelp Fusion API hard limit (~24.85 miles)
