# Food Finder

Find restaurant menu items matching a description (e.g. "pasta with
shrimp"), near an address, within a radius and budget — with distance,
price, and Yelp price tier.

## How it works

1. **Yelp Fusion API** finds currently-*open* restaurants near your
   address within the radius, sorted by distance (Yelp computes distance
   and filters closed restaurants for us, before any Claude call is
   spent).
2. For each restaurant, **Claude's web search tool** looks up the best URL
   for its menu — preferring the restaurant's own site, falling back to a
   delivery app (DoorDash/Uber Eats/Grubhub) listing if that's all that's
   findable.
3. The tool fetches that page (or PDF) and extracts the text, following a
   couple of linked menu pages on the same site if there are any.
4. **Claude** reads the scraped menu text and pulls out any items that
   contain **all** the components you named (ingredient-level matching —
   see below), with price if the menu shows one.
5. Matches are filtered by your budget, then results are capped and
   sorted, and printed to the terminal. You can then issue **follow-up
   commands** to expand or re-sort without starting over.

### Cost-saving stopping rule

Restaurants are checked in distance order, and the search **stops as soon
as enough restaurants have a qualifying match** (default: 7) rather than
checking every restaurant in the radius — this is the main lever for
keeping Claude usage down on a big radius. Combined with the open-now
filter (closed restaurants never even get a Claude call), this keeps
typical runs to a small, bounded number of API calls regardless of how
many restaurants are technically in range.

### Ingredient-level matching

Every distinct food/ingredient named in your `--query` is treated as
**required** — a menu item only matches if it contains all of them (extra
ingredients are fine). For example, `--query "pasta with shrimp"`:

- ✅ "Pasta with Shrimp and Mussels" — has both required components, plus an extra one
- ❌ "Pasta with Chicken" — missing shrimp
- ❌ "Shrimp Cocktail" — missing pasta

## Setup

1. Python 3.10+, then:
   ```
   pip install -r requirements.txt
   ```
2. Get a **free** Yelp Fusion API key: https://www.yelp.com/developers/v3/manage_app
   (free tier: 500 calls/day)
3. Get an **Anthropic API key**: https://console.anthropic.com/
   (pay-as-you-go; the default Haiku model keeps token costs low, but each
   restaurant checked makes two Claude calls — one to search for its
   menu, one to read it — and the web search tool carries its own small
   per-search fee on top of token costs; check Anthropic's current
   pricing page for the exact rate. The early-stopping rule above is what
   keeps this bounded.)
4. Copy the example env file and fill in your keys:
   ```
   cp .env.example .env
   ```

## Usage

```
python main.py --address "1600 Amphitheatre Parkway, Mountain View, CA" \
  --radius 3 \
  --query "pasta with shrimp" \
  --max-price 23
```

Options:
- `--radius` — search radius in miles (Yelp caps this at ~24.85 miles)
- `--max-price` — only include menu items priced at or below this amount (default: no limit). Items with a price above this are dropped entirely; items with **no price found at all** go to the "No Price Found" section instead of being dropped.
- `--restaurant-cap` — stop once this many restaurants have a qualifying item (default: 7)
- `--honorable-cap` — max items shown in the "No Price Found" section (default: 5)
- `--max-results` — max open restaurants pulled from Yelp to search through before giving up (default: 100)
- `--concurrency` — restaurants processed in parallel (default 5)
- `--verbose` — print per-restaurant progress (menu page found? menu text found? matches?)
- `--no-follow-up` — skip the interactive follow-up prompt after showing results (useful for scripting)

### Output

- **Main results**: up to `--restaurant-cap` restaurants (closest qualifying restaurants first, or highest-rated first after a "sort by rating" follow-up), each showing distance, Yelp price tier ($/$$/$$$/$$$$), rating if available, and every qualifying item with its price.
- **No Price Found**: up to `--honorable-cap` additional items that matched your query and ingredient criteria but had no price found on the menu — these aren't limited to the restaurants already shown in the main results. Each entry still shows the restaurant's Yelp price tier if available.

### Follow-up commands

After results print, if you're at an interactive terminal, you can type
follow-up commands (reusing already-fetched data wherever possible, so
these are usually free or cheap):

- `more restaurants` / `more restaurants 5` — raise the restaurant cap and keep searching if needed
- `more items` / `more items 10` — raise the "No Price Found" cap
- `sort by rating` — re-sort current results by Yelp rating (no new API calls)
- `sort by distance` — back to closest-first (no new API calls)
- press Enter (or `quit`/`exit`) to end

## Limitations (read before relying on this)

Menu discovery is **best-effort**, not a guaranteed data source — there is
no public API that returns structured menus for arbitrary restaurants. You
will miss real matches when:

- Claude's web search can't find any page with the restaurant's menu on it.
- The menu is only on a delivery app (DoorDash, Uber Eats, Grubhub) and
  that page is JavaScript-rendered — this tool fetches raw HTML and
  doesn't run a browser, so heavily JS-rendered pages may come back with
  little or no menu text even though the URL was found correctly.
- The menu is an image (not text) inside a PDF.
- The site's `robots.txt` disallows fetching the menu page (respected
  automatically).
- A price is written in a form the parser can't read (e.g. "Market Price")
  — these are treated as "no price found," not excluded.

Because restaurants are processed with some concurrency, the search may
check a couple of extra restaurants past the cap before stopping (their
results are still counted, then trimmed back to the closest N at display
time) — a small, bounded overshoot rather than a hard cutoff mid-restaurant.

Treat results as a helpful shortlist, not an exhaustive guarantee.
