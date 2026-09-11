"""Search for nearby restaurants using the Yelp Fusion API."""

from dataclasses import dataclass
from typing import Optional

import requests

from . import config

YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
PAGE_LIMIT = 50  # Yelp's per-request max


@dataclass
class Restaurant:
    yelp_id: str
    name: str
    yelp_url: str
    address: str
    phone: str
    distance_miles: float
    price: Optional[str]
    categories: list


def _meters_to_miles(meters: float) -> float:
    return meters / 1609.344


def search_restaurants(
    address: str,
    radius_miles: float,
    max_results: int = 150,
) -> list:
    """Return restaurants near `address` within `radius_miles`.

    Yelp caps radius at ~24.85 miles and results at 1000 total (50/page).
    """
    if not config.YELP_API_KEY:
        raise RuntimeError(
            "YELP_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    radius_meters = min(int(radius_miles * 1609.344), config.YELP_MAX_RADIUS_METERS)
    headers = {"Authorization": f"Bearer {config.YELP_API_KEY}"}

    restaurants = []
    offset = 0
    total = None

    while len(restaurants) < max_results:
        if total is not None and offset >= total:
            break

        params = {
            "location": address,
            "radius": radius_meters,
            "categories": "restaurants,food",
            "limit": min(PAGE_LIMIT, max_results - len(restaurants)),
            "offset": offset,
            "sort_by": "distance",
        }
        resp = requests.get(
            YELP_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Yelp API error {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        total = data.get("total", 0)
        businesses = data.get("businesses", [])
        if not businesses:
            break

        for b in businesses:
            restaurants.append(
                Restaurant(
                    yelp_id=b.get("id", ""),
                    name=b.get("name", "Unknown"),
                    yelp_url=b.get("url", "").split("?")[0],
                    address=", ".join(
                        b.get("location", {}).get("display_address", [])
                    ),
                    phone=b.get("display_phone", ""),
                    distance_miles=round(
                        _meters_to_miles(b.get("distance", 0)), 2
                    ),
                    price=b.get("price"),
                    categories=[
                        c.get("title") for c in b.get("categories", [])
                    ],
                )
            )

        offset += len(businesses)

    return restaurants[:max_results]
