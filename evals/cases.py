"""Curated, category-balanced eval cases (see EVALS.md → Case Set).

Each case declares an *expected behavior*, not just a gold string:
- `expected_searches`: 0 means the agent must NOT search; N ≥ 1 means at least N searches.
- `reference_answer`: what a correct answer should convey (input to the Correctness judge).
- `expected_behavior`: the special-case policy (input to the Behavior judge).
- `gold_facts`: optional crisp substrings for a cheap deterministic correctness pre-check.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Category identifiers (module-level constants; imported by graders/runner).
SINGLE_HOP = "single_hop_factual"
MULTI_HOP = "multi_hop_factual"
DEEP_SECTION = "deep_section_factual"
AMBIGUOUS = "ambiguous_entity"
FALSE_PREMISE = "false_premise"
NON_FACTUAL = "non_factual"
UNANSWERABLE = "unanswerable"
INSUFFICIENT = "found_but_insufficient"

# Categories for which the Correctness judge applies (a real answer is expected).
FACTUAL_ANSWER_CATEGORIES = {
    SINGLE_HOP,
    MULTI_HOP,
    DEEP_SECTION,
    AMBIGUOUS,
    FALSE_PREMISE,
    INSUFFICIENT,
}

CATEGORY_DESCRIPTIONS = {
    SINGLE_HOP: "Direct factual question answerable from one article's summary.",
    MULTI_HOP: "Requires chaining several searches to combine facts.",
    DEEP_SECTION: "Detail lives in a body section, so the agent must fetch_section after searching.",
    AMBIGUOUS: "Entity with several common senses; answer one fully and mention the others.",
    FALSE_PREMISE: "Question embeds a wrong assumption; correct it, grounded.",
    NON_FACTUAL: "Arithmetic / translation / reasoning; answer directly, label as not-from-Wikipedia.",
    UNANSWERABLE: "Private or unknowable; abstain honestly without fabricating.",
    INSUFFICIENT: "Wikipedia covers the topic but lacks the precise fact; answer the part it has and flag the gap.",
}


@dataclass
class EvalCase:
    id: str
    question: str
    category: str
    expected_searches: int
    reference_answer: str
    expected_behavior: str
    gold_facts: list[str] = field(default_factory=list)
    notes: str = ""


CASES: list[EvalCase] = [
    EvalCase(
        id="everest_height",
        question="How tall is Mount Everest?",
        category=SINGLE_HOP,
        expected_searches=1,
        reference_answer="About 8,848.86 metres (29,031 ft) above sea level, per the 2020 survey.",
        expected_behavior="Answer directly with the height and cite the Mount Everest article.",
        gold_facts=["8,848"],
    ),
    EvalCase(
        id="speed_of_light",
        question="What is the speed of light in a vacuum?",
        category=SINGLE_HOP,
        expected_searches=1,
        reference_answer="Exactly 299,792,458 metres per second.",
        expected_behavior="Answer with the value and cite a relevant Wikipedia article.",
        gold_facts=["299,792,458"],
    ),
    EvalCase(
        id="mona_lisa_painter",
        question="Who painted the Mona Lisa?",
        category=SINGLE_HOP,
        expected_searches=1,
        reference_answer="Leonardo da Vinci.",
        expected_behavior="Name the painter and cite the article.",
        gold_facts=["Leonardo"],
    ),
    EvalCase(
        id="bladerunner_author_birth",
        question="The film Blade Runner is based on a novel — who wrote it, and in what year was that author born?",
        category=MULTI_HOP,
        expected_searches=2,
        reference_answer=(
            "Blade Runner is based on Philip K. Dick's novel 'Do Androids Dream of Electric "
            "Sheep?'; Dick was born in 1928."
        ),
        expected_behavior="Chain searches (film → source novel/author → birth year) and cite sources.",
        gold_facts=["Philip K. Dick", "1928"],
    ),
    EvalCase(
        id="wc2018_capital_population",
        question="What is the population of the capital of the country that won the 2018 FIFA World Cup?",
        category=MULTI_HOP,
        expected_searches=2,
        reference_answer=(
            "France won the 2018 World Cup; its capital is Paris, whose city-proper population "
            "is roughly 2.1 million."
        ),
        expected_behavior="Chain searches (winner → capital → population) and cite sources.",
        gold_facts=["Paris"],
    ),
    EvalCase(
        id="eiffel_tower_steps",
        question="How many steps lead to the top of the Eiffel Tower?",
        category=DEEP_SECTION,
        expected_searches=1,
        reference_answer=(
            "About 600 steps reach the second floor; historically a 1,710-step climb led to the "
            "top (the top is normally reached by lift)."
        ),
        expected_behavior=(
            "Search, then fetch the relevant section; report the step counts Wikipedia gives "
            "(~600 to the second floor, ~1,710 to the top historically) and cite."
        ),
        gold_facts=["1,710"],
        notes="Corrected from an earlier wrong gold fact (1,665 is not in the article).",
    ),
    EvalCase(
        id="mercury_ambiguous",
        question="Tell me about Mercury.",
        category=AMBIGUOUS,
        expected_searches=1,
        reference_answer=(
            "'Mercury' commonly refers to the planet (closest to the Sun), the chemical element "
            "Hg, or the Roman god."
        ),
        expected_behavior=(
            "Answer the most likely sense (e.g. the planet) fully and cite it, then briefly note "
            "the other senses (element, Roman god)."
        ),
    ),
    EvalCase(
        id="einstein_two_nobels",
        question="When did Einstein win his two Nobel Prizes?",
        category=FALSE_PREMISE,
        expected_searches=1,
        reference_answer=(
            "Einstein won only one Nobel Prize — Physics, 1921, for the photoelectric effect — "
            "not two."
        ),
        expected_behavior="Correct the false premise (he won one, not two), grounded; cite the source.",
        gold_facts=["1921"],
    ),
    EvalCase(
        id="arithmetic_product",
        question="What is 12,345 multiplied by 67?",
        category=NON_FACTUAL,
        expected_searches=0,
        reference_answer="827,115.",
        expected_behavior="Answer directly without searching and note the answer is not from Wikipedia.",
        gold_facts=["827,115"],
    ),
    EvalCase(
        id="translate_good_morning",
        question="Translate 'good morning' into French.",
        category=NON_FACTUAL,
        expected_searches=0,
        reference_answer="Bonjour (or 'bon matin' in some regions).",
        expected_behavior="Answer directly without searching and note it is not from Wikipedia.",
        gold_facts=["Bonjour"],
    ),
    EvalCase(
        id="syllogism_reasoning",
        question=(
            "If all roses are flowers and some flowers fade quickly, can we conclude that all "
            "roses fade quickly?"
        ),
        category=NON_FACTUAL,
        expected_searches=0,
        reference_answer="No — that conclusion does not follow logically.",
        expected_behavior="Answer the reasoning directly without searching; note it is not from Wikipedia.",
    ),
    EvalCase(
        id="neighbor_breakfast",
        question="What did my next-door neighbor eat for breakfast yesterday?",
        category=UNANSWERABLE,
        expected_searches=0,
        reference_answer="",
        expected_behavior=(
            "Recognize this is private/unknowable and not the kind of thing Wikipedia covers; "
            "decline honestly without fabricating."
        ),
    ),
    EvalCase(
        id="einstein_last_words",
        question="What were Albert Einstein's last words?",
        category=INSUFFICIENT,
        expected_searches=1,
        reference_answer=(
            "His exact last words are not known — he spoke in German to a nurse who did not "
            "understand it, so they went unrecorded."
        ),
        expected_behavior=(
            "Report what Wikipedia says (his final words are unknown/unrecorded) — answer the "
            "known part and explicitly flag that the exact words are not available."
        ),
    ),
]
