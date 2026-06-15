"""Report writers: machine-readable JSON + a self-contained offline HTML report.

Both consume the same plain-dict `report` structure the runner assembles, so this module
has no dependency on the grader/case types. The HTML uses only inline CSS (no external CDN)
so it renders offline, and supports light/dark via CSS variables. See docs/EVALS.md.
"""

from __future__ import annotations

import html
import json

from .cases import CATEGORY_DESCRIPTIONS
from .graders import (
    CODE_DIMENSIONS,
    CORRECTNESS,
    DIMENSION_DESCRIPTIONS,
    DIMENSIONS,
    FAITHFULNESS,
    JUDGE_DIMENSIONS,
    JUDGE_SCORE_LABELS,
)

# Dimensions surfaced as headline summary cards (the quality story).
SUMMARY_CARDS = [CORRECTNESS, FAITHFULNESS, "behavior", "citations"]


def write_json(path: str, report: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)


def _esc(value: object) -> str:
    return html.escape(str(value))


def _label(dim: str) -> str:
    return dim.replace("_", " ")


def _verdict(grader: dict, dim: str) -> str:
    if not grader["applicable"]:
        return "n/a"
    if grader["kind"] == "code":
        return "pass" if grader["passed"] else "fail"
    return JUDGE_SCORE_LABELS[dim][int(grader["score"])]


# --------------------------------------------------------------------------- counts


def _counts(cases: list[dict], dim: str, kind: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for case in cases:
        g = case["graders"][dim]
        if not g["applicable"]:
            key = "na"
        elif kind == "code":
            key = "pass" if g["passed"] else "fail"
        else:
            key = f"s{int(g['score'])}"
        out[key] = out.get(key, 0) + 1
    return out


def _track(segments: list[tuple[int, str]], total: int) -> str:
    """Horizontal stacked bar; segments are (count, css-var). Widths cover applicable total."""
    if total == 0:
        return '<span class="er-track"></span>'
    cells = "".join(
        f'<span style="width:{n / total * 100:.1f}%;background:var({var})"></span>'
        for n, var in segments
        if n
    )
    return f'<span class="er-track">{cells}</span>'


# --------------------------------------------------------------------------- summary cards


def _card(label: str, pct: str, sub: str) -> str:
    return (
        '<div style="background:var(--color-background-secondary);border-radius:8px;padding:.8rem 1rem">'
        f'<div style="font-size:12px;color:var(--color-text-secondary)">{_esc(label)}</div>'
        f'<div style="font-size:24px;font-weight:500">{pct}</div>'
        f'<div style="font-size:11px;color:var(--color-text-tertiary)">{sub}</div></div>'
    )


def _summary_cards(report: dict) -> str:
    cases = report["cases"]
    cards = ""
    for dim in SUMMARY_CARDS:
        agg = report["aggregates"]["dimensions"][dim]
        is_judge = dim in JUDGE_DIMENSIONS
        c = _counts(cases, dim, "judge" if is_judge else "code")
        if is_judge:
            total = c.get("s2", 0) + c.get("s1", 0) + c.get("s0", 0)
            passed = c.get("s2", 0) + c.get("s1", 0)
            sub = f"{passed} / {total} · mean {agg['mean']:.2f}/2"
        else:
            total = c.get("pass", 0) + c.get("fail", 0)
            passed = c.get("pass", 0)
            sub = f"{passed} / {total}"
        pct = f"{(passed / total * 100):.0f}%" if total else "—"
        cards += _card(_label(dim), pct, sub)
    return (
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));'
        f'gap:12px;margin:1rem 0">{cards}</div>'
    )


def _legend() -> str:
    sw = "width:10px;height:10px;border-radius:2px"
    return (
        '<div style="display:flex;gap:16px;font-size:11px;color:var(--color-text-secondary);'
        'margin:1rem 0 6px;flex-wrap:wrap">'
        f'<span style="display:flex;align-items:center;gap:5px"><span style="{sw};background:var(--color-text-success)"></span>pass / top</span>'
        f'<span style="display:flex;align-items:center;gap:5px"><span style="{sw};background:var(--color-text-warning)"></span>partial</span>'
        f'<span style="display:flex;align-items:center;gap:5px"><span style="{sw};background:var(--color-text-danger)"></span>fail / bottom</span>'
        '<span style="color:var(--color-text-tertiary)">bars cover applicable cases · n/a shown beside the count</span></div>'
    )


