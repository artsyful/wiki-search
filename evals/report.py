"""Report writers: machine-readable JSON + a self-contained offline HTML report.

Both consume the same plain-dict `report` structure the runner assembles, so this module
has no dependency on the grader/case types. The HTML uses only inline CSS + CSS bar charts
(no external CDN) so it renders offline. See docs/EVALS.md → Reporting.
"""

from __future__ import annotations

import html
import json

from .cases import CATEGORY_DESCRIPTIONS
from .graders import CODE_DIMENSIONS, DIMENSION_DESCRIPTIONS, DIMENSIONS, JUDGE_DIMENSIONS


def write_json(path: str, report: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)


def _esc(value: object) -> str:
    return html.escape(str(value))


def _verdict(grader: dict) -> str:
    if not grader["applicable"]:
        return "n/a"
    if grader["kind"] == "code":
        return "pass" if grader["passed"] else "fail"
    return str(int(grader["score"]))


def _score_badge(grader: dict) -> str:
    if not grader["applicable"]:
        return '<span class="badge na">n/a</span>'
    if grader["kind"] == "code":
        cls = "good" if grader["passed"] else "bad"
        return f'<span class="badge {cls}">{"pass" if grader["passed"] else "fail"}</span>'
    score = int(grader["score"])
    cls = {2: "good", 1: "mid", 0: "bad"}[score]
    return f'<span class="badge {cls}">{score}</span>'


# --------------------------------------------------------------------------- summary cards


def _card(dim: str, agg: dict) -> str:
    pass_pct = f"{agg['pass_rate'] * 100:.0f}%"
    if "mean" in agg:  # judge dimension
        sub = f"mean {agg['mean']:.2f}/2 · n={agg['n']}"
    else:  # code dimension
        sub = f"n={agg['n']}"
    return (
        f'<div class="card"><div class="card-title">{_esc(dim)}</div>'
        f'<div class="card-num">{pass_pct}</div><div class="card-sub">{sub}</div></div>'
    )


def _summary_cards(report: dict) -> str:
    dims = report["aggregates"]["dimensions"]
    code_row = "".join(_card(d, dims[d]) for d in CODE_DIMENSIONS)
    judge_row = "".join(_card(d, dims[d]) for d in JUDGE_DIMENSIONS)
    return (
        '<div class="card-row-label">Code graders</div>'
        f'<div class="cards">{code_row}</div>'
        '<div class="card-row-label">LLM judges</div>'
        f'<div class="cards">{judge_row}</div>'
    )


# --------------------------------------------------------------------------- stacked charts

# Segment order + colour class per outcome.
_CODE_SEGMENTS = [("pass", "c-green"), ("fail", "c-red"), ("na", "c-grey")]
_JUDGE_SEGMENTS = [("s2", "c-green"), ("s1", "c-yellow"), ("s0", "c-red"), ("na", "c-grey")]


