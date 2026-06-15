"""The tool-use agent loop: Claude + two Wikipedia tools → a grounded AgentAnswer.

See docs/DESIGN.md → Agent Loop. The loop is manual (not the SDK tool runner) so we can
track whether search was used, count tool calls, cap multi-hop, and surface progress.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import anthropic

from .prompts import DEFAULT_MODEL, FETCH_TOOL, SEARCH_TOOL, SYSTEM_PROMPT, TOOLS
from .wiki_client import fetch_section, search_wikipedia

MAX_TOOL_CALLS = 5
MAX_TOKENS = 8000
_EMPTY_FALLBACK = "I wasn't able to put together a grounded answer for this from Wikipedia."
_FINAL_ANSWER_NUDGE = (
    "You have reached the tool-use limit, so you cannot search again. Give your final answer now "
    "using only the information you have already retrieved. Do not describe further searches you "
    "would do; if you could not find something, say plainly that you could not find it in Wikipedia."
)

ProgressFn = Callable[[str], None] | None

_URL_RE = re.compile(r"https?://\S+")


@dataclass
class Citation:
    title: str
    url: str


@dataclass
class AgentAnswer:
    text: str
    citations: list[Citation]
    used_search: bool
    tool_calls: int
    searches: int = 0  # count of search_wikipedia calls (≠ tool_calls, which includes fetches)
    retrieved_context: list[str] = field(default_factory=list)  # tool results the agent saw


def _extract_text(content: list) -> str:
    return "".join(block.text for block in content if block.type == "text")


def _parse_citations(text: str) -> list[Citation]:
    """Pull Title — URL pairs out of the answer's Sources list."""
    citations: list[Citation] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = _URL_RE.search(line)
        if not match:
            continue
        url = match.group(0).rstrip(".,;]'\"")
        # Keep a trailing ')' that belongs to a disambiguation slug like Mercury_(planet);
        # only strip it when it's unbalanced (e.g. wrapping punctuation: "(see http://x)").
        if url.endswith(")") and url.count("(") < url.count(")"):
            url = url[:-1]
        if url in seen:
            continue
        seen.add(url)
        title = line[: match.start()].strip(" -–—•*\t")
        citations.append(Citation(title=title or url, url=url))
    return citations


def _format_search_results(query: str, results: list) -> str:
    if not results:
        return f"No Wikipedia articles found for '{query}'. Try different search terms."
    blocks = []
    for result in results:
        sections = ", ".join(result.section_titles[:12]) if result.section_titles else "(none)"
        blocks.append(
            f"## {result.title}\n"
            f"URL: {result.url}\n"
            f"Summary: {result.summary or '(no summary available)'}\n"
            f"Sections: {sections}"
        )
    return "\n\n".join(blocks)


class WikiAgent:
    """Answers a question by grounding it in Wikipedia via the tool-use loop."""

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        model: str = DEFAULT_MODEL,
        max_tool_calls: int = MAX_TOOL_CALLS,
    ) -> None:
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.max_tool_calls = max_tool_calls

    def answer(self, question: str, on_progress: ProgressFn = None) -> AgentAnswer:
        messages: list[dict] = [{"role": "user", "content": question}]
        used_search = False
        tool_calls = 0
        searches = 0
        retrieved: list[str] = []

        while True:
            force_final = tool_calls >= self.max_tool_calls
            request: dict = {
                "model": self.model,
                "max_tokens": MAX_TOKENS,
                "system": SYSTEM_PROMPT,
                "tools": TOOLS,
                "thinking": {"type": "adaptive"},
                "messages": messages,
            }
            if force_final:
                # Force a text answer and drop thinking, so the whole token budget goes to the
                # answer (adaptive thinking on this long final turn could starve it to empty), and
                # nudge the model to commit to an answer from what it has rather than narrate more
                # searching.
                request["tool_choice"] = {"type": "none"}
                request["thinking"] = {"type": "disabled"}
                request["messages"] = messages + [{"role": "user", "content": _FINAL_ANSWER_NUDGE}]

            response = self.client.messages.create(**request)
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if force_final or response.stop_reason != "tool_use" or not tool_uses:
                text = _extract_text(response.content).strip() or _EMPTY_FALLBACK
                return AgentAnswer(
                    text=text,
                    citations=_parse_citations(text),
                    used_search=used_search,
                    tool_calls=tool_calls,
                    searches=searches,
                    retrieved_context=retrieved,
                )

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for tool_use in tool_uses:
                used_search = True
                tool_calls += 1
                if tool_use.name == SEARCH_TOOL:
                    searches += 1
                content = self._run_tool(tool_use, on_progress)
                retrieved.append(content)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": content,
                    }
                )
            messages.append({"role": "user", "content": results})

    def _run_tool(self, tool_use, on_progress: ProgressFn) -> str:
        name = tool_use.name
        args = tool_use.input
        try:
            if name == SEARCH_TOOL:
                query = args.get("query", "")
                if on_progress:
                    on_progress(f'Searching Wikipedia for "{query}"…')
                return _format_search_results(query, search_wikipedia(query))
            if name == FETCH_TOOL:
                title = args.get("title", "")
                section = args.get("section", "")
                if on_progress:
                    on_progress(f'Reading "{section}" from {title}…')
                content = fetch_section(title, section)
                if content is None:
                    return f"No section matching '{section}' was found in '{title}'."
                return (
                    f"Section '{content.section}' of {content.title} "
                    f"({content.url}):\n\n{content.text}"
                )
        except Exception as exc:  # surface failures to the model, don't crash the loop
            return f"Tool '{name}' failed: {exc}. Try reformulating or another approach."
        return f"Unknown tool: {name}"
