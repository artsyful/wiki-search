# Prompt / Eval Iteration Log

Chronological record of the changes I made and what the evals (or my own review) caught at each
step. Timestamps are approximate, in Pacific time, across the core build (the primary ~2 hour session, 4:30-6:30 PM, on the evening of June 12), a ~30 min round of additional iterations that same evening, and a separate post-assignment session on June 15 (Session 2 below). Result numbers are the actual run outputs at the time.

## Core Build and First Iteration ~2 hour session (4:30-6:30 PM)

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
HEAD-check that each URL resolves. A three-case probe at 5:42 PM scored only 71% (17 grades) and 
exposed three real failures at once, 1. Wikipedia returning HTTP 429 under back-to-back load, 
2. The agent was over-running its tool budget and sometimes returning an empty final answer resulting 
in one case burning all its turns and still returning an empty answer, and 3. a false-premise Einstein case 
answering from parametric memory (the faithfulness judge correctly scored that 0).

### 4. Robustness pass and grader cleanup — ~5:52 PM
Fixed 2 issues the previous pass surfaced: 1. retry requests on 429 with exponential backoff, 2. dropped 
the tool cap from 8 to 5, and replaced an empty final answer by an explicit "couldn't ground an answer" 
message. In the same pass I split the graders expectations into two clean families, code graders return pass
fail, judges return a rubric score from 0 to 2 (labeled tiers, for example Grounded / Minor gap / Unsupported). 
The three-case re-run came back at 94% (17 grades across the three cases) with no rate-limit failures.

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
Made three prompt changes : 1. Reorganized the prompt from one prose block into labeled sections (Role, How 
to search, Core rules, Edge cases, Output format), and 2. added two rules: fetch the relevant section when a 
summary lacks the figure the question asks for, and 3. correct a false premise instead of playing along. A
targeted two-case run at 6:21 PM came in at 73% (11 grades). The deep-section rule did change behavior,
eiffel's tool calls went from 1 to 3, but the agent still did not provide a complete answer: it gave 
roughly 600 steps to the second floor and claimed no total to the top exists, so accuracy and correctness 
failed while faithfulness stayed at 2 (grounded, just incomplete). Inspecting why accuracy failed, it was looking
for "1,665", is what surfaced the next problem.

### 8. Corrected the Eiffel gold fact (1,665 to 1,710), and caught a real hallucination — ~6:24 PM
The per-case inspection showed the case itself was wrong: the wiki article does not state 1,665. It states
roughly 600 steps to the second floor and a historical 1,710-step climb to the top (1,665 is a
popular internet figure I had mistakenly used as the gold fact). I fixed the gold fact and reference
to the article's actual numbers. Re-running the corrected case immediately. However, this exposed something 
new and run-dependent: this time the agent itself answered "approximately 1,665 steps" rather than 
grounding in wikiepedia  1,710, and faithfulness correctly scored it 0. Nothing about the agent or 
prompt changed between that run and the grounded one minutes earlier, only the gold fact, so the flip from
grounded to hallucinated was pure model variance. The corrected case became a strong grounding test, with the
caveat that the behavior varies run to run.

## Additional iterations ~30 min session (6:30-7:00 PM)

### 9. Groundedness clause — ~6:33 PM
To fix the grounding issue, appended an explicit instruction to the faithfulness rule: even when you are
confident a detail is true from your own knowledge (a famous figure, quote, date, or "well-known" fact), 
do not include it unless a tool result contains it. This was the direct fix for the pattern the evals kept
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

