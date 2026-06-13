"""Report writers: machine-readable JSON + a self-contained offline HTML report.

Both consume the same plain-dict `report` structure the runner assembles, so this module
has no dependency on the grader/case types. The HTML uses only inline CSS + CSS bar charts
(no external CDN) so it renders offline. See EVALS.md → Reporting.
"""

from __future__ import annotations

import html
import json

from .cases import CATEGORY_DESCRIPTIONS
from .graders import DIMENSION_DESCRIPTIONS


def write_json(path: str, report: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)


def _esc(value: object) -> str:
    return html.escape(str(value))


def _bar(mean: float | None, pass_rate: float | None, n: int) -> str:
    if mean is None:
        return '<span class="na">n/a</span>'
    pct = mean / 2 * 100
    return (
        f'<div class="bar-wrap"><div class="bar" style="width:{pct:.0f}%"></div></div>'
        f'<span class="bar-label">{mean:.2f}/2 · {pass_rate * 100:.0f}% pass · n={n}</span>'
    )


def _score_badge(grader: dict) -> str:
    if not grader["applicable"]:
        return '<span class="badge na">n/a</span>'
    score = int(grader["score"])
    cls = {2: "good", 1: "mid", 0: "bad"}[score]
    return f'<span class="badge {cls}">{score}</span>'


def _summary_cards(report: dict) -> str:
    cards = []
    overall = report["aggregates"]["overall"]
    cards.append(
        '<div class="card"><div class="card-title">Overall</div>'
        f'<div class="card-num">{overall["mean"]:.2f}<span>/2</span></div>'
        f'<div class="card-sub">{overall["pass_rate"] * 100:.0f}% pass · {overall["n"]} grades</div></div>'
    )
    for dim, agg in report["aggregates"]["dimensions"].items():
        cards.append(
            f'<div class="card"><div class="card-title">{_esc(dim)}</div>'
            f'<div class="card-num">{agg["mean"]:.2f}<span>/2</span></div>'
            f'<div class="card-sub">{agg["pass_rate"] * 100:.0f}% pass · n={agg["n"]}</div></div>'
        )
    return '<div class="cards">' + "".join(cards) + "</div>"


def _chart(title: str, rows: dict) -> str:
    items = []
    for name, agg in rows.items():
        items.append(
            f'<tr><td class="chart-name">{_esc(name)}</td>'
            f'<td class="chart-bar">{_bar(agg["mean"], agg["pass_rate"], agg["n"])}</td></tr>'
        )
    return f'<h3>{_esc(title)}</h3><table class="chart">{"".join(items)}</table>'


