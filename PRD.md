# PRD — Wikipedia-Grounded Q&A Agent

## Context
This is an Anthropic prompt-engineering take-home (1–2 hr target): build a system where Claude
answers questions using a `search_wikipedia(query)` tool, and evaluate it. The real subject is
**trustworthiness, not capability** — grounding discipline (when to search, refusing parametric
guesses, clean abstention, faithful citations) is what prompt engineering controls and what
evals can measure. This document defines product behavior; agent design lives in
[DESIGN.md](DESIGN.md) and eval design in [EVALS.md](EVALS.md).

## Goals
1. Answer factual/encyclopedic questions using **Wikipedia as the primary source of truth**.
2. **Bias to search over guessing** — when in doubt whether something is factual, search.
3. **Never present parametric memory as a Wikipedia-sourced fact**; non-Wikipedia answers are
   explicitly labeled as such.
4. **Abstain cleanly** when the answer isn't in Wikipedia rather than fabricate.
5. **Cite** every Wikipedia-sourced answer (**Title + URL**).
6. Be **transparent** about whether the answer came from Wikipedia.

## Non-Goals
Production search system; multi-turn conversation memory; non-English Wikipedia; media/images;
any built-in hosted search/RAG tool (forbidden by the assignment).

## Primary User & Use Case
A reviewer/end user runs the tool once and enters an **interactive Q&A session** (REPL — ask
many questions without relaunching). Each question returns a concise, grounded, cited answer —
or an honest "not in Wikipedia / not a factual question" response. A demo/sample-queries path
lets a reviewer see it work immediately.

## Input Taxonomy & Required Behavior
The agent classifies intent, biasing toward "factual → search" when uncertain.

| Input type | Behavior |
|---|---|
| **Encyclopedic factual** | Search, answer from retrieved text, cite (Title + URL). Core path. |
| **Multi-hop factual** | **Iterative search** — chain searches, reformulating between hops; cite each supporting source. |
| **Ambiguous entity** ("Mercury") | Answer the **most likely sense fully** and cite it; when senses are roughly equally likely, **answer at least one fully and list the others at the end** (important — no conversational follow-up in phase 1). |
| **Clearly non-factual** (arithmetic, reasoning, translation, meta/"what can you do") | Answer **directly without searching**, and **explicitly label** the answer as not from Wikipedia. |
| **Subjective / opinion / current / real-time** | If grounded in Wikipedia, answer "as of Wikipedia's current article state"; otherwise label as non-Wikipedia. No special-casing beyond this. |

(No bespoke harmful-content rule — rely on Claude's default behavior, which already handles this well.)

## Core Behavioral Requirements
1. **Search policy — bias to search.** Anything plausibly factual triggers a search; only
   *clearly* non-factual inputs are answered directly.
2. **Grounding / faithfulness (deep requirement).** Every factual claim in a Wikipedia answer
   must be supported by retrieved text — citation presence ≠ support. No unsupported specifics.
3. **No unlabeled parametric facts.** Non-Wikipedia answers must explicitly say so.
4. **Query reformulation.** Translate the question into effective search terms; retry with
   reformulations before concluding "not found."
5. **Pure abstention.** If not found after reasonable reformulation, **state plainly it wasn't
   found in Wikipedia and stop** — no parametric fallback for factual queries. Distinguish
   *not found* vs *found-but-insufficient* (answer the supported part, flag the gap).
6. **Citations** (Title + URL) on every Wikipedia answer; multi-hop cites each source.
7. **User-friendly summarization.** Concise **direct answer first**, then brief support +
   citations. **Summarize in the agent's own words**; avoid large verbatim Wikipedia excerpts.
8. **Transparency without internals.** The CLI shows a progress indicator while working and
   does **not** dump queries/raw retrieval. Whether search was used is conveyed by the answer
   itself (citations present, or an explicit "answered without Wikipedia" label) plus a single
   subtle footer line.

## Quality Dimensions (measured in evals)
Correctness · **Faithfulness/grounding** · **Citation validity** · **Behavior** (searched when
it should, answered directly when it shouldn't, abstained appropriately without over-abstaining)
· Conciseness/format.

## Open Questions / Future
Citation granularity (article-level default); multi-turn follow-ups; richer disambiguation via
clarifying questions; non-English Wikipedia. Search backend is a design decision (see DESIGN.md),
leaning to the live MediaWiki API.
