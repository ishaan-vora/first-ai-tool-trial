# Food Finder

Find restaurant menu items matching a description (e.g. "spicy tonkotsu
ramen"), near an address, within a radius — with distance and price when
available.

## How it works

1. **Yelp Fusion API** finds restaurants near your address within the
   radius (Yelp computes distance for you).
2. For each restaurant, the tool scrapes its Yelp page for a link to its
   own website (Yelp's API doesn't expose this directly).
3. It crawls that website for a menu page or PDF and extracts the text.
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
   (pay-as-you-go; each restaurant checked costs a small fraction of a
   cent using the default Haiku model)
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
- `--verbose` — print per-restaurant progress (website found? menu found? matches?)

## Limitations (read before relying on this)

Menu discovery is **best-effort scraping**, not a guaranteed data source —
there is no public API that returns structured menus for arbitrary
restaurants. You will miss real matches when:

- A restaurant has no website on file with Yelp, or Yelp's page layout
  changed and the website link couldn't be found.
- The menu is only on a third-party app (DoorDash, Uber Eats, Grubhub)
  with no menu on the restaurant's own site.
- The menu is an image (not text) inside a PDF, or requires JavaScript to
  render (this tool doesn't run a browser).
- The site's `robots.txt` disallows fetching the menu page (respected
  automatically).

Treat results as a helpful shortlist, not an exhaustive guarantee. Larger
radii and more restaurants also mean more Anthropic API calls (cost) and
longer run times.