def _case_rows(report: dict) -> str:
    from .graders import DIMENSIONS

    rows = []
    for case in report["cases"]:
        graders = case["graders"]
        cells = "".join(f"<td>{_score_badge(graders[d])}</td>" for d in DIMENSIONS)
        gold = case["gold_facts_matched"]
        gold_txt = "—" if gold is None else ("✓" if gold else "✗")
        rationales = "<br>".join(
            f"<b>{_esc(d)}:</b> {_esc(graders[d]['rationale'])}" for d in DIMENSIONS
        )
        rows.append(
            f'<tr class="case-head"><td>{_esc(case["id"])}</td>'
            f'<td>{_esc(case["category"])}</td>'
            f'<td class="q">{_esc(case["question"])}</td>'
            f"{cells}"
            f'<td>{case["answer"]["searches"]}</td>'
            f"<td>{gold_txt}</td></tr>"
            f'<tr class="case-detail"><td colspan="{4 + len(DIMENSIONS)}">'
            f'<div class="rationale">{rationales}</div></td></tr>'
        )
    header_dims = "".join(f"<th>{_esc(d)}</th>" for d in DIMENSIONS)
    return (
        '<table class="cases"><thead><tr><th>id</th><th>category</th><th>question</th>'
        f"{header_dims}<th>searches</th><th>gold</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _definitions() -> str:
    dim_items = "".join(
        f"<li><b>{_esc(d)}</b> — {_esc(desc)}</li>" for d, desc in DIMENSION_DESCRIPTIONS.items()
    )
    cat_items = "".join(
        f"<li><b>{_esc(c)}</b> — {_esc(desc)}</li>" for c, desc in CATEGORY_DESCRIPTIONS.items()
    )
    return (
        "<details><summary>Grader definitions</summary><ul>" + dim_items + "</ul></details>"
        "<details><summary>Case categories</summary><ul>" + cat_items + "</ul></details>"
    )


def _transcript(report: dict) -> str:
    blocks = []
    for case in report["cases"]:
        answer = case["answer"]
        cites = "".join(
            f'<li><a href="{_esc(c["url"])}">{_esc(c["title"])}</a></li>'
            for c in answer["citations"]
        )
        cites_block = f"<ul class='cites'>{cites}</ul>" if cites else ""
        blocks.append(
            f'<div class="transcript"><div class="t-q">Q [{_esc(case["category"])}]: '
            f'{_esc(case["question"])}</div>'
            f'<div class="t-a">{_esc(answer["text"])}</div>{cites_block}</div>'
        )
    return "<details><summary>Full Q&amp;A transcript</summary>" + "".join(blocks) + "</details>"


_CSS = """
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:2rem auto;max-width:1100px;color:#1a1a1a;padding:0 1rem}
h1{margin-bottom:.2rem}.meta{color:#666;margin-bottom:1.5rem}
.cards{display:flex;flex-wrap:wrap;gap:.75rem;margin:1rem 0}
.card{flex:1;min-width:140px;border:1px solid #e3e3e3;border-radius:10px;padding:.75rem 1rem;background:#fafafa}
.card-title{font-size:12px;color:#666;text-transform:capitalize}
.card-num{font-size:1.8rem;font-weight:700}.card-num span{font-size:1rem;color:#999;font-weight:400}
.card-sub{font-size:12px;color:#777}
table{border-collapse:collapse;width:100%;margin:.5rem 0}
.chart td{padding:.2rem .4rem;vertical-align:middle}.chart-name{width:230px;text-transform:capitalize}
.bar-wrap{display:inline-block;width:220px;height:12px;background:#eee;border-radius:6px;overflow:hidden;vertical-align:middle}
.bar{height:100%;background:linear-gradient(90deg,#d98,#5a8)}
.bar-label{font-size:12px;color:#555;margin-left:.5rem}
.cases th,.cases td{border:1px solid #eee;padding:.35rem .5rem;font-size:13px;text-align:center}
.cases th{background:#f4f4f4}.cases .q{text-align:left;max-width:320px}
.case-detail td{text-align:left;background:#fbfbfb;color:#444;font-size:12px}
.rationale{padding:.25rem .5rem}
.badge{display:inline-block;min-width:1.4em;padding:.05em .4em;border-radius:5px;color:#fff;font-weight:700}
.badge.good{background:#2e8b57}.badge.mid{background:#c89010}.badge.bad{background:#c0392b}.badge.na{background:#bbb}
.na{color:#999}
details{margin:.5rem 0;border:1px solid #eee;border-radius:8px;padding:.5rem .75rem;background:#fafafa}
summary{cursor:pointer;font-weight:600}
.transcript{border-top:1px solid #eee;padding:.6rem 0}.t-q{font-weight:600;color:#0a5}
.t-a{white-space:pre-wrap;margin:.3rem 0}.cites{margin:.2rem 0 .2rem 1rem;color:#555}
"""


def write_html(path: str, report: dict) -> None:
    meta = report["meta"]
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Wiki-search eval — {_esc(meta['timestamp'])}</title>"
        f"<style>{_CSS}</style></head><body>"
        "<h1>Wikipedia-Grounded Q&amp;A — Eval Report</h1>"
        f"<div class='meta'>Agent: {_esc(meta['agent_model'])} · Judge: {_esc(meta['judge_model'])} "
        f"· {meta['n_cases']} cases · {_esc(meta['timestamp'])}</div>"
        + _summary_cards(report)
        + _chart("By dimension", report["aggregates"]["dimensions"])
        + _chart("By category", report["aggregates"]["categories"])
        + "<h3>Per-case results</h3>"
        + _case_rows(report)
        + _definitions()
        + _transcript(report)
        + "</body></html>"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
