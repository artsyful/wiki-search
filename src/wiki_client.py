"""Thin live MediaWiki client backing the two Wikipedia tools.

`search_wikipedia` returns a lightweight overview (summary + section titles) for the
top candidate articles; `fetch_article` returns one article's full plain text. See
docs/DESIGN.md → Retrieval Integration.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import quote

import requests

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
# Wikipedia asks all API clients to send a descriptive User-Agent.
USER_AGENT = "wiki-search-agent/0.1 (Anthropic prompt-eng take-home)"
SEARCH_LIMIT = 5
TOP_K_ARTICLES = 3
HTTP_TIMEOUT = 15
# Cap on a single full-article fetch, so a very large article (e.g. a country or war)
# stays bounded. Fetch is the targeted, post-decision call for one article, so this is
# the only place we return long text; search never returns full bodies.
MAX_ARTICLE_CHARS = 40000
MAX_RETRIES = 4  # retry on HTTP 429 (rate limit) with exponential backoff
BACKOFF_BASE = 1.0

# Boilerplate sections that never help answer a question; hidden from the agent.
SKIP_SECTIONS = {
    "references",
    "external links",
    "see also",
    "notes",
    "further reading",
    "bibliography",
    "citations",
    "sources",
}


@dataclass
class SearchResult:
    """One candidate article from `search_wikipedia`."""

    title: str
    summary: str
    section_titles: list[str]
    url: str


@dataclass
class ArticleContent:
    """The full plain text of one article from `fetch_article`."""

    title: str
    text: str
    url: str


_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def _request(method: str, url: str, **kwargs: object) -> requests.Response:
    """Issue a request, retrying on HTTP 429 with backoff (honoring Retry-After)."""
    resp = None
    for attempt in range(MAX_RETRIES):
        resp = _session.request(method, url, timeout=HTTP_TIMEOUT, **kwargs)
        if resp.status_code != 429 or attempt == MAX_RETRIES - 1:
            return resp
        wait = float(resp.headers.get("Retry-After", BACKOFF_BASE * (2**attempt)))
        time.sleep(wait)
    return resp  # type: ignore[return-value]


def _get(params: dict[str, object]) -> dict:
    resp = _request("GET", WIKIPEDIA_API, params={**params, "format": "json"})
    resp.raise_for_status()
    return resp.json()


def _url_for(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))


def url_exists(url: str) -> bool:
    """True if `url` resolves to a live page (HTTP 200). Used to validate citations."""
    try:
        resp = _request("HEAD", url, allow_redirects=True)
        if resp.status_code == 405:  # some endpoints reject HEAD; fall back to GET
            resp = _request("GET", url, allow_redirects=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _fetch_extracts(titles: list[str]) -> dict[str, tuple[str, str]]:
    """Batch intro extract + canonical URL for several titles in one query.

    Resolves MediaWiki's `normalized`/`redirects` aliasing so results map back to
    the original search titles.
    """
    data = _get(
        {
            "action": "query",
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
            "redirects": 1,
            "titles": "|".join(titles),
        }
    )
    query = data.get("query", {})
    alias: dict[str, str] = {}
    for entry in query.get("normalized", []) + query.get("redirects", []):
        alias[entry["from"]] = entry["to"]

    def canonical(title: str) -> str:
        seen: set[str] = set()
        while title in alias and title not in seen:
            seen.add(title)
            title = alias[title]
        return title

    pages_by_title = {p.get("title"): p for p in query.get("pages", {}).values()}
    out: dict[str, tuple[str, str]] = {}
    for title in titles:
        page = pages_by_title.get(canonical(title))
        if page:
            summary = (page.get("extract") or "").strip()
            url = page.get("fullurl") or _url_for(title)
            out[title] = (summary, url)
    return out


def _fetch_section_titles(title: str) -> list[str]:
    try:
        data = _get({"action": "parse", "page": title, "prop": "sections", "redirects": 1})
    except requests.RequestException:
        return []
    sections = data.get("parse", {}).get("sections", [])
    titles: list[str] = []
    for section in sections:
        line = (section.get("line") or "").strip()
        if line and line.lower() not in SKIP_SECTIONS:
            titles.append(line)
    return titles


def search_wikipedia(
    query: str,
    limit: int = SEARCH_LIMIT,
    top_k: int = TOP_K_ARTICLES,
) -> list[SearchResult]:
    """Search English Wikipedia and return lightweight overviews of the top hits."""
    data = _get({"action": "query", "list": "search", "srsearch": query, "srlimit": limit})
    hits = data.get("query", {}).get("search", [])
    titles = [h["title"] for h in hits[:top_k]]
    if not titles:
        return []

    extracts = _fetch_extracts(titles)
    results: list[SearchResult] = []
    for title in titles:
        summary, url = extracts.get(title, ("", _url_for(title)))
        results.append(
            SearchResult(
                title=title,
                summary=summary,
                section_titles=_fetch_section_titles(title),
                url=url,
            )
        )
    return results


def _trim_apparatus(text: str) -> str:
    """Cut the article at the first trailing boilerplate heading (References, Notes, etc.).

    The plain-text extract renders section headings as bare lines, so a heading that is
    exactly a SKIP_SECTIONS name on its own line marks where the encyclopedic body ends.
    """
    cut = len(text)
    for name in SKIP_SECTIONS:
        match = re.search(rf"(?im)^\s*{re.escape(name)}\s*$", text)
        if match:
            cut = min(cut, match.start())
    return text[:cut].strip()


def fetch_article(title: str) -> ArticleContent | None:
    """Return the full plain text of article `title`, or None if it does not exist.

    This is the targeted, post-decision call: the agent has already picked one article
    from search and found its summary insufficient, so we return the whole body (minus
    trailing boilerplate, capped) rather than a single section the agent must name.
    """
    try:
        data = _get(
            {
                "action": "query",
                "prop": "extracts|info",
                "explaintext": 1,
                "inprop": "url",
                "redirects": 1,
                "titles": title,
            }
        )
    except requests.RequestException:
        return None
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), None)
    if not page or page.get("missing") is not None or "extract" not in page:
        return None
    text = _trim_apparatus(page.get("extract") or "")[:MAX_ARTICLE_CHARS]
    if not text:
        return None
    url = page.get("fullurl") or _url_for(title)
    return ArticleContent(title=page.get("title") or title, text=text, url=url)
