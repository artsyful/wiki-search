# Prompt / Eval Iteration Log

Chronological record of the changes I made and what the evals (or my own review) caught at each
step. Timestamps are approximate, in Pacific time, across two working sessions: the core build during the primary ~2 hour session (4:30-6:30 PM) on the evening of June 12, followed by a ~30 min round of additional iterations. Result numbers are the actual run outputs at the time.

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