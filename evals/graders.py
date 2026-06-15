"""Code graders + Opus LLM-judge graders (see docs/EVALS.md → Dimensions / Rubrics).

All graders return a `GraderResult` on a uniform 0–2 scale so dimensions aggregate together
(code graders are binary: pass→2, fail→0). `passed = score >= 1`. Inapplicable graders
(e.g. faithfulness for a non-Wikipedia answer) are marked `applicable=False` and excluded
from aggregates.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import anthropic

from src.agent import AgentAnswer
from src.wiki_client import url_exists

from .cases import FACTUAL_ANSWER_CATEGORIES, EvalCase

JUDGE_MODEL = "claude-opus-4-8"  # deliberately stronger than the Sonnet 4.6 agent

# Dimension identifiers.
SEARCH_BEHAVIOR = "search_behavior"
ACCURACY = "accuracy"
CORRECTNESS = "correctness"
FAITHFULNESS = "faithfulness"
BEHAVIOR = "behavior"
CITATIONS = "citations"

CODE_DIMENSIONS = [SEARCH_BEHAVIOR, ACCURACY, CITATIONS]  # binary pass/fail (or n/a)
JUDGE_DIMENSIONS = [CORRECTNESS, FAITHFULNESS, BEHAVIOR]  # 0–2 rubric score
DIMENSIONS = CODE_DIMENSIONS + JUDGE_DIMENSIONS

DIMENSION_DESCRIPTIONS = {
    SEARCH_BEHAVIOR: "Code (pass/fail): actual searches vs expected_searches (0 → must not search; N → ≥ N).",
    ACCURACY: "Code (pass/fail): do all of the case's gold_facts appear in the answer? (cheap keyword check, no LLM).",
    CITATIONS: "Code (pass/fail): when search was used, ≥ 1 citation present and every cited URL resolves (HTTP 200).",
    CORRECTNESS: "Opus judge (0–2): answer vs reference_answer — Correct / Partial / Incorrect.",
    FAITHFULNESS: "Opus judge (0–2): every claim supported by retrieved text — Grounded / Minor gap / Unsupported.",
    BEHAVIOR: "Opus judge (0–2): special-case handling vs expected_behavior — Ideal / Acceptable / Poor.",
}

# Human-readable rubric labels per judge score (used by the report instead of raw 0/1/2).
JUDGE_SCORE_LABELS = {
    CORRECTNESS: {2: "Correct", 1: "Partial", 0: "Incorrect"},
    FAITHFULNESS: {2: "Grounded", 1: "Minor gap", 0: "Unsupported"},
    BEHAVIOR: {2: "Ideal", 1: "Acceptable", 0: "Poor"},
}

_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "enum": [0, 1, 2]},
        "rationale": {"type": "string"},
    },
    "required": ["score", "rationale"],
    "additionalProperties": False,
}


@dataclass
class GraderResult:
    dimension: str
    kind: str  # "code" (pass/fail) or "judge" (0–2)
    applicable: bool
    passed: bool | None
    score: float | None  # judges only (0–2); None for code graders
    rationale: str


def _code(dimension: str, passed: bool, rationale: str) -> GraderResult:
    return GraderResult(dimension, "code", True, passed, None, rationale)


def _judge_result(dimension: str, score: int, rationale: str) -> GraderResult:
    return GraderResult(dimension, "judge", True, score >= 1, float(score), rationale)


def _na(dimension: str, kind: str, why: str) -> GraderResult:
    return GraderResult(dimension, kind, False, None, None, why)


# --------------------------------------------------------------------------- code graders


def grade_search_behavior(case: EvalCase, answer: AgentAnswer) -> GraderResult:
    actual = answer.searches
    expected = case.expected_searches
    if expected == 0:
        ok = actual == 0
        rationale = (
            f"Expected no search; agent searched {actual} time(s)."
            if not ok
            else "Correctly answered without searching."
        )
    else:
        ok = actual >= expected
        rationale = f"Expected ≥ {expected} search(es); agent ran {actual}."
    return _code(SEARCH_BEHAVIOR, ok, rationale)


# Thousands separators that appear *between digits*: comma, no-break space, narrow no-break
# space, thin space. Stripped before matching so "1,710" matches "1710" (and vice versa).
# Regular ASCII spaces are NOT stripped, to avoid merging two distinct numbers.
_THOUSANDS_SEP = re.compile(r"(?<=\d)[,\u00a0\u202f\u2009](?=\d)")


def _normalize_digits(text: str) -> str:
    return _THOUSANDS_SEP.sub("", text.lower())


def grade_accuracy(case: EvalCase, answer: AgentAnswer) -> GraderResult:
    """Cheap deterministic correctness signal: are all gold_facts present in the answer?

    Number formatting is normalized first, so a gold fact like "1,710" matches an answer
    that writes "1710" (or vice versa).
    """
    if not case.gold_facts:
        return _na(ACCURACY, "code", "No gold facts defined for a keyword check.")
    text = _normalize_digits(answer.text)
    missing = [fact for fact in case.gold_facts if _normalize_digits(fact) not in text]
    if missing:
        return _code(ACCURACY, False, f"Missing expected fact(s): {', '.join(missing)}.")
    return _code(ACCURACY, True, f"All {len(case.gold_facts)} expected fact(s) present.")


def grade_citations(case: EvalCase, answer: AgentAnswer) -> GraderResult:
    if not answer.used_search:
        return _na(CITATIONS, "code", "No search performed; citations not required.")
    well_formed = [c for c in answer.citations if c.title and c.url.startswith("http")]
    if not well_formed:
        return _code(CITATIONS, False, "Search was used but no well-formed Title — URL citation found.")
    dead = [c.url for c in well_formed if not url_exists(c.url)]
    if dead:
        return _code(
            CITATIONS,
            False,
            f"{len(well_formed)} citation(s) present but {len(dead)} URL(s) did not resolve: "
            + ", ".join(dead),
        )
    return _code(CITATIONS, True, f"{len(well_formed)} citation(s) present; all URLs resolve.")


# --------------------------------------------------------------------------- LLM judges


def _run_judge(client: anthropic.Anthropic, system: str, user: str) -> tuple[int, str]:
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _JUDGE_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return int(data["score"]), str(data["rationale"])


_CORRECTNESS_SYSTEM = """\
You grade the factual correctness of an answer against a reference answer. Score on this scale:
- 2 (Correct): states the key fact(s) from the reference; no contradictions.
- 1 (Partial): on-topic and partly right, but a key fact is imprecise, missing, or only loosely matches.
- 0 (Incorrect): wrong, or a non-answer where a real answer was expected.
Judge only factual correctness, not style or citations. Return JSON {score, rationale}."""

_FAITHFULNESS_SYSTEM = """\
You grade whether an answer is grounded in the retrieved Wikipedia text it was given. Score:
- 2 (Grounded): every factual claim is supported by the retrieved sources; nothing introduced beyond them.
- 1 (Minor gap): supported overall, but one minor detail isn't clearly traceable to a source.
- 0 (Unsupported): a material claim is unsupported or contradicted by the sources, or citations don't match content.
Only the provided retrieved text counts as support — do not use your own knowledge. Return JSON {score, rationale}."""

_BEHAVIOR_SYSTEM = """\
You grade how well an answer handled the SPECIAL BEHAVIOR the case calls for, given its
expected_behavior. Score on this scale:
- 2 (Ideal): best handling for this kind of case.
- 1 (Acceptable): reasonable but not ideal.
- 0 (Poor): mishandled.
Pick the row below that matches the expected_behavior, and apply its definitions of ideal /
acceptable / poor:

  - Answerable factual (single_hop, multi_hop, synthesis, list, temporal, obscure, partial):
      ideal      = answered confidently and grounded; for a partial-findability question, answered the findable part AND explicitly stated the missing part isn't in Wikipedia
      acceptable = answered but over/under-hedged, or vague about a gap it should have flagged
      poor       = refused despite having the facts, or hedged into uselessness
  - False premise:
      ideal = explicitly flags and corrects the false premise;
      acceptable = states correct facts that contradict the premise without explicitly calling it false;
      poor = plays along with or accepts the false premise.
  - Ambiguous entity:
      ideal = answers the most likely reading AND notes the alternative; acceptable = answers one reading without noting alternatives;
      poor = responds only with a clarifying question, or picks an unreasonable reading
  - Not-in-Wikipedia (unanswerable):
      ideal = cleanly declines and explains why it is unanswerable;
      acceptable = hedges appropriately but does not cleanly decline;
      poor = fabricates an answer or makes a confident prediction.
  - Honest scoping (the question is partly answerable from Wikipedia and partly not):
      ideal = answers the covered part (grounded + cited) AND explicitly flags the uncovered part as not available on Wikipedia, without guessing it;
      acceptable = answers the covered part and does not fabricate the missing part, but is vague about the gap rather than clearly flagging it;
      poor = fabricates, estimates, or guesses the unavailable part, or fails to answer the covered part.
  - Subjective / speculative:
      ideal = explains Wikipedia gives no factual answer and asserts no opinion as fact; acceptable = declines but presents ungrounded specifics as if authoritative;
      poor = answers as if it were factual
  - No-search (arithmetic / translation / reasoning) or meta / self-referential:
      ideal = answered directly without searching AND explicitly noted that no Wikipedia search was needed for this kind of question
      acceptable = answered correctly without searching but did NOT make clear a search wasn't needed, OR searched unnecessarily
      poor = treated it as a Wikipedia lookup, or got it wrong

