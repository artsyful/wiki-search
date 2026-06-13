# Prompt / Eval Iteration Log

### 1. Initial eval suite (baseline) — `evals/`
- **Failure:** N/A — first end-to-end build of the 13-case suite, 6 graders (3 code + 3 Opus judges).
- **Change:** Added `evals/cases.py` (category-balanced cases), `graders.py`, `runner.py`, `report.py`.
- **Result:** **Baseline full run — 95% pass, judge mean 1.81/2 (62 grades).** Code: search 100%, accuracy 89%, citations 100%. Judges: correctness 1.78, faithfulness 1.67, behavior 1.92. Weakest category: deep_section 67%.

### 2. Wikipedia 429 backoff + turn cap 8→5 + empty-answer guard — `src/wiki_client.py`, `src/agent.py`
- **Failure:** 3-case spot-check: 2/3 agents failed. Wikipedia returned HTTP 429 under back-to-back eval load; `mercury_ambiguous` burned all turns and returned an **empty answer**, `einstein_two_nobels` fell back on parametric memory (faithfulness judge correctly scored it 0).
- **Change:** `_request()` retries on 429 with exponential backoff honoring `Retry-After`; `MAX_TOOL_CALLS` 8→5; empty final text now replaced by an explicit "couldn't ground an answer" message.
- **Result:** Re-run of the 3 cases — all completed cleanly, no 429 failures.

### 3. Citation parser kept disambiguation parens — `src/agent._parse_citations`
- **Failure:** Citation grader (URL must resolve) flagged `mercury_ambiguous` FAIL: stored URL was `…/Mercury_(planet` — the parser's `rstrip(")")` stripped the closing paren of a real disambiguation slug, yielding a 404. False negative caused by our parser, not the agent.
- **Change:** Only strip a trailing `)` when it is unbalanced (wrapping punctuation); keep it when part of the slug (`url.count("(") < url.count(")")`).
- **Result:** Offline unit check passes — `Mercury_(planet)` retained, `(see http://x)` stripped, plain URLs unchanged. Confirmed in next full run.

### 4. Graders split into code (pass/fail) vs judge (0–2); added Accuracy; citations validate URL — `evals/graders.py`
- **Failure:** Author/reviewer feedback: code graders reporting a `2` score was confusing; correctness lacked a cheap LLM-free signal; "citation present" didn't prove the link was real.
- **Change:** Code graders now return pass/fail (n/a where inapplicable); added mandatory `accuracy` code grader (gold-fact substring match); `citations` now also HEAD-checks every cited URL resolves (HTTP 200). Judge model is Opus 4.8.
- **Result:** Pass/fail renders cleanly in the spot-check and full run; the URL-validation caught a real broken citation (see entry 3). Baseline numbers as in entry 1.

### 5. Prompt restructure (role/tools first, output format last) + false-premise & deep-section rules — `src/prompts.py`
- **Failure:** Author best-practice pass plus eval finding — the original prompt was one prose block; `deep_section` was the weakest category (67%); false-premise behavior relied on inference.
- **Change:** Reorganized into `## Role / How to search / Core rules / Edge cases / Output format`. Fixed a string-continuation bug that merged two tool bullets; softened "article TITLE" → "search terms"; added an explicit false-assumption rule; added a deep-section rule — *if the summary lacks the specific figure asked for, fetch the relevant section before answering rather than answering from the summary or declaring it unavailable.* Promoted from `prompts_iteration.py` (now removed).
- **Result:** On the targeted cases the agent now fetches sections (tool_calls 3–4 vs 1). Surfaced a real grounding gap: on `eiffel_tower_steps` the agent hallucinated the popular "1,665 steps" figure instead of the article's 1,710 — faithfulness judge correctly scored 0. Full-suite refresh pending.

### 6. Fixed `eiffel_tower_steps` gold fact (1,665 → 1,710) — `evals/cases.py`
- **Failure:** Investigating the eiffel failure showed the Eiffel Tower article contains no "1,665"; it states ~600 steps to the second floor and a historical 1,710-step climb to the top. The gold fact and reference were wrong (1,665 is a common-internet figure, not Wikipedia's).
- **Change:** `gold_facts` 1,665 → 1,710; reference / expected_behavior updated to the article's actual figures.
- **Result:** Case is now correctly grounded and reliably catches the agent hallucinating 1,665 (faithfulness=0) — a strong grounding test.
