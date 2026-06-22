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

Example questions to try (distinct from the eval cases):
- In what U.S. city was the director of Pulp Fiction born?
- How many individual iron pieces were used to construct the Eiffel Tower?
- Combined, how many Academy Awards did the films 'Titanic' and 'The Lord of the Rings: The Return of the King' win? Give the total.
- In what year did World War II end?

## Run the evals
```bash
.venv/bin/python -m evals.runner            # full suite
.venv/bin/python -m evals.runner --list     # list every case id + question, then exit
.venv/bin/python -m evals.runner --limit 3  # first 3 cases (quick)
.venv/bin/python -m evals.runner --ids everest_height,mercury_ambiguous  # specific cases
```
Use `--list` to see all case ids, then `--ids <id1,id2>` to run just those. Each run prints a
per-dimension summary table and writes two artifacts to `results/` (retained per run): a
machine-readable `<timestamp>.json` and a self-contained `<timestamp>.html` report. Open the HTML
in a browser for summary cards, a "needs attention" spotlight, a per-dimension chart, the
per-case grid, and a per-case "answer + grading" section.

## Results
Latest full run (21 cases): **overall 99% pass, judge mean 1.94/2**. Per-dimension and per-case
detail live in the timestamped reports under [`results/`](results/) (open the latest `.html`).

What the evals taught us (see [`docs/PROMPT_ITERATION.md`](docs/PROMPT_ITERATION.md)):
- **Grounding discipline is the hard part.** Early on the agent supplemented answers with
  confident-but-ungrounded "famous" facts (e.g. the popular "1,665 steps" for the Eiffel Tower).
  A targeted prompt rule fixed this: the agent now stays grounded in retrieved text.
- **Multi-hop and compute work well.** 3-hop chains, arithmetic over retrieved facts (Everest
  minus K2), and cross-article aggregation (combined Baltic states' land area) all pass.
- **LLM judges have a temporal blind spot.** On a real post-cutoff event (the 2026 Strait of
  Hormuz crisis), the agent correctly grounded its answer in Wikipedia, but the Opus judge,
  sharing the same training cutoff, wrongly penalized it as "speculative." A reminder that
  LLM-judge verdicts on recent events need a human in the loop.

## Requirements and Design
Single-loop tool-using agent (Claude + `search_wikipedia` + `fetch_article` over the live
MediaWiki API), wrapped in a `rich` CLI. See **[docs/DESIGN.md](docs/DESIGN.md)** for the
agent/CLI design, **[docs/PRD.md](docs/PRD.md)** for product requirements, and
**[docs/EVALS.md](docs/EVALS.md)** for the eval design.
