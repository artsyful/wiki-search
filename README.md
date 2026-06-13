# Wikipedia-Grounded Q&A Agent

A CLI agent that answers questions using **Claude (Sonnet 4.6)** + a two-tool **Wikipedia**
integration, plus an eval suite that grades answers with code checks and **Opus 4.8** LLM judges.
The agent is built to be *trustworthy*: it grounds every factual claim in retrieved Wikipedia
text, abstains rather than fabricating, and labels anything it answers without Wikipedia.

## Setup
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then add your key:  ANTHROPIC_API_KEY=sk-ant-...
```

## Run the CLI
Interactive REPL (ask many questions; `exit` or Ctrl-D to quit):
```bash
.venv/bin/python -m src.cli
```
Demo mode (runs curated sample questions end-to-end):
```bash
.venv/bin/python -m src.cli --demo
```
Each answer ends with a `Sources:` list and a one-line footer showing whether Wikipedia was
used (`🔍 Answered using Wikipedia (N sources)` vs `💡 Answered without Wikipedia`).

Example questions to try: *"How tall is Mount Everest?"*, *"What is the population of the capital
of the country that won the 2018 FIFA World Cup?"*, *"Tell me about Mercury."*,
*"What is 12,345 multiplied by 67?"* (answered directly, not from Wikipedia).

## Run the evals
```bash
.venv/bin/python -m evals.runner            # full suite
.venv/bin/python -m evals.runner --limit 3  # first 3 cases (quick)
.venv/bin/python -m evals.runner --ids everest_height,mercury_ambiguous  # specific cases
```
Each run prints a per-dimension summary table and writes two artifacts to `results/`: a
machine-readable `<timestamp>.json` and a self-contained `<timestamp>.html` report (open it in a
browser — summary cards, per-dimension/category charts, per-case grades, and a full transcript).

## Results (latest full run — 17 cases)
**Overall: 96% pass, judge mean 1.79/2 (82 grades).**

| Dimension | Type | Score |
|---|---|---|
| search_behavior | code | 100% pass |
| accuracy (gold-fact match) | code | 90% pass |
| citations (present + URL resolves) | code | 100% pass |
| correctness | Opus judge | 1.92/2 · 100% pass |
| faithfulness / grounding | Opus judge | 1.69/2 · 92% pass |
| behavior (special cases) | Opus judge | 1.76/2 · 94% pass |

What the evals taught us (see `docs/PROMPT_ITERATION.md`):
- **Grounding discipline is the hard part.** Early on the agent supplemented answers with
  confident-but-ungrounded "famous" facts (e.g. the popular "1,665 steps" for the Eiffel Tower).
  A targeted prompt rule fixed this — the agent now stays grounded in retrieved text.
- **Multi-hop / compute works well.** 3-hop chains, arithmetic over retrieved facts (Everest − K2),
  and cross-article aggregation (combined Baltic population) all pass.
- **LLM judges have a temporal blind spot.** On a real post-cutoff event (the 2026 Strait of
  Hormuz crisis), the agent correctly grounded its answer in Wikipedia, but the Opus judge —
  sharing the same training cutoff — wrongly penalized it as "speculative." A reminder that
  LLM-judge verdicts on recent events need a human in the loop.

## Design
Single-loop tool-using agent (Claude + `search_wikipedia` + `fetch_section` over the live
MediaWiki API), wrapped in a `rich` CLI. See **[docs/DESIGN.md](docs/DESIGN.md)** for the
agent/CLI design, **[docs/PRD.md](docs/PRD.md)** for product requirements, and
**[docs/EVALS.md](docs/EVALS.md)** for the eval design.