# --------------------------------------------------------------------------- grader bars + defs


def _cnt_text(passed: int, total: int, na: int) -> str:
    base = f"{passed} / {total}" if total else "—"
    return base + (f' <span style="opacity:.6">· {na} n/a</span>' if na else "")


def _bar_row(dim: str, track: str, cnt: str) -> str:
    return (
        f'<div class="er-row"><span class="er-lab">{_esc(_label(dim))}</span>{track}'
        f'<span class="er-cnt">{cnt}</span></div>'
    )


def _grader_bars(report: dict) -> str:
    cases = report["cases"]
    code_rows = ""
    for dim in CODE_DIMENSIONS:
        c = _counts(cases, dim, "code")
        p, f, na = c.get("pass", 0), c.get("fail", 0), c.get("na", 0)
        track = _track([(p, "--color-text-success"), (f, "--color-text-danger")], p + f)
        code_rows += _bar_row(dim, track, _cnt_text(p, p + f, na))

    judge_rows = ""
    for dim in JUDGE_DIMENSIONS:
        c = _counts(cases, dim, "judge")
        s2, s1, s0, na = c.get("s2", 0), c.get("s1", 0), c.get("s0", 0), c.get("na", 0)
        total = s2 + s1 + s0
        track = _track(
            [(s2, "--color-text-success"), (s1, "--color-text-warning"), (s0, "--color-text-danger")],
            total,
        )
        judge_rows += _bar_row(dim, track, _cnt_text(s2 + s1, total, na))

    defs = ""
    for dim in DIMENSIONS:
        kind = "judge" if dim in JUDGE_DIMENSIONS else "code"
        defs += (
            '<div style="margin:6px 0"><span style="font-weight:500">'
            f'{_esc(dim)}</span> <span style="font-size:10px;padding:1px 6px;border-radius:4px;'
            'background:var(--color-background-secondary);color:var(--color-text-tertiary)">'
            f'{kind}</span><br><span style="color:var(--color-text-secondary)">'
            f'{_esc(DIMENSION_DESCRIPTIONS[dim])}</span></div>'
        )

    return (
        '<div class="er-card">'
        '<p class="er-sec">Code graders <span style="color:var(--color-text-tertiary)">(deterministic)</span></p>'
        f"{code_rows}"
        '<p class="er-sec" style="margin-top:1.25rem">Judge <span style="color:var(--color-text-tertiary)">(semantic, 0–2)</span></p>'
        f"{judge_rows}"
        '<details style="margin-top:1.1rem;border-top:0.5px solid var(--color-border-tertiary);padding-top:10px">'
        '<summary style="font-size:12px;color:var(--color-text-secondary);font-weight:500">Definitions — graders</summary>'
        f'<div style="margin-top:10px;font-size:12px;line-height:1.55">{defs}</div></details></div>'
    )


# --------------------------------------------------------------------------- per-case table


def _cell(grader: dict, dim: str) -> str:
    if not grader["applicable"]:
        return '<span class="er-pill" style="color:var(--color-text-tertiary)">n/a</span>'
    if grader["kind"] == "code":
        if grader["passed"]:
            return '<span style="color:var(--color-text-success)">✓</span>'
        return '<span style="color:var(--color-text-danger)">✗</span>'
    score = int(grader["score"])
    tone = {2: "success", 1: "warning", 0: "danger"}[score]
    label = JUDGE_SCORE_LABELS[dim][score]
    return (
        f'<span class="er-pill" style="background:var(--color-background-{tone});'
        f'color:var(--color-text-{tone})">{_esc(label)}</span>'
    )


def _category_defs(report: dict) -> str:
    present = {c["category"] for c in report["cases"]}
    items = ""
    for cat, desc in CATEGORY_DESCRIPTIONS.items():
        if cat not in present:
            continue
        items += (
            '<div style="margin:6px 0"><span style="font-weight:500;font-family:var(--font-mono);'
            f'font-size:11px">{_esc(cat)}</span> — <span style="color:var(--color-text-secondary)">'
            f'{_esc(desc)}</span></div>'
        )
    return (
        '<details style="margin:0 0 12px"><summary style="font-size:12px;'
        'color:var(--color-text-secondary);font-weight:500">Definitions — categories</summary>'
        f'<div style="margin-top:10px;font-size:12px;line-height:1.55">{items}</div></details>'
    )


