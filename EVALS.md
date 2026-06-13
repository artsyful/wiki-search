# EVALS — Wikipedia-Grounded Q&A Agent

High-level eval proposal. Start basic and category-balanced; iterate. Measures the quality
dimensions in [PRD.md](PRD.md) against the design in [DESIGN.md](DESIGN.md). Each case declares
an **expected behavior**, not just a gold string.

## Dimensions → Graders
| Dimension | Grader | How |
|---|---|---|
| **Search behavior** | **Code** | Compare actual searches to the case's `expected_searches`: `0` → must not search; `N ≥ 1` → at least N searches (multi-hop ≥ 2). |
| **Correctness** | **LLM judge** (rubric) | Score the answer against the case's `reference_answer`. Optional cheap code pre-check on `gold_facts` (substring) for crisp numeric facts. |
| **Faithfulness / grounding** | **LLM judge** (rubric) | Is every factual claim supported by the **retrieved** Wikipedia text? Subsumes "do the cited articles support the claim." |
| **Behavior** | **LLM judge** (rubric) | Does the answer handle the case's special requirement — abstain honestly, label non-Wikipedia answers, disambiguate, correct false premises — per `expected_behavior`? |
| **Citations** | **Code** | When search was used, assert ≥ 1 well-formed `Title — URL` citation is present. |

Two grader families: **code/deterministic** (cheap, exact — search counts, key-fact substrings,
citation presence) and **LLM judge** (rubric-scored — correctness, faithfulness, behavior). Each
judge returns a 0–3 score **plus a short rationale** for the report.

Dropped from the earlier draft: the standalone **Abstention** grader (folded into
`expected_searches = 0` + the Behavior judge) and **Conciseness** (hard to validate; some answers
are legitimately long).

## LLM-Judge Rubrics (review these)
Each judge sees the question, the agent's answer, and case-specific context, and returns
`{score: 0–3, rationale}`. Judges run on an Anthropic model (same family as the agent, separate
call). Per-dimension pass threshold for aggregation: **score ≥ 2**.

### Correctness (input: question, answer, `reference_answer`)
Applies to factual-answer cases. For pure non-factual / abstention cases it is **N/A** (Behavior
carries those).
- **3** — Fully correct: states the key fact(s) from the reference; no contradictions.
- **2** — Mostly correct: core fact right, minor omission or imprecision.
- **1** — Partially correct: on-topic but a key fact is wrong or missing.
- **0** — Incorrect, or a non-answer where a real answer was expected.

### Faithfulness / grounding (input: question, answer, **retrieved Wikipedia text the agent saw**)
Graded against what was actually retrieved during the run (the tool results), not a re-fetch.
For non-Wikipedia answers (non-factual cases) it is **N/A**.
- **3** — Every factual claim is supported by the retrieved sources; nothing introduced beyond them.
- **2** — Supported overall, but one minor detail isn't clearly traceable to a source.
- **1** — Contains a material claim not supported by any retrieved source.
- **0** — Key claims unsupported or contradicted by the sources; citations don't match content.

### Behavior (input: question, answer, `expected_behavior`)
Grades special-case handling against the case's stated policy. For ordinary factual cases the
expected behavior is simply "answer normally with citations," and this judge confirms nothing
went wrong (no fabrication, no false hedging).
- **3** — Handles the case exactly as policy requires.
- **2** — Right behavior, weakly executed (abstains but over-hedges; mentions other senses only vaguely).
- **1** — Partially right (abstains but adds an unsourced guess; answers ambiguity but ignores other senses; labels weakly).
- **0** — Wrong behavior (fabricates, fails to label a non-Wikipedia answer, plays along with a false premise).

## Case Set (initial ~12–15, balanced across categories)
- **Single-hop factual** — e.g. "height of Mount Everest" (`expected_searches = 1`).
- **Multi-hop factual** — e.g. "population of the capital of the 2018 World Cup winner"
  (`expected_searches ≥ 2`).
- **Deep-section factual** — a detail that lives in a body section, not the intro, so the agent
  must call `fetch_section` after searching (e.g. a specific figure from an article's "History"
  or "Climate" section).
- **Ambiguous entity** — e.g. "Mercury" (answer one sense fully + mention the others).
- **False premise** — question with a wrong assumption (e.g. "When did Einstein win his two Nobel
  Prizes?" — he won one); expected behavior is to correct the premise, grounded.
- **Clearly non-factual** — arithmetic, translation, reasoning (`expected_searches = 0`; expects
  the explicit "not from Wikipedia" label).
- **Not in Wikipedia / unanswerable** — expects honest abstention, no fabrication.
- **Found-but-insufficient** — expects a partial answer + an explicit gap flag.

Each case is an `@dataclass`:
`id`, `question`, `category`, `expected_searches: int`, `reference_answer: str`,
`gold_facts: list[str]` (optional code pre-check), `expected_behavior: str`, `notes`.

## Runner
Iterate cases → run the agent, capturing the `AgentAnswer`, the **search count**, and the
**retrieved Wikipedia text** (tool results, fed to the Faithfulness judge) → apply code graders,
then LLM-judge graders → aggregate **per-dimension** and **per-category** (mean score + pass rate
at score ≥ 2) → print a console summary table. Latest numbers are recorded in the README per
CLAUDE.md after every run.

## Reporting (two artifacts every run)
1. **JSON** (`results/<timestamp>.json`) — machine-readable: per-case grader scores + rationales,
   per-dimension and per-category aggregates, run metadata (model, case count, timestamp). The
   diff-able source of truth across runs.
2. **HTML report** (`results/<timestamp>.html`) — **self-contained, no external CDN** (inline CSS
   + inline SVG/CSS bar charts; works offline), with:
   - **Key-metrics summary at top** — headline mean score + pass rate per dimension, and overall.
   - **Charts** — success-percentage bars per dimension and per category.
   - **Detailed table** — every case: question, category, expected behavior, each grader's score
     + rationale, and the search-used flag.
   - **Expandable sections** (`<details>`) defining each **grader/rubric** and each **case category**.
   - **Full Q&A transcript** (`<details>` at the bottom) — every case's question and the agent's
     complete answer + citations, for quick eyeballing.

   The runner prints the report path on completion (does not auto-open the browser).

## Iteration Loop
Run suite → read failures → adjust system prompt / tool definition / grader → re-run → log the
change in `PROMPT_ITERATION.md` (per CLAUDE.md). Common early targets: over- vs under-searching on
borderline inputs, abstention calibration, and citation-support faithfulness.