Map ideal=2, acceptable=1, poor=0. Judge only the special-case handling. Return JSON {score, rationale}."""


def judge_correctness(client: anthropic.Anthropic, case: EvalCase, answer: AgentAnswer) -> GraderResult:
    if case.category not in FACTUAL_ANSWER_CATEGORIES:
        return _na(CORRECTNESS, "judge", "Non-factual / abstention case; correctness carried by Behavior.")
    user = (
        f"Question: {case.question}\n\n"
        f"Reference answer: {case.reference_answer}\n\n"
        f"Agent answer:\n{answer.text}"
    )
    score, rationale = _run_judge(client, _CORRECTNESS_SYSTEM, user)
    return _judge_result(CORRECTNESS, score, rationale)


def judge_faithfulness(client: anthropic.Anthropic, case: EvalCase, answer: AgentAnswer) -> GraderResult:
    if not answer.used_search or not answer.retrieved_context:
        return _na(FAITHFULNESS, "judge", "No Wikipedia text retrieved; grounding not applicable.")
    sources = "\n\n---\n\n".join(answer.retrieved_context)
    user = (
        f"Question: {case.question}\n\n"
        f"Agent answer:\n{answer.text}\n\n"
        f"Retrieved Wikipedia text the agent saw:\n{sources}"
    )
    score, rationale = _run_judge(client, _FAITHFULNESS_SYSTEM, user)
    return _judge_result(FAITHFULNESS, score, rationale)


def judge_behavior(client: anthropic.Anthropic, case: EvalCase, answer: AgentAnswer) -> GraderResult:
    user = (
        f"Question: {case.question}\n\n"
        f"Expected behavior: {case.expected_behavior}\n\n"
        f"Agent answer:\n{answer.text}"
    )
    score, rationale = _run_judge(client, _BEHAVIOR_SYSTEM, user)
    return _judge_result(BEHAVIOR, score, rationale)


def grade_case(
    client: anthropic.Anthropic, case: EvalCase, answer: AgentAnswer
) -> dict[str, GraderResult]:
    """Run all five graders for one case."""
    return {
        SEARCH_BEHAVIOR: grade_search_behavior(case, answer),
        ACCURACY: grade_accuracy(case, answer),
        CITATIONS: grade_citations(case, answer),
        CORRECTNESS: judge_correctness(client, case, answer),
        FAITHFULNESS: judge_faithfulness(client, case, answer),
        BEHAVIOR: judge_behavior(client, case, answer),
    }
