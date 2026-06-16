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
.venv/bin/python -m evals.runner --limit 3  # first 3 cases (quick)
.venv/bin/python -m evals.runner --ids everest_height,mercury_ambiguous  # specific cases
```
Each run prints a per-dimension summary table and writes two artifacts to `results/`: a
machine-readable `<timestamp>.json` and a self-contained `<timestamp>.html` report. Open the HTML
in a browser for summary cards, per-dimension and per-category charts, a "needs attention"
spotlight, the per-case grade table, and a full Q&A transcript.

## Results
Latest full run (17 cases): **overall 96% pass, judge mean 1.79/2**. Per-dimension and per-case
detail live in the timestamped reports under [`results/`](results/) (open the latest `.html`).

## Requirements and Design
Single-loop tool-using agent (Claude + `search_wikipedia` + `fetch_section` over the live
MediaWiki API), wrapped in a `rich` CLI. See **[docs/DESIGN.md](docs/DESIGN.md)** for the
agent/CLI design, **[docs/PRD.md](docs/PRD.md)** for product requirements, and
**[docs/EVALS.md](docs/EVALS.md)** for the eval design.
