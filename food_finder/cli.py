import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import menu_fetcher, menu_matcher, website_finder, yelp_client


def _process_restaurant(restaurant, food_query, verbose):
    website = website_finder.find_website(restaurant.yelp_url)
    if not website:
        if verbose:
            print(f"  [skip] {restaurant.name}: no website found", file=sys.stderr)
        return []

    menu_text = menu_fetcher.fetch_menu_text(website)
    if not menu_text:
        if verbose:
            print(f"  [skip] {restaurant.name}: no menu text found", file=sys.stderr)
        return []

    matches = menu_matcher.find_matching_items(restaurant.name, menu_text, food_query)
    if verbose:
        print(
            f"  [ok] {restaurant.name}: {len(matches)} match(es)",
            file=sys.stderr,
        )

    return [
        {
            "restaurant": restaurant.name,
            "distance_miles": restaurant.distance_miles,
            "item_name": m["item_name"],
            "price": m["price"],
            "source": website,
        }
        for m in matches
    ]


def run(address, radius_miles, food_query, max_results, concurrency, verbose):
    print(
        f'Searching for restaurants within {radius_miles} mi of "{address}"...',
        file=sys.stderr,
    )
    restaurants = yelp_client.search_restaurants(
        address, radius_miles, max_results=max_results
    )
    print(f"Found {len(restaurants)} restaurant(s). Checking menus...", file=sys.stderr)

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(_process_restaurant, r, food_query, verbose): r
            for r in restaurants
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            if not verbose:
                print(f"  ...{done}/{len(restaurants)}", end="\r", file=sys.stderr)
            try:
                results.extend(future.result())
            except Exception as exc:
                r = futures[future]
                print(f"  [error] {r.name}: {exc}", file=sys.stderr)

    if not verbose:
        print(file=sys.stderr)

    results.sort(key=lambda r: r["distance_miles"])
    return results


def print_results(results, food_query, address, radius_miles):
    if not results:
        print(
            f'\nNo matches found for "{food_query}" within {radius_miles} mi '
            f'of "{address}".'
        )
        return

    print(
        f'\nFound {len(results)} matching item(s) for "{food_query}" within '
        f'{radius_miles} mi of "{address}":\n'
    )
    for i, r in enumerate(results, 1):
        price = f" — {r['price']}" if r["price"] else ""
        print(f"{i}. {r['item_name']} — {r['restaurant']} — {r['distance_miles']} mi{price}")
        print(f"   source: {r['source']}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find restaurant menu items matching a description, near an "
            "address, within a radius."
        )
    )
    parser.add_argument("--address", required=True, help="Address to search around")
    parser.add_argument(
        "--radius", required=True, type=float, help="Search radius in miles"
    )
    parser.add_argument(
        "--query", required=True, help="Description of the food you're looking for"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Max number of restaurants to check (default: 100)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Number of restaurants to process in parallel (default: 5)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print per-restaurant progress"
    )
    args = parser.parse_args()

    try:
        results = run(
            args.address,
            args.radius,
            args.query,
            args.max_results,
            args.concurrency,
            args.verbose,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print_results(results, args.query, args.address, args.radius)


if __name__ == "__main__":
    main()
