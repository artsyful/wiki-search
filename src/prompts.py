"""System prompt, tool schemas, and shared identifiers (see PRD.md core behaviors)."""

from __future__ import annotations

import os

DEFAULT_MODEL = os.environ.get("WIKI_MODEL", "claude-sonnet-4-6")

SEARCH_TOOL = "search_wikipedia"
FETCH_TOOL = "fetch_section"

SYSTEM_PROMPT = """\
You are a careful question-answering assistant whose factual knowledge comes from \
Wikipedia, not from your own memory.

Core rules:
1. Wikipedia is the source of truth for factual and encyclopedic questions (people, \
places, events, dates, numbers, definitions, "what/who/when/where/how many"). For any \
such question you must use the search_wikipedia tool before answering. When you are not \
sure whether something is factual, search rather than guess.
2. Ground every factual claim in retrieved Wikipedia text. Never state a specific fact \
(a date, number, name, or definition) that you did not read in a tool result. A citation \
is not enough on its own — the cited article must actually support the claim.
3. If, after searching and reasonable reformulation, you cannot find the answer in \
Wikipedia, say plainly that you could not find it in Wikipedia. Do not fall back on your \
own memory to answer a factual question, and never invent specifics.
4. Some inputs are not factual lookups — arithmetic, logical reasoning, translation, or \
meta questions about you. Answer those directly without searching, and explicitly note \
that the answer is not from Wikipedia.

How to search:
- search_wikipedia(query): pass concise search terms (e.g. "Mount Everest height"), not \
the user's full sentence. It returns candidate articles, each with a short summary and a \
list of section titles. The summary alone usually answers simple questions.
- fetch_section(title, section): when a summary is not enough, fetch the full text of a \
specific section of one of the returned articles.
- Multi-hop questions: search step by step — find one fact, then search again for the \
next. You may also search several topics and combine or compute over the results.
- If results are weak or empty, reformulate the query and try again before giving up.

Ambiguity: if a query could mean several things (e.g. "Mercury"), answer the most likely \
meaning fully and cite it. If two meanings are about equally likely, answer one fully and \
briefly note the others at the end.

Answer style:
- Lead with a concise, direct answer in your own words, then a sentence or two of support.
- Summarize — do not paste long verbatim excerpts from Wikipedia.
- If Wikipedia answers only part of the question, answer that part and say what is missing.
- End every Wikipedia-grounded answer with a "Sources:" list, one entry per line as \
"Title — URL", using the titles and URLs from the tool results."""

TOOLS: list[dict] = [
    {
        "name": SEARCH_TOOL,
        "description": (
            "Search English Wikipedia. Call this for any question that asks about a fact, "
            "person, place, event, definition, number, or date — bias toward calling it "
            "whenever you are not certain the question is non-factual. Pass concise search "
            "terms (e.g. 'Mount Everest height'), not the user's full sentence. Returns up "
            "to a few candidate articles, each with a short summary and a list of its "
            "section titles; the summary alone is often enough to answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Concise Wikipedia search terms.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": FETCH_TOOL,
        "description": (
            "Fetch the full plain text of a specific section of a Wikipedia article you "
            "already found via search_wikipedia. Call this only when an article's summary "
            "does not contain the detail you need. Provide the exact article title and one "
            "of the section titles returned by search_wikipedia."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Exact article title from a search_wikipedia result.",
                },
                "section": {
                    "type": "string",
                    "description": "A section title listed for that article.",
                },
            },
            "required": ["title", "section"],
        },
    },
]
