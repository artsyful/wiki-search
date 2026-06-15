# Design Rationale — Wikipedia-Grounded Q&A

A CLI agent that answers questions using **Claude + Wikipedia**, plus an eval suite that
measures how well it actually does it.

| | |
|---|---|
| **Model** | Agent: **Claude Sonnet 4.6** (`claude-sonnet-4-6`). Eval judges: **Claude Opus 4.8** (`claude-opus-4-8`). |
| **Retrieval** | Hand-rolled live **MediaWiki API** client — **no hosted search / RAG tools** used, per the constraint. |
| **Headline result** | **96% pass · judge mean 1.79/2** over 17 cases / 6 dimensions (latest run in `results/`). |
| **Time spent** | ~`<X>` hours. |
| **Where to look** | Run instructions: [README.md](README.md) · deep dives: [docs/DESIGN.md](docs/DESIGN.md), [docs/EVALS.md](docs/EVALS.md), [docs/PROMPT_ITERATION.md](docs/PROMPT_ITERATION.md) · latest eval report: `results/*.html`. |

---

## 1. What I built

A single-loop tool-using agent. A question goes into a manual tool loop where Claude can call
two tools — `search_wikipedia(query)` and `fetch_section(title, section)` — over the live
MediaWiki API, then returns a direct answer with a `Sources:` list. The CLI shows whether
search was used (`🔍 Answered using Wikipedia` vs `💡 Answered without Wikipedia`) and has a
`--demo` mode so a reviewer sees it work immediately. Alongside it is an eval harness that runs
a category-balanced case set through six graders and emits a JSON + offline HTML report.

> **Flow:** question → Claude (system prompt + 2 tools) → `search` / `fetch_section` over MediaWiki → loop (cap 5 tool calls) → grounded, cited answer.

## 2. Prompt engineering approach — and why

**Thesis: the hard part is grounding discipline, not retrieval.** Getting Claude to *find*
facts on Wikipedia is easy; getting it to say *only* what it actually read — and to abstain
otherwise — is where the quality lives. Every prompt choice serves that.

- **Bias to search, but draw the factual / non-factual line.** Factual questions *must* call
  `search_wikipedia` before answering ("when unsure whether something is factual, search rather
  than guess"); arithmetic, translation, and reasoning are answered directly and explicitly
  labeled as *not* from Wikipedia. This prevents both lazy hallucination and pointless searches.
- **The faithfulness rule (the centerpiece).** *"Never state a specific fact you did not read in
  a tool result. A citation is not enough — the cited article must actually support the claim.
  Even if you're confident a detail is true from your own knowledge (a famous figure, quote,
  date, 'well-known' fact), do not include it unless a tool result contains it."* This last
  clause was added in direct response to an eval failure (§5).
- **Abstain over fabricate.** If retrieval comes up empty after reformulation, say so plainly
  rather than falling back on memory.
- **Edge-case rules** for the cases that separate a careful assistant from a naive one:
  ambiguity (answer the likeliest sense fully, note the others), partial coverage (answer what's
  there, flag the gap), and false premises (correct the assumption instead of playing along).
- **Two-tool design as a prompt lever.** Splitting cheap `search` (summary + section list) from
  `fetch_section` keeps context lean *and* gives the model an explicit instruction hook: if a
  summary lacks the specific figure asked for, fetch the relevant section before answering
  rather than guessing or claiming it's unavailable.
- **Output format that's also machine-checkable.** "Lead with a direct answer, then a `Sources:`
  list of `Title — URL`." This is good UX and it's exactly what the citations grader parses and
  HTTP-checks.

## 3. Eval design — which dimensions, and why

Two design commitments drive the suite:

1. **Test expected *behavior*, not a gold string.** Each case declares `expected_searches`, a
   `reference_answer`, an `expected_behavior` policy, and optional `gold_facts`. That lets one
   framework grade a factual lookup, an abstention, and a false-premise correction uniformly.
2. **Category balance over volume.** 17 cases across 10 categories (single/multi-hop, deep
   section, ambiguous, false premise, non-factual, unanswerable, found-but-insufficient,
   temporal recent/past) — each category probes a *distinct failure mode* rather than piling on
   more of the same.

Six dimensions, deliberately split into **cheap deterministic code graders** and **LLM judges**:

| Dimension | Grader | What it checks |
|---|---|---|
| `search_behavior` | code | actual searches vs `expected_searches` (0 = must not search; N≥1 = at least N) |
| `accuracy` | code | do all `gold_facts` appear in the answer? (free, no LLM) |
| `citations` | code | when search used, ≥1 well-formed `Title — URL` **and every URL resolves (HTTP 200)** |
| `correctness` | Opus judge (0–2) | answer vs `reference_answer` |
| `faithfulness` | Opus judge (0–2) | every claim supported by retrieved text; nothing invented |
| `behavior` | Opus judge (0–2) | special-case handling vs `expected_behavior` |

