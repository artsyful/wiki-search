# EVALS — Wikipedia-Grounded Q&A Agent

High-level eval proposal. Start basic and category-balanced; iterate. Measures the quality
dimensions in [PRD.md](PRD.md) against the design in [DESIGN.md](DESIGN.md). Each case declares
an **expected behavior**, not just a gold string.

## Dimensions → Graders
| Dimension | Grader | How |
|---|---|---|
| **Search behavior** | **Code** | Compare actual searches to the case's `expected_searches`: `0` → must not search; `N ≥ 1` → at least N searches (multi-hop ≥ 2). |
| **Accuracy** | **Code** | Do all of the case's `gold_facts` appear in the answer? A cheap, LLM-free correctness signal that can run on every iteration without Opus. N/A when a case has no `gold_facts`. |
| **Correctness** | **LLM judge** (rubric) | Score the answer against the case's `reference_answer` — the semantic check that goes beyond keyword matching. |
| **Faithfulness / grounding** | **LLM judge** (rubric) | Is every factual claim supported by the **retrieved** Wikipedia text? Subsumes "do the cited articles support the claim." |
| **Behavior** | **LLM judge** (rubric) | Does the answer handle the case's special requirement — abstain honestly, label non-Wikipedia answers, disambiguate, correct false premises — per `expected_behavior`? |
| **Citations** | **Code** | When search was used, assert ≥ 1 well-formed `Title — URL` citation **and that every cited URL resolves** (HTTP 200) — presence alone is not enough. |

Two grader families: **code/deterministic** (cheap, exact, no LLM — search counts, gold-fact
accuracy, citation presence + URL liveness) and **LLM judge** (rubric-scored — correctness,
faithfulness, behavior). Code graders are mandatory and run every time; the Opus judges are the
expensive layer. Each judge returns a 3-tier score (0–2) **plus a short rationale** for the report.

Dropped from the earlier draft: the standalone **Abstention** grader (folded into
`expected_searches = 0` + the Behavior judge) and **Conciseness** (hard to validate; some answers
are legitimately long).

## LLM-Judge Rubrics (review these)
Each judge sees the question, the agent's answer, and case-specific context, and returns
`{score, rationale}` on a **3-tier scale** (labeled below). Judges run on **Claude Opus 4.8**
(`claude-opus-4-8`) — deliberately more capable than the Sonnet 4.6 agent, so the grader is
stronger than what it grades. Primary metric is **mean score (0–2)**; a case **passes** a
dimension at **score ≥ 1** (anything but the bottom tier).

### Correctness (input: question, answer, `reference_answer`)
Applies to factual-answer cases. For pure non-factual / abstention cases it is **N/A** (Behavior
carries those).
- **2 — Correct:** states the key fact(s) from the reference; no contradictions.
- **1 — Partial:** on-topic and partly right, but a key fact is imprecise, missing, or only loosely matches the reference.
- **0 — Incorrect:** wrong, or a non-answer where a real answer was expected.

### Faithfulness / grounding (input: question, answer, **retrieved Wikipedia text the agent saw**)
Graded against what was actually retrieved during the run (the tool results), not a re-fetch.
For non-Wikipedia answers (non-factual cases) it is **N/A**.
- **2 — Grounded:** every factual claim is supported by the retrieved sources; nothing introduced beyond them.
- **1 — Minor gap:** supported overall, but one minor detail isn't clearly traceable to a source.
- **0 — Unsupported:** a material claim is unsupported or contradicted by the sources, or citations don't match content.

### Behavior (input: question, answer, `expected_behavior`)
Grades special-case handling against the case's stated policy. For ordinary factual cases the
expected behavior is simply "answer normally with citations," and this judge confirms nothing
went wrong (no fabrication, no false hedging).
- **2 — Ideal:** handles the case exactly as policy requires.
- **1 — Acceptable:** right behavior but weakly executed — abstains but over-hedges, mentions other senses only vaguely, or labels the non-Wikipedia answer faintly.
- **0 — Poor:** wrong behavior — fabricates, fails to label a non-Wikipedia answer, adds an unsourced guess when it should abstain, or plays along with a false premise.

## Case Set (initial ~12–15, balanced across categories)
- **Single-hop factual** — e.g. "height of Mount Everest" (`expected_searches = 1`).
- **Multi-hop factual** — e.g. "population of the capital of the 2018 World Cup winner"
  (`expected_searches ≥ 2`).
- **Deep-section factual** — a detail that lives in a body section, not the intro, so the agent
  must call `fetch_article` after searching (e.g. a specific figure from an article's "History"
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
then LLM-judge graders → aggregate **per-dimension** and **per-category**: code dimensions report
a **pass rate**, judge dimensions report a **mean (0–2) + pass rate** (score ≥ 1) → print a
console summary table. Latest numbers are recorded in the README per
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
