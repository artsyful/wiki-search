# Prompt / Eval Iteration Log

Chronological record of the changes I made and what the evals (or my own review) caught at each
step. Timestamps are approximate, in Pacific time, across two working sessions: the core build during the primary ~2 hour session (4:30-6:30 PM) on the evening of June 12, and a round of additional iterations early on June 15. Result numbers are the actual run outputs at the time.

## Session 1 — June 12 (core build and first iterations)

### 1. Built the agent — ~5:08 PM
Stood up the system itself: a single tool-use loop where Claude calls two tools, `search_wikipedia`
and `fetch_section`, over a thin live MediaWiki client, plus a `rich` CLI that shows whether search
was used. No eval signal yet; this is the thing the rest of the log iterates on.

### 2. Built the eval harness — ~5:33 PM
Added the category-balanced case set (13 cases to start), the six graders, the runner, and the
JSON/HTML report. A smoke run over the first two cases passed cleanly (100%, 10 grades), confirming
the harness wired end to end.

### 3. Added the accuracy grader and citation URL checks; first real probe — ~5:40 PM
Added the cheap `accuracy` code grader (gold-fact substring match) and made `citations` actually
HEAD-check that each URL resolves. A three-case probe at 5:42 PM scored only 71% (17 grades) and exposed three genuine failures at once, Wikipedia returning HTTP 429 under back-to-back load, one case burning all its turns and returning an empty answer, and a false-premise Einstein case answering from parametric memory (the faithfulness judge correctly scored that 0).

### 4. Robustness pass and grader cleanup — ~5:52 PM
Fixed what the previous pass surfaced: retry requests on 429 with exponential backoff, dropped the tool cap from 8 to 5, and replaced an empty final answer by an explicit "couldn't ground an answer" message. In the same pass I split the graders into two clean families, code graders return pass/fail, judges return a rubric score from 0 to 2 (labeled tiers, for example Grounded / Minor gap / Unsupported). The three-case re-run came back at 94% (17 grades across the three cases) with no rate-limit failures.

### 5. Citation parser fix — ~6:01 PM
The citation grader flagged a Mercury 404 that turned out to be a code bug: the URL parser's
`rstrip(")")` was stripping the closing paren of a real disambiguation slug (`Mercury_(planet`),
producing a dead link. Changed it to only strip a trailing paren when it is unbalanced, so
`Mercury_(planet)` is preserved while wrapping punctuation is still removed.

### 6. Baseline full run — ~6:09 PM
First full-suite run: 95% pass, judge mean 1.81/2, 62 grades. Code graders strong (search 100%,
accuracy 89%, citations 100%); deep-section was the weakest category at 67%, which set the next
target.

### 7. Prompt restructure plus deep-section and false-premise rules — ~6:15 PM
Reorganized the prompt from one prose block into labeled sections (Role, How to search, Core rules,
Edge cases, Output format), and added two rules: fetch the relevant section when a summary lacks the
figure the question asks for, and correct a false premise instead of playing along. A targeted
two-case run at 6:21 PM came in at 73% (11 grades). The deep-section rule did change behavior,
eiffel's tool calls went from 1 to 3, but the agent still did not provide a complete answer: it gave roughly 600 steps to the second floor and claimed no total to the top exists, so accuracy and correctness failed while
faithfulness stayed at 2 (grounded, just incomplete). Inspecting why accuracy failed, it was looking
for "1,665", is what surfaced the next problem.

### 8. Corrected the Eiffel gold fact (1,665 to 1,710), and caught a real hallucination — ~6:24 PM
The per-case inspection showed the case itself was wrong: the article never says 1,665. It states
roughly 600 steps to the second floor and a historical 1,710-step climb to the top (1,665 is a
popular internet figure I had mistakenly used as the gold fact). I fixed the gold fact and reference
to the article's actual numbers. Re-running the corrected case immediately exposed something new and
run-dependent: this time the agent itself answered "approximately 1,665 steps" rather than grounding
1,710, and faithfulness correctly scored it 0. Nothing about the agent or prompt changed between
that run and the grounded one minutes earlier, only the gold fact, so the flip from grounded to
hallucinated was pure model variance. The corrected case became a strong grounding test, with the
caveat that the behavior varies run to run.

### 9. Groundedness clause — ~6:33 PM
Appended an explicit instruction to the faithfulness rule: even when you are confident a detail is
true from your own knowledge (a famous figure, quote, date, or "well-known" fact), do not include
it unless a tool result contains it. This was the direct fix for the pattern the evals kept
surfacing, the agent garnishing a grounded answer with true-but-unretrieved facts.

