"""Interactive REPL for the Wikipedia-grounded agent (see docs/DESIGN.md → CLI).

Run:  python -m src.cli            # interactive Q&A session
      python -m src.cli --demo     # run a curated set of sample questions
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.rule import Rule

from .agent import AgentAnswer, WikiAgent
from .prompts import DEFAULT_MODEL

DEMO_QUESTIONS = [
    "How tall is Mount Everest?",
    "What is the population of the capital of the country that won the 2018 FIFA World Cup?",
    "Tell me about Mercury.",
    "What is 12,345 multiplied by 67?",
    "What did my next-door neighbor eat for breakfast yesterday?",
]


def _render_answer(console: Console, answer: AgentAnswer) -> None:
    console.print("[bold]A:[/bold] ", end="")
    console.print(answer.text or "(no answer)")
    count = len(answer.citations)
    if answer.used_search and count:
        plural = "s" if count != 1 else ""
        console.print(f"[green]🔍 Answered using Wikipedia ({count} source{plural})[/green]")
    elif answer.used_search:
        console.print("[yellow]🔍 Searched Wikipedia (no citable answer found)[/yellow]")
    else:
        console.print("[blue]💡 Answered without Wikipedia[/blue]")
    console.print(Rule(style="dim"))


def _ask(console: Console, agent: WikiAgent, question: str) -> None:
    console.print(f"[bold cyan]Q:[/bold cyan] {question}")
    with console.status("[dim]Thinking…[/dim]", spinner="dots") as status:
        answer = agent.answer(question, on_progress=lambda msg: status.update(f"[dim]{msg}[/dim]"))
    _render_answer(console, answer)


def _run_demo(console: Console, agent: WikiAgent) -> None:
    console.print("[bold]Demo mode[/bold] — running sample questions.\n")
    for question in DEMO_QUESTIONS:
        _ask(console, agent, question)


def _run_interactive(console: Console, agent: WikiAgent) -> None:
    console.print("[bold]Wikipedia Q&A[/bold] — ask a question, or 'exit' to quit.\n")
    while True:
        try:
            question = console.input("[bold green]Ask a question ▷ [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")
            return
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            console.print("Goodbye.")
            return
        _ask(console, agent, question)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Wikipedia-grounded Q&A agent.")
    parser.add_argument("--demo", action="store_true", help="Run curated sample questions.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model id.")
    args = parser.parse_args()

    console = Console()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            "[red]ANTHROPIC_API_KEY is not set.[/red] Copy .env.example to .env and add your key, "
            "or export ANTHROPIC_API_KEY."
        )
        sys.exit(1)

    agent = WikiAgent(model=args.model)
    if args.demo:
        _run_demo(console, agent)
    else:
        _run_interactive(console, agent)


if __name__ == "__main__":
    main()
