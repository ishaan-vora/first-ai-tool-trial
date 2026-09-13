"""Stateful search session.

Keeps every restaurant checked so far, and every match found, in memory so
follow-up requests ("show more restaurants", "sort by rating") can be
served by re-slicing/re-sorting data already fetched instead of re-running
Yelp search or re-reading menus with Claude wherever possible -- expanding
only calls the API again when there genuinely isn't enough banked data yet.

Also owns the cost-saving stopping rule: restaurants are processed in
distance order (Yelp already sorts that way) and the search stops as soon
as `restaurant_cap` distinct restaurants have at least one budget-qualifying
match, rather than checking every restaurant in the radius.
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import menu_fetcher, menu_matcher, menu_search, yelp_client
from .pricing import parse_price


def _process_restaurant(restaurant, food_query, verbose):
    menu_url = menu_search.find_menu_url(restaurant.name, restaurant.address)
    if not menu_url:
        if verbose:
            print(f"  [skip] {restaurant.name}: no menu page found", file=sys.stderr)
        return []

    menu_text = menu_fetcher.fetch_menu_text(menu_url)
    if not menu_text:
        if verbose:
            print(f"  [skip] {restaurant.name}: no menu text found", file=sys.stderr)
        return []

    matches = menu_matcher.find_matching_items(restaurant.name, menu_text, food_query)
    if verbose:
        print(f"  [ok] {restaurant.name}: {len(matches)} match(es)", file=sys.stderr)

    return [
        {"item_name": m["item_name"], "price_text": m["price"], "menu_url": menu_url}
        for m in matches
    ]


class SearchSession:
    def __init__(
        self,
        address,
        radius_miles,
        food_query,
        max_price=None,
        max_results=100,
        concurrency=5,
        restaurant_cap=7,
        honorable_cap=5,
        verbose=False,
    ):
        self.address = address
        self.radius_miles = radius_miles
        self.food_query = food_query
        self.max_price = max_price
        self.max_results = max_results
        self.concurrency = concurrency
        self.restaurant_cap = restaurant_cap
        self.honorable_cap = honorable_cap
        self.verbose = verbose
        self.sort_by = "distance"  # or "rating"

        self._restaurant_iter = None
        self.exhausted = False

        # Uncapped accumulators -- caps are applied only at display time,
        # so raising a cap on a follow-up can often be served from here
        # with no further API calls.
        self.qualifying = []  # [{"restaurant": Restaurant, "items": [...]}]
        self.honorable = []  # [{"restaurant": Restaurant, "item": {...}}]

    def _load_restaurants(self):
        if self._restaurant_iter is not None:
            return
        print(
            f'Searching for open restaurants within {self.radius_miles} mi '
            f'of "{self.address}"...',
            file=sys.stderr,
        )
        restaurants = yelp_client.search_restaurants(
            self.address,
            self.radius_miles,
            max_results=self.max_results,
            open_now=True,
        )
        print(f"Found {len(restaurants)} open restaurant(s). Checking menus...", file=sys.stderr)
        self._restaurant_iter = iter(restaurants)

    def _record(self, restaurant, matches):
        priced_in_budget = []
        for m in matches:
            price_value = parse_price(m["price_text"])
            if price_value is not None:
                if self.max_price is None or price_value <= self.max_price:
                    priced_in_budget.append({**m, "price_value": price_value})
                # else: has a price, but over budget -- dropped entirely,
                # not shown anywhere.
            else:
                self.honorable.append({"restaurant": restaurant, "item": m})

        if priced_in_budget:
            self.qualifying.append({"restaurant": restaurant, "items": priced_in_budget})

    def expand(self, target_qualifying=None):
        """Process more restaurants until `target_qualifying` distinct
        restaurants have a budget-qualifying match, or restaurants run out.

        Restaurants already in flight when the target is reached are still
        recorded (their cost is already spent) but no new ones are started.
        """
        target = target_qualifying if target_qualifying is not None else self.restaurant_cap
        self._load_restaurants()

        if self.exhausted or len(self.qualifying) >= target:
            return

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            pending = {}

            def submit_next():
                try:
                    r = next(self._restaurant_iter)
                except StopIteration:
                    self.exhausted = True
                    return None
                fut = pool.submit(_process_restaurant, r, self.food_query, self.verbose)
                pending[fut] = r
                return fut

            for _ in range(self.concurrency):
                if submit_next() is None:
                    break

            while pending and len(self.qualifying) < target:
                fut = next(as_completed(pending))
                r = pending.pop(fut)
                try:
                    matches = fut.result()
                except Exception as exc:
                    print(f"  [error] {r.name}: {exc}", file=sys.stderr)
                    matches = []
                self._record(r, matches)
                if len(self.qualifying) < target:
                    submit_next()

            # Drain whatever was already in flight when the target was hit --
            # that cost is already spent, so keep the results.
            for fut in as_completed(list(pending.keys())):
                r = pending.pop(fut)
                try:
                    matches = fut.result()
                except Exception as exc:
                    print(f"  [error] {r.name}: {exc}", file=sys.stderr)
                    matches = []
                self._record(r, matches)

    def _sort_key(self, restaurant):
        if self.sort_by == "rating":
            return (-(restaurant.rating or 0), restaurant.distance_miles)
        return (restaurant.distance_miles,)

    def display_qualifying(self):
        ordered = sorted(self.qualifying, key=lambda q: self._sort_key(q["restaurant"]))
        return ordered[: self.restaurant_cap]

    def display_honorable(self):
        ordered = sorted(self.honorable, key=lambda h: self._sort_key(h["restaurant"]))
        return ordered[: self.honorable_cap]