### 10. Expanded the suite (13 to 17) and found the judge blind spot — ~6:34 PM
Added coverage for the gaps: two temporal cases (a post-cutoff event and an immutable past date), a
three-hop chain, an arithmetic case, a cross-article aggregation, and a partial-answer case. The
full run at 6:47 PM held quality at 96% pass, judge mean 1.79/2, 82 grades, with the new
multi-hop, compute, and aggregation cases all passing. It also surfaced the headline finding: on the
post-cutoff `hormuz_blocked_2026` case the agent grounded its answer in the real Wikipedia article,
but the Opus behavior judge, sharing the same training cutoff, scored it 0 and called it
speculative.

## Session 2 — June 15 (additional iterations)

### 11. Plain-text output rule — ~1:41 AM
The agent was emitting Markdown (`**`, `##`) that rendered as literal noise in the CLI and report.
Added an output rule to write in plain text with no Markdown, and switched the report to show rubric
labels instead of raw 0/1/2 judge scores.

### 12. Behavior-judge calibration and a number-robust accuracy grader — ~1:49 AM
Two grader fixes. Rewrote the behavior judge with explicit per-case-type rubrics (answerable
factual including temporal, false premise, ambiguous, unanswerable, honest scoping, subjective or
speculative, no-search) mapped to the 2/1/0 scale. Separately, made the accuracy grader normalize
thousands separators on both sides before matching, so a gold fact like `1,710` matches an answer
that writes `1710`. The full run at 2:06 AM came in at 94% pass, judge mean 1.79/2: the calibration
worked (hormuz behavior moved 0 to 2 in this run), and the dip from 96% was one case,
`einstein_last_words`, returning the empty-answer fallback despite successful retrieval.

### 13. Fixed the forced-final empty answer plus a Grounding section — ~2:40 AM
Diagnosed the einstein empty answer as deterministic, not flaky: across repeated single-case runs,
the only empty result was the run that hit the tool-call cap. On that forced-final turn (tool choice
disabled, adaptive thinking on) thinking consumed the whole token budget and the visible answer came
back empty. Fix: disable thinking on the forced-final turn so the full budget goes to the answer
text. Also added a dedicated Grounding section to the prompt. A two-case re-run at 2:43 AM had
einstein and mercury both passing every dimension, einstein's correctness and behavior back to 2.

### 14. Enabled the accuracy grader on four more cases — ~2:59 AM
Accuracy was n/a wherever `gold_facts` was empty, leaving baltic, mercury, einstein, and pushpavanam
with no cheap deterministic signal. Added stable, article-verified gold facts for each (baltic now
uses the three country names rather than the volatile population sum). The full run at 3:23 AM came
in at 92% pass, judge mean 1.74/2, 86 grades. Notably, hormuz behavior had flipped back to 0 in this
run even though the same calibrated judge scored it 2 earlier, which is itself the lesson: the judge
is non-deterministic on genuinely post-cutoff facts, so these cases need multi-run aggregation and a
human in the loop.

### 15. Final case polish and last full run — ~3:26 AM
Tidied the remaining cases (pushpavanam gold facts and a category description) and ran the full suite
once more to land on a consistent final snapshot.

### 16. Cleaner report design and four behavior-coverage cases — ~12:37 PM
Reworked the HTML report into a light/dark design: headline summary cards, code-vs-judge grader bars
with a definitions drawer, a category-definitions collapsible above the per-case table, and explicit
n/a cells (the by-category chart was dropped). Added four cases that activate previously-dead
behavior-judge branches: `list_switzerland_borders` (closed-set enumeration, with the Liechtenstein
completeness trap), `subjective_best_language` and `speculative_london_rain` (two new abstention
triggers distinct from the private/unknowable one), and `meta_capabilities` (a no-search
self-description path). The full 21-case run came in at 94% pass, judge mean 1.81/2, 98 grades, and
all four new cases passed as designed (the three abstention/meta cases at 0 searches with behavior 2,
the enumeration case clean with all five countries). The two persistent failures recurred:
`einstein_last_words` hit the tool-call cap and returned a non-answer (the open robustness item), and
`hormuz_blocked_2026` behavior again landed at 0 (the same post-cutoff judge variance).

### 17. "Give your final answer now" nudge on the forced-final turn — ~1:45 PM
The entry-13 fix stopped *empty* answers but not the related failure where, after hitting the
tool-call cap mid-investigation, the model emitted a "&lt;thinking&gt;… let me fetch more" monologue
instead of an answer (baltic, and einstein whenever it reached the cap). Added a user-turn
instruction on the forced-final turn: it has hit the tool limit and must give its final answer now
from what it already retrieved, abstaining honestly if it couldn't find something. Ran the einstein
case, which this time did hit the cap (tool_calls=5, 3 searches): instead of the previous non-answer
it returned a grounded answer (faithfulness 2, behavior 2, accuracy and citations pass, correctness
1), with no empty fallback and no thinking-tag leak. The exact cap-hit path that used to fail now
produces a real answer.