### 18. Enabled accuracy and correctness grading on the post-cutoff temporal case — ~4:50 PM
The `hormuz_blocked_2026` case (a post-training-cutoff temporal probe) was only being graded on
behavior and faithfulness; accuracy and correctness both reported n/a. Accuracy was n/a because the
case had no `gold_facts`, and correctness was n/a because `TEMPORAL_RECENT` was not in
`FACTUAL_ANSWER_CATEGORIES`, so the correctness judge skipped it. I added the Wikipedia ground truth
as the `reference_answer` (the 2026 Strait of Hormuz crisis: largely blocked by Iran since 28
February 2026, after the US and Israel launched an air war and Khamenei was assassinated), set
`gold_facts=["28", "February", "2026", "Iran"]`, and added `TEMPORAL_RECENT` to the factual-answer
set. This is a category-wide change, which is intended: recent factual events should still be checked
for correctness and accuracy, not just grounding.

### 19. Gave the behavior judge the retrieved context so it stops calling grounded recent answers fabricated — ~5:00 PM
With accuracy and correctness now enabled, the `hormuz_blocked_2026` behavior judge was the holdout:
it scored 0 in three of four prior runs, calling the (correct, cited) answer a fabrication because
the event postdates its own training cutoff. The faithfulness judge mostly passed the same answer
because it is given the retrieved Wikipedia text and the behavior judge was not. The fix mirrors
faithfulness: `judge_behavior` now appends `answer.retrieved_context` to its prompt, and
`_BEHAVIOR_SYSTEM` gained a "Grounding vs fabrication" clause telling it to treat the retrieved text
as the source of truth for what Wikipedia contains, judge fabrication against that text rather than
its own knowledge, and that "your training cutoff is not evidence that an article does not exist."
Reran the case: behavior went from 0 to 2, with a rationale that explicitly cites the retrieved 2026
crisis article. All six dimensions now pass, overall 2.00.

### 20. Swapped the brittle Baltic population aggregation for a fixed-quantity (area) one — ~12:13 PM
The multi-hop aggregation case asked for the combined population of the three Baltic states. The
gold_facts were already drift-proof (the three country names, not a number), but the correctness
judge still graded against a `reference_answer` of "roughly 5.9 million", which goes stale every year
as Wikipedia updates each country's population, so a correct grounded answer could start diverging
from the reference and be wrongly docked. The case's own notes flagged this. Replaced it with
`baltic_states_total_area` ("combined land area of the three Baltic states"): same multi-hop shape
(three separate article fetches, then a sum) over a fixed quantity that does not drift. Kept
gold_facts on the three country names and set the reference to the area sum (~175,000 km2). Reran:
the agent did three searches and summed Estonia 45,335 + Latvia 64,573 + Lithuania 65,300 = 175,208
km2, and all six dimensions passed at 2.00.

### 21. Removed the self-contradictory Einstein last-words case — ~2:23 PM
`einstein_last_words` ("What were Albert Einstein's last words?") was failing correctness and
behavior (both 0) in the last full run while faithfulness passed (2). The case contradicted itself:
its `gold_facts` were the documented quote from List of last words (20th century) ("I want to go when
I want..."), but its `reference_answer` asserted the opposite, that his last words are "not known."
So a grounded, cited answer based on the documented quote was scored as a contradiction. I first
tried to reframe the case to credit both facts (the documented quote AND the popular anecdote that
his true final words were spoken in German to a nurse and went unrecorded). Reran: correctness and
behavior recovered to 2, but faithfulness dropped to 0, because the nurse anecdote is not retrievable
through the agent's tools (checked the List of last words article, the Albert Einstein article's
Death section, and the Notes section: none contain it; the [note 46] footnote is not surfaced by the
plain-text extract API). Requiring that caveat forced the agent to state an ungrounded claim. Rather
than keep iterating on a case whose "insufficient data" premise turned out to be false (Wikipedia
does document a last-words quote), I removed it. The found_but_insufficient category is still covered
by `pushpavanam_village_avg_age`. Suite is now 20 cases.

