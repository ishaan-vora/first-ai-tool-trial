import argparse
import sys

from . import intent, request_parser
from .session import SearchSession

MAX_CLARIFICATION_ROUNDS = 5


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
    "Follow-up commands: plain English is fine, e.g. \"show me a few more "
    'places", "any more options?", "sort by rating", "back to closest '
    'first" -- or press Enter to quit.'
)


def follow_up_loop(session):
    if not sys.stdin.isatty():
        return

    print(f"\n{FOLLOW_UP_HELP}")
    while True:
        try:
            command = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not command or command.lower() in ("quit", "exit", "done"):
            break

        try:
            action, count = intent.classify_follow_up(command)
        except RuntimeError as exc:
            print(f"Error: {exc}")
            continue
        except Exception as exc:
            print(f"Couldn't interpret that ({exc}); try rephrasing.")
            continue

        if action == "more_restaurants":
            session.restaurant_cap += count or 3
            session.expand(target_qualifying=session.restaurant_cap)
            print_main_results(session)
        elif action == "more_items":
            session.honorable_cap += count or 5
            if len(session.honorable) < session.honorable_cap and not session.exhausted:
                session.expand(target_qualifying=session.restaurant_cap)
            print_main_results(session)
        elif action == "sort_rating":
            session.sort_by = "rating"
            print_main_results(session)
        elif action == "sort_distance":
            session.sort_by = "distance"
            print_main_results(session)
        elif action == "quit":
            break
        else:
            print(f"Sorry, I didn't understand that. {FOLLOW_UP_HELP}")


def gather_request(initial_text):
    """Repeatedly parse free text with Claude, asking for whatever required
    field is still missing, until address/radius/food_query are all known."""
    raw_text = initial_text.strip()
    if not raw_text:
        try:
            raw_text = input("What are you looking for? ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)

    for _ in range(MAX_CLARIFICATION_ROUNDS):
        parsed = request_parser.parse_request(raw_text)
        missing = request_parser.missing_required_fields(parsed)
        if not missing:
            return parsed

        needed = " and ".join(
            request_parser.FIELD_LABELS[f] for f in missing
        )
        print(f"\nI still need {needed}. Could you tell me?")
        try:
            clarification = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        raw_text = f"{raw_text}\n{clarification}"

    print(
        "Error: couldn't get enough information after several tries.",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find restaurant menu items matching a plain-language request, "
            'e.g. "pasta with shrimp near 1600 Amphitheatre Parkway, '
            'Mountain View, within 3 miles, under $23".'
        )
    )
    parser.add_argument(
        "request",
        nargs="*",
        help=(
            "Describe what you want in plain language: address, radius, "
            "food, budget, and whether to only show open restaurants. "
            "If omitted, you'll be prompted. Quote it as one argument if "
            "it contains characters your shell might mangle."
        ),
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
        help="Max number of restaurants to pull from Yelp to search through (default: 100)",
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

    initial_text = " ".join(args.request)

    try:
        parsed = gather_request(initial_text)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    budget_note = f", budget ${parsed['max_price']:.2f}" if parsed["max_price"] is not None else ""
    open_note = ", open now only" if parsed["open_now"] else ""
    print(
        f'Got it — searching for "{parsed["food_query"]}" near '
        f'"{parsed["address"]}" within {parsed["radius_miles"]} mi'
        f"{budget_note}{open_note}.",
        file=sys.stderr,
    )

    session = SearchSession(
        address=parsed["address"],
        radius_miles=parsed["radius_miles"],
        food_query=parsed["food_query"],
        max_price=parsed["max_price"],
        max_results=args.max_results,
        concurrency=args.concurrency,
        restaurant_cap=args.restaurant_cap,
        honorable_cap=args.honorable_cap,
        open_now=parsed["open_now"],
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
