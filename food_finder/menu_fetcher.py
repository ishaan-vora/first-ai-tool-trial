"""Best-effort crawl of a restaurant website to collect menu text."""

import io
import urllib.robotparser as robotparser
from urllib.parse import urljoin, urlparse

import pdfplumber
import requests
from bs4 import BeautifulSoup

from . import config

MENU_KEYWORDS = ("menu", "order", "food", "eat")
COMMON_MENU_PATHS = (
    "/menu",
    "/menus",
    "/menu.pdf",
    "/our-menu",
    "/food-menu",
    "/order",
)
MAX_CANDIDATE_PAGES = 5
MAX_TOTAL_CHARS = 20000

_robots_cache = {}


def _allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_cache.get(origin)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            rp.set_url(urljoin(origin, "/robots.txt"))
            rp.read()
        except Exception:
            rp = None
        _robots_cache[origin] = rp
    if rp is None:
        return True  # couldn't fetch robots.txt; assume allowed
    try:
        return rp.can_fetch(config.USER_AGENT, url)
    except Exception:
        return True


def _get(url: str):
    if not _allowed_by_robots(url):
        return None
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            return None
        return resp
    except requests.RequestException:
        return None


def _extract_pdf_text(content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(
                (page.extract_text() or "") for page in pdf.pages
            )
    except Exception:
        return ""


def _extract_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _find_menu_links(base_url: str, html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    domain = urlparse(base_url).netloc
    candidates = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True).lower()
        haystack = f"{href.lower()} {text}"
        if not any(kw in haystack for kw in MENU_KEYWORDS):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).netloc != domain:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        candidates.append(absolute)

    return candidates[:MAX_CANDIDATE_PAGES]


def fetch_menu_text(website_url: str) -> str:
    """Return concatenated best-effort menu text scraped from the site."""
    if not website_url:
        return ""

    home_resp = _get(website_url)
    candidates = []
    if home_resp is not None:
        candidates = _find_menu_links(website_url, home_resp.text)

    if not candidates:
        for path in COMMON_MENU_PATHS:
            candidates.append(urljoin(website_url, path))

    texts = []
    total_len = 0
    visited = set()

    for url in candidates:
        if url in visited or total_len >= MAX_TOTAL_CHARS:
            continue
        visited.add(url)

        resp = _get(url)
        if resp is None:
            continue

        content_type = resp.headers.get("Content-Type", "")
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            text = _extract_pdf_text(resp.content)
        else:
            text = _extract_html_text(resp.text)

        if not text:
            continue

        remaining = MAX_TOTAL_CHARS - total_len
        text = text[:remaining]
        texts.append(text)
        total_len += len(text)

    return "\n\n---\n\n".join(texts)