**Why this split:** code graders are free, objective, and catch regressions instantly (a broken
citation URL, a missing search); judges catch the nuance code can't (is this *grounded*? did it
handle the edge case *gracefully*?). **Why a stronger judge than the agent** — judges run on
Opus 4.8 while the agent runs on Sonnet 4.6, so the grader is more capable than what it grades.
Each dimension maps to a product risk: `faithfulness` = the trust risk, `behavior` = graceful
edges, `search_behavior` = using the tool when (and only when) it should.

## 4. Where it succeeds and fails — what the evals taught me

**Latest run — 96% pass, judge mean 1.79/2 (82 grades):**

| Dimension | Result |
|---|---|
| search_behavior (code) | **100%** pass · n=17 |
| accuracy (code) | **90%** pass · n=10 |
| citations (code) | **100%** pass · n=13 |
| correctness (judge) | **100%** pass · mean **1.92**/2 · n=12 |
| faithfulness (judge) | **92%** pass · mean **1.69**/2 · n=13 |
| behavior (judge) | **94%** pass · mean **1.76**/2 · n=17 |

**Succeeds:** search/no-search discipline is perfect; citations are always well-formed and
resolve; multi-hop chaining works including a 3-hop chain, arithmetic on retrieved figures, and
cross-article aggregation; non-factual inputs are answered directly and labeled; unanswerable
questions are declined without fabrication.

**Fails — three named, instructive cases:**
- **Grounding still leaks (`einstein_last_words`, faithfulness 0).** The agent grounds the
  quoted last words correctly but *adds biographical detail not in the retrieved sources.* The
  prompt's grounding clause reduced this but didn't eliminate it — the residual trust risk.
- **Deep-section retrieval isn't reliably triggered (`eiffel_tower_steps`, accuracy 0).** The
  answer is right about the ~600 steps to the second floor but misses the historical 1,710-step
  figure and claims Wikipedia gives no total — because it answered from the summary instead of
  fetching the section, exactly the behavior the prompt tries to prevent.
- **The most interesting finding is about the *evaluator*, not the agent
  (`hormuz_blocked_2026`).** On a post-training-cutoff event, the agent produced a fully
  *grounded* answer — the retrieval-based **faithfulness grader passed it** — but the
  knowledge-based **behavior judge scored it 0**, calling a real Wikipedia article
  "almost certainly fabricated." The judge shares the agent's training cutoff, so it distrusts
  genuine new content. **Lesson: an LLM judge reasoning from its own world-knowledge is unsafe
  for post-cutoff facts; ground the judge in retrieval or put a human in the loop.**

## 5. Key iterations driven by the evals

The suite didn't just score the system — it *drove* the prompt and even exposed a limit of
LLM-as-judge. The highest-signal iterations (full log in `docs/PROMPT_ITERATION.md`):

1. **Grounding clause added after a hallucination.** Evals caught the agent asserting confident
   "well-known" facts it never retrieved; appending the "do not include it unless a tool result
   contains it" clause to the faithfulness rule moved the worst case (`eiffel`, then) from
   faithfulness 0 → 2.
2. **Citation parser bug surfaced by a real 404.** `mercury_ambiguous` failed citations because
   the URL parser stripped a disambiguation paren (`Mercury_(planet`) → 404. Fixed to only strip
   an unbalanced trailing paren.
3. **Grader redesign for honest signal.** Split code graders into clean pass/fail, added the
   `accuracy` gold-fact check (free correctness signal), and made `citations` HTTP-validate that
   URLs resolve — so "a citation is present" can't pass when the link is dead.
4. **Expanded the case set (13 → 17) and found the judge blind spot.** Adding temporal, 3-hop,
   compute, and aggregation cases held quality steady (95% → 96%) *and* surfaced the
   post-cutoff judge-skepticism finding above — the kind of thing only a broader suite reveals.

## 6. What I'd do with more time

- **Close the deep-section gap:** detect when a requested figure is absent from the summary and
  *force* a `fetch_section` before the model is allowed to claim unavailability.
- **Fix temporal judging:** give judges the agent's retrieved context (retrieval-grounded
  judging) or route post-cutoff cases to a human, so genuine new facts aren't penalized.
- **Harden faithfulness:** self-consistency / a second adversarial "find an unsupported claim"
  pass over each answer, since faithfulness is the residual risk.
- **Scale the suite:** auto-generate and adversarially mutate cases; add cost/latency telemetry
  per case to the report.

## 7. Scope and time

Spent ~`<X>` hours. I deliberately **did not** build a production search system (the brief says
not to): no local Wikipedia dump or index (live API trades reproducibility for simplicity and
freshness), no multi-turn memory, no UI beyond the CLI. The effort went where the assignment
points — **prompt quality and eval design** — and into making the evals trustworthy enough that
their numbers, and their failures, actually mean something.