def _case_table(report: dict) -> str:
    cols = '<col style="width:22%">' + "".join(
        f'<col style="width:{78 / len(DIMENSIONS):.1f}%">' for _ in DIMENSIONS
    )
    header = '<th style="text-align:left">case</th>' + "".join(
        f"<th>{_esc(_label(d))}</th>" for d in DIMENSIONS
    )
    rows = ""
    for case in report["cases"]:
        cells = "".join(f"<td>{_cell(case['graders'][d], d)}</td>" for d in DIMENSIONS)
        rows += (
            '<tr><td style="text-align:left;overflow:hidden">'
            f'<div style="font-family:var(--font-mono);font-size:11px">{_esc(case["id"])}</div>'
            f'<div style="font-size:10px;color:var(--color-text-tertiary)">{_esc(case["category"])}</div></td>'
            f"{cells}</tr>"
        )
    return (
        '<div class="er-card"><p class="er-sec">Per-case results</p>'
        + _category_defs(report)
        + f'<table class="er-tbl"><colgroup>{cols}</colgroup>'
        + f"<thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>"
    )


# --------------------------------------------------------------------------- spotlight (drill-down)


def _spotlight(report: dict) -> str:
    failing: list[tuple[str, str, list[str]]] = []
    ungrounded: list[tuple[str, str]] = []
    for case in report["cases"]:
        g = case["graders"]
        bad = []
        for dim in DIMENSIONS:
            x = g[dim]
            if not x["applicable"]:
                continue
            if x["kind"] == "code" and not x["passed"]:
                bad.append(f"{dim}: fail")
            elif x["kind"] == "judge" and x["score"] < 2:
                bad.append(f"{dim}: {_verdict(x, dim)}")
        if bad:
            failing.append((case["id"], case["category"], bad))
        corr, faith = g[CORRECTNESS], g[FAITHFULNESS]
        if corr["applicable"] and faith["applicable"] and corr["score"] == 2 and faith["score"] == 0:
            ungrounded.append((case["id"], faith["rationale"]))

    if not failing and not ungrounded:
        return '<div class="er-card"><p class="er-sec">Needs attention</p><div style="font-size:12px;color:var(--color-text-success)">No failures.</div></div>'

    body = ""
    if ungrounded:
        items = "".join(
            f'<li><b>{_esc(cid)}</b> — correct answer but ungrounded: {_esc(r)}</li>'
            for cid, r in ungrounded
        )
        body += '<div class="spot-h">Right answer, wrong grounding (correctness 2 · faithfulness 0)</div><ul>' + items + "</ul>"
    if failing:
        items = "".join(
            f'<li><b>{_esc(cid)}</b> <span style="color:var(--color-text-tertiary)">[{_esc(cat)}]</span> — {_esc(", ".join(bad))}</li>'
            for cid, cat, bad in failing
        )
        body += '<div class="spot-h">Cases needing attention</div><ul>' + items + "</ul>"
    return f'<div class="er-card spotlight"><p class="er-sec">Needs attention</p>{body}</div>'


# --------------------------------------------------------------------------- detailed Q&A + grading


def _detailed_results(report: dict) -> str:
    blocks = ""
    for case in report["cases"]:
        a = case["answer"]
        g = case["graders"]
        cites = "".join(
            f'<li><a href="{_esc(c["url"])}">{_esc(c["title"])}</a></li>' for c in a["citations"]
        )
        cites_block = f'<ul class="cites">{cites}</ul>' if cites else ""
        grades = "".join(
            f'<li><b>{_esc(d)}</b> [{_esc(_verdict(g[d], d))}]: {_esc(g[d]["rationale"])}</li>'
            for d in DIMENSIONS
        )
        blocks += (
            '<div style="padding:12px 0;border-top:0.5px solid var(--color-border-tertiary)">'
            f'<div style="font-family:var(--font-mono);font-size:11px">{_esc(case["id"])} '
            f'<span style="color:var(--color-text-tertiary)">· {_esc(case["category"])}</span></div>'
            f'<div style="font-size:13px;margin:6px 0"><span style="color:var(--color-text-tertiary)">Q:</span> {_esc(case["question"])}</div>'
            f'<div style="font-size:13px;margin:6px 0;white-space:pre-wrap"><span style="color:var(--color-text-tertiary)">A:</span> {_esc(a["text"])}</div>'
            f"{cites_block}"
            f'<div class="cb-grades"><b>Grading</b><ul>{grades}</ul></div></div>'
        )
    return (
        '<div class="er-card"><details><summary style="font-size:13px;font-weight:500;'
        'color:var(--color-text-secondary)">Detailed results — answer + grading, all '
        f'{report["meta"]["n_cases"]} cases</summary><div style="margin-top:4px">{blocks}</div></details></div>'
    )