### 22. Added a straightforward deep-section case for breadth — ~5:43 PM
The only deep_section_factual case was `eiffel_tower_steps`, where the gold fact (1,710 steps) hides
in an oddly-named "Inauguration and the 1889 exposition" history section and the agent fails to drill
into it. So the dimension only ever demonstrated failure, with no positive example of the agent
doing deep-section retrieval when the section is well-signposted. Added `saturn_v_height` ("How tall
is the Saturn V rocket?"). Vetted against the live article first: the height is absent from the
summary the agent sees (so it forces a fetch_section) but lives in a clearly-named "Specifications"
section that is in the agent-visible section list. Reran: the agent did 1 search + 1 fetch_section,
reported "363 feet (111 meters)", and passed all six dimensions at 2.00. Suite is now 21 cases with
two deep-section cases: one pass-expected (saturn_v_height), one stress (eiffel_tower_steps).

### 23. Replaced section-specific fetch with a full-article fetch — `src/wiki_client.py`, `src/prompts.py`, `src/agent.py`
- **Failure:** the `fetch_section(title, section)` tool forced the agent to *name* a section, and it
  failed when the answer lived under an unintuitive heading. `eiffel_tower_steps` was the standing
  example: the 1,710-step figure sits in an "Inauguration and the 1889 exposition" history section,
  so across runs the agent fetched plausible-sounding sections, never reached it, and scored accuracy
  fail / correctness 1 (and, after the retrieval-grounded behavior judge, behavior 2 only because it
  honestly flagged the gap). The split's economy is really a *search*-stage concern (don't dump ~3
  full articles per query); at *fetch* time the agent has already chosen one article, so returning
  the whole body is a bounded, post-decision cost and avoids the section-guessing failure.
- **Change:** replaced `fetch_section(title, section)` with `fetch_article(title)` — one
  `prop=extracts&explaintext` call returning the full plain text (trailing boilerplate stripped,
  capped at 40k chars via `MAX_ARTICLE_CHARS`); renamed `SectionContent` → `ArticleContent` (dropped
  the `section` field); updated the tool schema (removed the `section` param) and the system-prompt
  guidance to "fetch the full article and read it; the detail may sit in a section whose title isn't
  the obvious one"; deleted the now-unused HTML-stripping helpers.
- **Result:** `eiffel_tower_steps` went from accuracy fail / correctness 1 to all six dimensions 2.00,
  and its tool use dropped from 2 searches + 3 fetches to 1 search + 1 fetch (fewer round trips).
  Full 21-case suite: overall mean 1.94/2, 99% pass; accuracy 100% (16), correctness 2.00, behavior
  1.95, faithfulness 1.86. No regression from the change: the one sub-2 cell is
  `list_switzerland_borders` (faithfulness 0), a summary-only case (0 fetches) where the agent added
  an ungrounded "doubly landlocked" factoid from memory, unrelated to the fetch tool.

### 24. Verified the list_switzerland_borders faithfulness 0 is a correct grade (no change) — analysis only
- **Question:** was the faithfulness judge right to score `list_switzerland_borders` a 0 for the
  claim that Liechtenstein is "one of only two doubly landlocked countries in the world"?
- **Check:** reconstructed what the agent actually retrieved (2 searches, 0 fetches; it cited only
  Switzerland and Geography of Switzerland). Those summaries contain "landlocked" only about
  *Switzerland*, never "doubly landlocked" and never "one of only two." The "doubly landlocked"
  descriptor lives in the Liechtenstein and Landlocked-country articles, which the agent never
  searched; and even Liechtenstein's own summary does not contain the "only two" framing. So the
  claim is true in the real world but absent from the retrieved text.
- **Result:** the grade is correct. It is exactly the grounding violation the dimension exists to
  catch (a true-but-unretrieved fact pulled from memory), and the judge correctly credited the five
  borders as supported and docked only the one material unsupported addition. No case or grader
  change. Side observation: `retrieved_context` is not persisted to the JSON report (used at grading
  time, then dropped), so post-hoc faithfulness audits require reconstructing the searches; serializing
  it (truncated) is a possible future reporting tweak.
