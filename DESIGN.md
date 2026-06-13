# DESIGN — Wikipedia-Grounded Q&A Agent

High-level design proposal for the agent logic, tool use, and CLI. Implements the behavior in
[PRD.md](PRD.md). Iterate as we build.

## Overview
A single-loop tool-using agent: Claude + **two** Wikipedia tools (`search_wikipedia` and
`fetch_section`) over a live MediaWiki API integration, wrapped in an interactive CLI. The
system prompt encodes the PRD behaviors (bias-to-search, grounding, labeling non-Wikipedia
answers, pure abstention, citations).

## Model
**Claude Sonnet 4.6** by default (`claude-sonnet-4-6`) — strong instruction-following and
grounding at low latency/cost for an agent loop; model id configurable via env var. The exact
model is named in the writeup per the assignment constraint.

## Agent Loop
1. User question → append to the message list.
2. Call Claude with the system prompt + the two tool definitions.
3. If Claude emits a `tool_use`, execute it, return a `tool_result`, and loop. Two distinct
   multi-hop patterns are supported:
   - **Reformulation hop** — weak results → re-`search_wikipedia` with better terms.
   - **Aggregation hop** — search/fetch several articles, then combine (summarize or compute,
     e.g. arithmetic over retrieved facts).
4. Cap tool calls per question (**max 8 turns**) to bound runaway loops while leaving room for
   rare deep recursive search; on cap, answer with what is grounded or abstain.
5. Stop when Claude returns a final text answer.

## Tools (two-tool design)
Splitting search from section-fetch keeps context lean: a single broad search that dumped
multiple full articles would bloat the context, while most Wikipedia **summaries already answer
simple questions**. So the agent gets a cheap overview first and only drills into a section when
it needs to.

1. **`search_wikipedia(query: str)`** — pass concise search terms (not the raw question), call
   repeatedly for multi-hop, reformulate on weak results. Returns a small set of candidate
   articles, each with **title, summary (intro extract), section titles, url**. The summary +
   section list is usually enough to answer or to decide which section to fetch.
2. **`fetch_section(title: str, section: str)`** — retrieve the plain text of a specific section
   of a named article, for when the summary is insufficient. Returns **title, section, text,
   url**.

We start here and iterate (e.g. tune what `search` returns, or merge/split tools) if evals are
weak.

## Retrieval Integration (live MediaWiki API)
- **Search** (`search_wikipedia`): `list=search` for candidate titles, then per top-K (~3) page
  fetch the **intro extract** (`prop=extracts&exintro&explaintext`) and the **section list**
  (`action=parse&prop=sections`). Assemble into `SearchResult`s.
- **Section fetch** (`fetch_section`): resolve the section index for the given title+section via
  `prop=sections`, then pull that section's plain text (`action=parse&section=N` → strip markup,
  or `prop=extracts` scoped to the section). Returns a `SectionContent`.
- One thin client module; no local index. Zero/empty results are returned cleanly so the agent
  can reformulate or abstain.

## CLI (interactive, well-formatted)
- REPL: launch once, prompt loop (`Ask a question ▷ `), `exit`/Ctrl-D to quit; `--demo` runs a
  curated set of sample queries end-to-end.
- **Rich terminal formatting** (use the `rich` library):
  - **Color-coded roles** — question and answer visually distinct (question bold/cyan, answer
    default, citations dimmed, footer colored by search-used vs not).
  - **Line separator** (horizontal rule) printed after each Q→A exchange so `--demo` output is
    scannable.
  - **Progress indicator** (spinner with "Searching Wikipedia…") while the agent works; no
    internal query/retrieval dump.
- Renders per question: concise answer → citations (Title + URL) → one footer line:
  `🔍 Answered using Wikipedia (N source(s))` **or** `💡 Answered without Wikipedia`.
  This single line is how the prototype "shows whether search was used."

## Code Shape (per CLAUDE.md style)
- Module-level constants for the model id, tool names, and API endpoint (no repeated string
  literals across files).
- `@dataclass` returns between internal functions:
  - `SearchResult(title: str, summary: str, section_titles: list[str], url: str)`
  - `SectionContent(title: str, section: str, text: str, url: str)`
  - `Citation(title: str, url: str)`
  - `AgentAnswer(text: str, citations: list[Citation], used_search: bool, tool_calls: int)`
- Typed function signatures throughout; dicts only at the API I/O boundary.

### File structure
```
wiki-search/
├── README.md                 # setup / run / eval results (reviewer entry point)
├── CLAUDE.md  PRD.md  DESIGN.md  EVALS.md  PROMPT_ITERATION.md
├── requirements.txt          # anthropic, requests, rich
├── .env.example              # ANTHROPIC_API_KEY, optional WIKI_MODEL
├── src/
│   ├── __init__.py
│   ├── wiki_client.py        # MediaWiki search + section fetch → SearchResult / SectionContent
│   ├── prompts.py            # system prompt + the two tool schemas + constants
│   ├── agent.py              # tool-use loop → AgentAnswer
│   └── cli.py                # interactive REPL + demo mode + rich rendering  (entry: python -m src.cli)
├── evals/
│   ├── __init__.py
│   ├── cases.py              # EvalCase dataclass + the curated case set
│   ├── graders.py            # code graders + LLM-judge graders
│   ├── runner.py             # run suite, aggregate, emit reports  (entry: python -m evals.runner)
│   └── report.py             # JSON + self-contained HTML report writers
└── results/
    ├── <timestamp>.json      # machine-readable run output
    └── <timestamp>.html      # self-contained human-readable report
```
- Entry points: `python -m src.cli` (REPL / `--demo`) and `python -m evals.runner` (eval suite).

## Tradeoffs / Notes
- Live API chosen for **simplicity and freshness** over a downloaded dump/local index — fits the
  "don't build a production search system" guidance.
- Iteration cap trades worst-case latency for bounded cost; tune during evals.
- Extracts (not full article text) keep token usage low; risk is occasional thin context, which
  the reformulation rule and multi-hop loop mitigate.