_CSS = """
:root{
  --color-background-primary:#ffffff;--color-background-secondary:#f5f4ef;--color-background-tertiary:#efede6;
  --color-text-primary:#1a1a18;--color-text-secondary:#5f5e5a;--color-text-tertiary:#8a8980;
  --color-text-success:#0f6e56;--color-text-danger:#a32d2d;--color-text-warning:#854f0b;
  --color-background-success:#e1f5ee;--color-background-danger:#fcebeb;--color-background-warning:#faeeda;
  --color-border-tertiary:rgba(0,0,0,.12);--color-border-secondary:rgba(0,0,0,.24);
  --font-sans:system-ui,-apple-system,"Segoe UI",sans-serif;--font-mono:ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --color-background-primary:#211f1d;--color-background-secondary:#2a2825;--color-background-tertiary:#1a1917;
  --color-text-primary:#ededea;--color-text-secondary:#b4b2a9;--color-text-tertiary:#888780;
  --color-text-success:#5dcaa5;--color-text-danger:#f09595;--color-text-warning:#ef9f27;
  --color-background-success:#0a4034;--color-background-danger:#4a1414;--color-background-warning:#523005;
  --color-border-tertiary:rgba(255,255,255,.14);--color-border-secondary:rgba(255,255,255,.26);
}}
body{font-family:var(--font-sans);color:var(--color-text-primary);background:var(--color-background-tertiary);max-width:920px;margin:0 auto;padding:1.5rem;line-height:1.5}
.er-card{background:var(--color-background-primary);border:0.5px solid var(--color-border-tertiary);border-radius:12px;padding:1rem 1.25rem;margin:1rem 0}
.er-sec{font-size:13px;font-weight:500;color:var(--color-text-secondary);margin:0 0 12px}
.er-row{display:flex;align-items:center;gap:10px;margin:9px 0}
.er-lab{width:130px;flex:none;font-size:12px;color:var(--color-text-secondary)}
.er-track{flex:1;height:18px;border-radius:5px;overflow:hidden;display:flex;background:var(--color-background-secondary)}
.er-cnt{width:150px;flex:none;font-size:11px;color:var(--color-text-tertiary);text-align:right}
.er-pill{font-size:11px;padding:2px 7px;border-radius:5px;display:inline-block;white-space:nowrap}
.er-tbl{width:100%;border-collapse:collapse;table-layout:fixed;font-size:11.5px}
.er-tbl td,.er-tbl th{padding:5px 6px;border-bottom:0.5px solid var(--color-border-tertiary);text-align:center}
.er-tbl th{font-weight:500;color:var(--color-text-tertiary);font-size:10.5px;vertical-align:bottom;line-height:1.25}
.spotlight{border-color:var(--color-border-secondary)}
.spot-h{font-weight:500;color:var(--color-text-danger);font-size:12px;margin:.6rem 0 .2rem}
.spotlight ul{margin:.2rem 0 .4rem 1.1rem;font-size:12px;color:var(--color-text-secondary)}
.cb-grades{margin-top:.5rem;font-size:12px;color:var(--color-text-secondary)}.cb-grades ul{margin:.2rem 0 0 1.1rem}
.cites{margin:.2rem 0 .2rem 1.1rem;font-size:12px;color:var(--color-text-secondary)}
summary{cursor:pointer}
"""


def write_html(path: str, report: dict) -> None:
    m = report["meta"]
    meta_line = (
        f"agent: {_esc(m['agent_model'])} · judge: {_esc(m['judge_model'])} · "
        f"{m['n_cases']} cases · {_esc(m['timestamp'])}"
    )
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Wiki-search eval report</title>"
        f"<style>{_CSS}</style></head><body>"
        '<div style="display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:6px;padding:1rem 0 0">'
        '<span style="font-size:18px;font-weight:500">Wikipedia-Grounded Q&amp;A · Eval report</span>'
        f'<span style="font-size:12px;color:var(--color-text-tertiary)">{meta_line}</span></div>'
        + _summary_cards(report)
        + _legend()
        + _grader_bars(report)
        + _case_table(report)
        + _spotlight(report)
        + _detailed_results(report)
        + "</body></html>"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
