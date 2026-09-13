# Food Finder

Find restaurant menu items matching a description (e.g. "spicy tonkotsu
ramen"), near an address, within a radius — with distance and price when
available.

## How it works

1. **Yelp Fusion API** finds restaurants near your address within the
   radius (Yelp computes distance for you).
2. For each restaurant, **Claude's web search tool** looks up the best URL
   for its menu — preferring the restaurant's own site, falling back to a
   delivery app (DoorDash/Uber Eats/Grubhub) listing if that's all that's
   findable.
3. The tool fetches that page (or PDF) and extracts the text, following a
   couple of linked menu pages on the same site if there are any.
4. **Claude** reads the scraped menu text and pulls out any items matching
   your description, with price if the menu shows one.
5. Results are sorted by distance and printed to the terminal.

## Setup

1. Python 3.10+, then:
   ```
   pip install -r requirements.txt
   ```
2. Get a **free** Yelp Fusion API key: https://www.yelp.com/developers/v3/manage_app
   (free tier: 500 calls/day)
3. Get an **Anthropic API key**: https://console.anthropic.com/
   (pay-as-you-go; the default Haiku model keeps token costs low, but each
   restaurant now makes two Claude calls — one to search for its menu,
   one to read it — and the web search tool carries its own small
   per-search fee on top of token costs; check Anthropic's current
   pricing page for the exact rate)
4. Copy the example env file and fill in your keys:
   ```
   cp .env.example .env
   ```

## Usage

```
python main.py --address "1600 Amphitheatre Parkway, Mountain View, CA" \
  --radius 3 \
  --query "spicy tonkotsu ramen"
```

Options:
- `--radius` — search radius in miles (Yelp caps this at ~24.85 miles)
- `--max-results` — max restaurants to check (default 100)
- `--concurrency` — restaurants processed in parallel (default 5)
- `--verbose` — print per-restaurant progress (menu page found? menu text found? matches?)

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

Treat results as a helpful shortlist, not an exhaustive guarantee. Larger
radii and more restaurants also mean more Anthropic API calls (cost) and
longer run times.
