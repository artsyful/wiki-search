"""Eval runner: run the agent on each case, grade, aggregate, and emit reports.

Run:  python -m evals.runner               # full suite
      python -m evals.runner --limit 3     # first 3 cases (quick smoke)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from src.agent import WikiAgent
from src.prompts import DEFAULT_MODEL

from .cases import CASES
from .graders import DIMENSIONS, JUDGE_MODEL, check_gold_facts, grade_case
from .report import write_html, write_json

RESULTS_DIR = "results"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pass_rate(values: list[float]) -> float:
    return _mean([1.0 if v >= 1 else 0.0 for v in values])


def _agg(scores: list[float], n_cases: int | None = None) -> dict:
    out = {"mean": _mean(scores), "pass_rate": _pass_rate(scores), "n": len(scores)}
    if n_cases is not None:
        out["n_cases"] = n_cases
    return out


def _aggregate(cases: list[dict]) -> dict:
    by_dim: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    by_cat: dict[str, list[float]] = {}
    overall: list[float] = []

    for case in cases:
        cat = case["category"]
        by_cat.setdefault(cat, [])
        for dim in DIMENSIONS:
            grader = case["graders"][dim]
            if grader["applicable"]:
                by_dim[dim].append(grader["score"])
                by_cat[cat].append(grader["score"])
                overall.append(grader["score"])

    return {
        "dimensions": {d: _agg(s) for d, s in by_dim.items()},
        "categories": {c: _agg(s) for c, s in by_cat.items()},
        "overall": _agg(overall),
    }


def run(agent_model: str, limit: int | None) -> dict:
    console = Console()
    client = anthropic.Anthropic()
    agent = WikiAgent(client=client, model=agent_model)
    cases = CASES[:limit] if limit else CASES

    case_results: list[dict] = []
    for i, case in enumerate(cases, 1):
        console.print(f"[dim]({i}/{len(cases)})[/dim] [bold cyan]{case.id}[/bold cyan]: {case.question}")
        with console.status("[dim]running agent + judges…[/dim]"):
            answer = agent.answer(case.question)
            graders = grade_case(client, case, answer)
        case_results.append(
            {
                "id": case.id,
                "question": case.question,
                "category": case.category,
                "expected_searches": case.expected_searches,
                "reference_answer": case.reference_answer,
                "expected_behavior": case.expected_behavior,
                "gold_facts": case.gold_facts,
                "notes": case.notes,
                "answer": {
                    "text": answer.text,
                    "citations": [{"title": c.title, "url": c.url} for c in answer.citations],
                    "used_search": answer.used_search,
                    "tool_calls": answer.tool_calls,
                    "searches": answer.searches,
                },
                "gold_facts_matched": check_gold_facts(case, answer),
                "graders": {
                    d: {
                        "applicable": g.applicable,
                        "score": g.score,
                        "passed": g.passed,
                        "rationale": g.rationale,
                    }
                    for d, g in graders.items()
                },
            }
        )

    return {
        "meta": {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agent_model": agent_model,
            "judge_model": JUDGE_MODEL,
            "n_cases": len(case_results),
        },
        "aggregates": _aggregate(case_results),
        "cases": case_results,
    }


def _print_summary(console: Console, report: dict) -> None:
    table = Table(title="Per-dimension results (mean 0–2 · pass rate at ≥ 1)")
    table.add_column("dimension")
    table.add_column("mean", justify="right")
    table.add_column("pass", justify="right")
    table.add_column("n", justify="right")
    for dim, agg in report["aggregates"]["dimensions"].items():
        table.add_row(dim, f"{agg['mean']:.2f}", f"{agg['pass_rate'] * 100:.0f}%", str(agg["n"]))
    overall = report["aggregates"]["overall"]
    table.add_row("[bold]overall[/bold]", f"[bold]{overall['mean']:.2f}[/bold]",
                  f"[bold]{overall['pass_rate'] * 100:.0f}%[/bold]", str(overall["n"]))
    console.print(table)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the Wikipedia agent eval suite.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N cases.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Agent model id.")
    args = parser.parse_args()

    console = Console()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY is not set.[/red] Copy .env.example to .env or export it.")
        sys.exit(1)

    report = run(args.model, args.limit)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = os.path.join(RESULTS_DIR, f"{stamp}.json")
    html_path = os.path.join(RESULTS_DIR, f"{stamp}.html")
    write_json(json_path, report)
    write_html(html_path, report)

    _print_summary(console, report)
    console.print(f"\n[green]JSON:[/green] {json_path}\n[green]HTML:[/green] {html_path}")


if __name__ == "__main__":
    main()
