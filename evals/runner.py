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
from .graders import DIMENSIONS, JUDGE_DIMENSIONS, JUDGE_MODEL, grade_case
from .report import write_html, write_json

RESULTS_DIR = "results"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _aggregate(cases: list[dict]) -> dict:
    """Code dimensions aggregate to a pass rate; judge dimensions add a mean (0–2)."""
    dim_pass: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    dim_score: dict[str, list[float]] = {d: [] for d in JUDGE_DIMENSIONS}
    cat_pass: dict[str, list[float]] = {}
    overall_pass: list[float] = []
    judge_scores: list[float] = []

    for case in cases:
        cat = case["category"]
        cat_pass.setdefault(cat, [])
        for dim in DIMENSIONS:
            grader = case["graders"][dim]
            if not grader["applicable"]:
                continue
            passed = 1.0 if grader["passed"] else 0.0
            dim_pass[dim].append(passed)
            cat_pass[cat].append(passed)
            overall_pass.append(passed)
            if grader["kind"] == "judge":
                dim_score[dim].append(grader["score"])
                judge_scores.append(grader["score"])

    dims = {}
    for dim in DIMENSIONS:
        is_judge = dim in JUDGE_DIMENSIONS
        entry = {
            "kind": "judge" if is_judge else "code",
            "pass_rate": _mean(dim_pass[dim]),
            "n": len(dim_pass[dim]),
        }
        if is_judge:
            entry["mean"] = _mean(dim_score[dim])
        dims[dim] = entry

    return {
        "dimensions": dims,
        "categories": {c: {"pass_rate": _mean(v), "n": len(v)} for c, v in cat_pass.items()},
        "overall": {
            "pass_rate": _mean(overall_pass),
            "n": len(overall_pass),
            "judge_mean": _mean(judge_scores),
            "judge_n": len(judge_scores),
        },
    }


def run(agent_model: str, limit: int | None, ids: list[str] | None) -> dict:
    console = Console()
    client = anthropic.Anthropic()
    agent = WikiAgent(client=client, model=agent_model)
    cases = [c for c in CASES if c.id in ids] if ids else CASES
    if limit:
        cases = cases[:limit]

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
                "graders": {
                    d: {
                        "kind": g.kind,
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
    table = Table(title="Results — code graders: pass rate · judges: mean 0–2 + pass rate (≥ 1)")
    table.add_column("dimension")
    table.add_column("type")
    table.add_column("mean", justify="right")
    table.add_column("pass", justify="right")
    table.add_column("n", justify="right")
    for dim, agg in report["aggregates"]["dimensions"].items():
        mean = f"{agg['mean']:.2f}" if "mean" in agg else "—"
        table.add_row(dim, agg["kind"], mean, f"{agg['pass_rate'] * 100:.0f}%", str(agg["n"]))
    overall = report["aggregates"]["overall"]
    table.add_row(
        "[bold]overall[/bold]",
        "",
        f"[bold]{overall['judge_mean']:.2f}[/bold]",
        f"[bold]{overall['pass_rate'] * 100:.0f}%[/bold]",
        str(overall["n"]),
    )
    console.print(table)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the Wikipedia agent eval suite.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N cases.")
    parser.add_argument("--ids", default=None, help="Comma-separated case ids to run (subset).")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Agent model id.")
    args = parser.parse_args()

    console = Console()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY is not set.[/red] Copy .env.example to .env or export it.")
        sys.exit(1)

    ids = [s.strip() for s in args.ids.split(",")] if args.ids else None
    report = run(args.model, args.limit, ids)

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
