"""Thin live MediaWiki client backing the two Wikipedia tools.

`search_wikipedia` returns a lightweight overview (summary + section titles) for the
top candidate articles; `fetch_section` drills into one section's full text. See
DESIGN.md → Retrieval Integration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote

import requests

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
# Wikipedia asks all API clients to send a descriptive User-Agent.
USER_AGENT = "wiki-search-agent/0.1 (Anthropic prompt-eng take-home)"
SEARCH_LIMIT = 5
TOP_K_ARTICLES = 3
HTTP_TIMEOUT = 15
MAX_SECTION_CHARS = 6000

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
class SectionContent:
    """The plain text of one article section from `fetch_section`."""

    title: str
    section: str
    text: str
    url: str


_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def _get(params: dict[str, object]) -> dict:
    resp = _session.get(WIKIPEDIA_API, params={**params, "format": "json"}, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _url_for(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))


class _TextExtractor(HTMLParser):
    """Collect visible text, dropping tables/citations/scripts."""

    _SKIP_TAGS = {"style", "script", "sup", "table"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def _strip_html(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"\[edit\]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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


def fetch_section(title: str, section: str) -> SectionContent | None:
    """Return the plain text of `section` within article `title`, or None if absent."""
    try:
        data = _get({"action": "parse", "page": title, "prop": "sections", "redirects": 1})
    except requests.RequestException:
        return None
    sections = data.get("parse", {}).get("sections", [])

    wanted = section.strip().lower()
    index: str | None = None
    for entry in sections:
        if (entry.get("line") or "").strip().lower() == wanted:
            index = entry.get("index")
            break
    if index is None:  # fall back to a contains-match
        for entry in sections:
            if wanted in (entry.get("line") or "").strip().lower():
                index = entry.get("index")
                break
    if index is None:
        return None

    try:
        body = _get(
            {
                "action": "parse",
                "page": title,
                "prop": "text",
                "section": index,
                "redirects": 1,
                "disabletoc": 1,
            }
        )
    except requests.RequestException:
        return None
    html = body.get("parse", {}).get("text", {}).get("*", "")
    text = _strip_html(html)[:MAX_SECTION_CHARS]
    return SectionContent(title=title, section=section, text=text, url=_url_for(title))