def _dim_distribution(cases: list[dict], dim: str, is_judge: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        grader = case["graders"][dim]
        if not grader["applicable"]:
            key = "na"
        elif is_judge:
            key = f"s{int(grader['score'])}"
        else:
            key = "pass" if grader["passed"] else "fail"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _cat_distribution(cases: list[dict], category: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        if case["category"] != category:
            continue
        for dim in DIMENSIONS:
            grader = case["graders"][dim]
            if not grader["applicable"]:
                key = "na"
            else:
                key = "pass" if grader["passed"] else "fail"
            counts[key] = counts.get(key, 0) + 1
    return counts


def _stacked_bar(counts: dict[str, int], segments: list[tuple[str, str]]) -> str:
    total = sum(counts.values()) or 1
    cells = ""
    for key, css in segments:
        n = counts.get(key, 0)
        if n:
            cells += f'<div class="seg {css}" style="width:{n / total * 100:.1f}%" title="{key}={n}"></div>'
    return f'<div class="stack">{cells}</div>'


def _chart_dimensions(report: dict) -> str:
    cases = report["cases"]
    dims = report["aggregates"]["dimensions"]
    rows = ""
    for dim in DIMENSIONS:
        is_judge = dim in JUDGE_DIMENSIONS
        segments = _JUDGE_SEGMENTS if is_judge else _CODE_SEGMENTS
        bar = _stacked_bar(_dim_distribution(cases, dim, is_judge), segments)
        agg = dims[dim]
        label = f"{agg['pass_rate'] * 100:.0f}% pass · n={agg['n']}"
        rows += (
            f'<tr><td class="chart-name">{_esc(dim)}</td>'
            f'<td class="chart-bar">{bar}</td><td class="chart-num">{label}</td></tr>'
        )
    return f'<h3>By dimension</h3><table class="chart">{rows}</table>'


def _chart_categories(report: dict) -> str:
    cases = report["cases"]
    cats = report["aggregates"]["categories"]
    rows = ""
    for cat, agg in cats.items():
        bar = _stacked_bar(_cat_distribution(cases, cat), _CODE_SEGMENTS)
        label = f"{agg['pass_rate'] * 100:.0f}% pass · n={agg['n']}"
        rows += (
            f'<tr><td class="chart-name">{_esc(cat)}</td>'
            f'<td class="chart-bar">{bar}</td><td class="chart-num">{label}</td></tr>'
        )
    return f'<h3>By category</h3><table class="chart">{rows}</table>'


def _legend() -> str:
    return (
        '<div class="legend">'
        '<span class="lg"><i class="seg c-green"></i> pass / score 2</span>'
        '<span class="lg"><i class="seg c-yellow"></i> score 1</span>'
        '<span class="lg"><i class="seg c-red"></i> fail / score 0</span>'
        '<span class="lg"><i class="seg c-grey"></i> n/a</span></div>'
    )


# --------------------------------------------------------------------------- definitions


def _definitions() -> str:
    dim_items = "".join(
        f"<li><b>{_esc(d)}</b> — {_esc(desc)}</li>" for d, desc in DIMENSION_DESCRIPTIONS.items()
    )
    cat_items = "".join(
        f"<li><b>{_esc(c)}</b> — {_esc(desc)}</li>" for c, desc in CATEGORY_DESCRIPTIONS.items()
    )
    return (
        "<details><summary>Dimension / grader definitions</summary><ul>"
        + dim_items
        + "</ul></details>"
        "<details><summary>Case category definitions</summary><ul>"
        + cat_items
        + "</ul></details>"
    )


# --------------------------------------------------------------------------- per-case table


def _case_table(report: dict) -> str:
    rows = ""
    for case in report["cases"]:
        graders = case["graders"]
        cells = "".join(f"<td>{_score_badge(graders[d])}</td>" for d in DIMENSIONS)
        rows += (
            f'<tr><td class="id-cell"><div class="cid">{_esc(case["id"])}</div>'
            f'<div class="ccat">{_esc(case["category"])}</div></td>'
            f"{cells}<td>{case['answer']['searches']}</td></tr>"
        )
    header = "".join(f"<th>{_esc(d)}</th>" for d in DIMENSIONS)
    return (
        '<table class="cases"><thead><tr><th>id</th>'
        f"{header}<th>searches</th></tr></thead><tbody>{rows}</tbody></table>"
    )


# --------------------------------------------------------------------------- bottom collapsibles


def _detailed_grading(report: dict) -> str:
    blocks = ""
    for case in report["cases"]:
        graders = case["graders"]
        items = "".join(
            f'<li><b>{_esc(d)}</b> [{_verdict(graders[d])}]: {_esc(graders[d]["rationale"])}</li>'
            for d in DIMENSIONS
        )
        blocks += (
            f'<div class="grade-block"><div class="gb-id">{_esc(case["id"])} '
            f'[{_esc(case["category"])}]</div><ul>{items}</ul></div>'
        )
    return "<details><summary>Detailed grading (rationales)</summary>" + blocks + "</details>"


def _transcript(report: dict) -> str:
    blocks = ""
    for case in report["cases"]:
        answer = case["answer"]
        cites = "".join(
            f'<li><a href="{_esc(c["url"])}">{_esc(c["title"])}</a></li>' for c in answer["citations"]
        )
        cites_block = f"<ul class='cites'>{cites}</ul>" if cites else ""
        blocks += (
            f'<div class="transcript"><div class="t-q">Q [{_esc(case["category"])}]: '
            f'{_esc(case["question"])}</div>'
            f'<div class="t-a">{_esc(answer["text"])}</div>{cites_block}</div>'
        )
    return "<details><summary>Full Q&amp;A transcript</summary>" + blocks + "</details>"


_CSS = """
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:2rem auto;max-width:1100px;color:#1a1a1a;padding:0 1rem}
h1{margin-bottom:.2rem}h3{margin:1.2rem 0 .4rem}.meta{color:#666;margin-bottom:1.5rem}
.card-row-label{font-size:12px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.04em;margin:.6rem 0 .2rem}
.cards{display:flex;flex-wrap:wrap;gap:.75rem}
.card{flex:1;min-width:150px;border:1px solid #e3e3e3;border-radius:10px;padding:.7rem 1rem;background:#fafafa}
.card-title{font-size:12px;color:#666;text-transform:capitalize}
.card-num{font-size:2rem;font-weight:700}
.card-sub{font-size:12px;color:#777}
table{border-collapse:collapse;width:100%;margin:.3rem 0}
.chart td{padding:.18rem .5rem;vertical-align:middle}.chart-name{width:210px;text-transform:capitalize}
.chart-num{font-size:12px;color:#555;white-space:nowrap}
.stack{display:flex;width:240px;height:14px;border-radius:4px;overflow:hidden;background:#eee}
.seg{height:100%}.c-green{background:#2e8b57}.c-yellow{background:#c89010}.c-red{background:#c0392b}.c-grey{background:#bbb}
.legend{margin:.4rem 0;font-size:12px;color:#555}.legend .lg{margin-right:1rem;white-space:nowrap}
.legend i{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:middle;margin-right:.25rem}
.cases th,.cases td{border:1px solid #eee;padding:.3rem .5rem;font-size:13px;text-align:center}
.cases th{background:#f4f4f4}
.id-cell{text-align:left}.cid{font-weight:600}.ccat{font-size:11px;color:#999}
.badge{display:inline-block;min-width:1.4em;padding:.05em .4em;border-radius:5px;color:#fff;font-weight:700}
.badge.good{background:#2e8b57}.badge.mid{background:#c89010}.badge.bad{background:#c0392b}.badge.na{background:#bbb}
details{margin:.5rem 0;border:1px solid #eee;border-radius:8px;padding:.5rem .75rem;background:#fafafa}
summary{cursor:pointer;font-weight:600}
.grade-block{border-top:1px solid #eee;padding:.4rem 0}.gb-id{font-weight:600;color:#0a5}
.grade-block ul{margin:.2rem 0 .2rem 1rem;font-size:12px;color:#444}
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
        + _chart_dimensions(report)
        + _chart_categories(report)
        + _legend()
        + _definitions()
        + "<h3>Per-case results</h3>"
        + _case_table(report)
        + _detailed_grading(report)
        + _transcript(report)
        + "</body></html>"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
