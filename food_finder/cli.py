import argparse
import re
import sys

from .session import SearchSession


def _price_tier(restaurant):
    return restaurant.price or "n/a"


def print_main_results(session):
    print()
    qualifying = session.display_qualifying()
    budget_note = f", ${session.max_price:.2f} or under" if session.max_price is not None else ""

    if not qualifying:
        print(
            f'No qualifying menu items found for "{session.food_query}"'
            f'{budget_note} within {session.radius_miles} mi of '
            f'"{session.address}".'
        )
    else:
        print(
            f'Results for "{session.food_query}"{budget_note} within '
            f'{session.radius_miles} mi of "{session.address}" '
            f"(top {len(qualifying)} restaurant(s), sorted by {session.sort_by}):\n"
        )
        for i, q in enumerate(qualifying, 1):
            r = q["restaurant"]
            rating_note = f" — {r.rating}★" if r.rating else ""
            print(
                f"{i}. {r.name} — {r.distance_miles} mi — "
                f"price tier: {_price_tier(r)}{rating_note}"
            )
            for item in q["items"]:
                print(f"   • {item['item_name']} — ${item['price_value']:.2f}")
            print(f"   source: {q['items'][0]['menu_url']}")

    honorable = session.display_honorable()
    print("\n--- No Price Found ---")
    if not honorable:
        print("(none)")
    else:
        for i, h in enumerate(honorable, 1):
            r = h["restaurant"]
            item = h["item"]
            print(
                f"{i}. {item['item_name']} — {r.name} — {r.distance_miles} mi — "
                f"price tier: {_price_tier(r)}"
            )
            print(f"   source: {item['menu_url']}")


FOLLOW_UP_HELP = (
    'Follow-up commands: "more restaurants [N]", "more items [N]", '
    '"sort by rating", "sort by distance", or press Enter to quit.'
)


def follow_up_loop(session):
    if not sys.stdin.isatty():
        return

    print(f"\n{FOLLOW_UP_HELP}")
    while True:
        try:
            command = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not command or command in ("quit", "exit", "done"):
            break

        num_match = re.search(r"\d+", command)
        n = int(num_match.group()) if num_match else None

        if "restaurant" in command or "place" in command:
            session.restaurant_cap += n or 3
            session.expand(target_qualifying=session.restaurant_cap)
            print_main_results(session)
        elif "item" in command or "mention" in command or "menu" in command:
            session.honorable_cap += n or 5
            if len(session.honorable) < session.honorable_cap and not session.exhausted:
                session.expand(target_qualifying=session.restaurant_cap)
            print_main_results(session)
        elif "rating" in command:
            session.sort_by = "rating"
            print_main_results(session)
        elif "distance" in command or "proximity" in command or "closest" in command or "near" in command:
            session.sort_by = "distance"
            print_main_results(session)
        else:
            print(f"Sorry, I didn't understand that. {FOLLOW_UP_HELP}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find restaurant menu items matching a description, near an "
            "address, within a radius and budget."
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
        "--max-price",
        type=float,
        default=None,
        help="Only include menu items priced at or below this amount (default: no limit)",
    )
    parser.add_argument(
        "--restaurant-cap",
        type=int,
        default=7,
        help="Stop once this many restaurants have a qualifying item (default: 7)",
    )
    parser.add_argument(
        "--honorable-cap",
        type=int,
        default=5,
        help='Max items to show in the "No Price Found" section (default: 5)',
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Max number of open restaurants to pull from Yelp to search through (default: 100)",
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
    parser.add_argument(
        "--no-follow-up",
        action="store_true",
        help="Skip the interactive follow-up prompt after showing results",
    )
    args = parser.parse_args()

    session = SearchSession(
        address=args.address,
        radius_miles=args.radius,
        food_query=args.query,
        max_price=args.max_price,
        max_results=args.max_results,
        concurrency=args.concurrency,
        restaurant_cap=args.restaurant_cap,
        honorable_cap=args.honorable_cap,
        verbose=args.verbose,
    )

    try:
        session.expand()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print_main_results(session)

    if not args.no_follow_up:
        follow_up_loop(session)


if __name__ == "__main__":
    main()
