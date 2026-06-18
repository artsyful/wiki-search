"""Curated, category-balanced eval cases (see docs/EVALS.md → Case Set).

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
TEMPORAL_RECENT = "temporal_recent"
TEMPORAL_PAST = "temporal_past"
LIST = "list_enumeration"
SUBJECTIVE = "subjective"
SPECULATIVE = "speculative"
META = "meta"

# Categories for which the Correctness judge applies (a real answer is expected).
FACTUAL_ANSWER_CATEGORIES = {
    SINGLE_HOP,
    MULTI_HOP,
    DEEP_SECTION,
    AMBIGUOUS,
    FALSE_PREMISE,
    INSUFFICIENT,
    TEMPORAL_PAST,
    TEMPORAL_RECENT,
    LIST,
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
    TEMPORAL_RECENT: "Very recent / post-training-cutoff event; ground in Wikipedia or abstain — never answer from memory.",
    TEMPORAL_PAST: "A fixed historical fact that cannot change; retrieve and cite.",
    LIST: "Exhaustive closed-set enumeration; graded on all-of completeness and no over-inclusion.",
    SUBJECTIVE: "Opinion question with no factual answer; explain that and don't assert a pick as fact.",
    SPECULATIVE: "Future/forecast question Wikipedia can't supply; don't fabricate a prediction.",
    META: "Self-referential ('what can you do?'); answer directly without searching.",
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
        id="berlin_wall_fall_date",
        question="On what date did the Berlin Wall fall?",
        category=TEMPORAL_PAST,
        expected_searches=1,
        reference_answer="The Berlin Wall fell on 9 November 1989.",
        expected_behavior="Answer with the date and cite the article.",
        gold_facts=["1989"],
    ),
    EvalCase(
        id="hormuz_blocked_2026",
        question="When was the Strait of Hormuz blocked in 2026?",
        category=TEMPORAL_RECENT,
        expected_searches=1,
        reference_answer=(
            "Shipping traffic through the Strait of Hormuz has been largely blocked by Iran since "
            "February 28, 2026, when the United States and Israel launched an air war against Iran "
            "and assassinated its Supreme Leader, Ali Khamenei."
        ),
        expected_behavior=(
            "Search Wikipedia. If there is no clear record of such an event, say it isn't found "
            "in Wikipedia rather than inventing a date or answering from prior knowledge; if "
            "Wikipedia does cover it, report what it says with a citation."
        ),
        gold_facts=["28", "February", "2026", "Iran"],
        notes="Post-training-cutoff temporal probe; tests grounding/abstention over hallucination.",
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
        id="bladerunner_author_birthplace_population",
        question=(
            "The film Blade Runner is based on a novel. Who wrote it, in which city was that "
            "author born, and what is that city's population?"
        ),
        category=MULTI_HOP,
        expected_searches=3,
        reference_answer=(
            "Blade Runner is based on Philip K. Dick's novel 'Do Androids Dream of Electric "
            "Sheep?'; Dick was born in Chicago, whose population is roughly 2.7 million."
        ),
        expected_behavior=(
            "Chain three lookups (film → author → birthplace → that city's population) and cite "
            "sources."
        ),
        gold_facts=["Philip K. Dick", "Chicago"],
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
        id="everest_minus_k2_height",
        question="How much taller is Mount Everest than K2, in metres?",
        category=MULTI_HOP,
        expected_searches=2,
        reference_answer=(
            "Everest is about 8,849 m and K2 about 8,611 m, so Everest is roughly 238 m taller."
        ),
        expected_behavior=(
            "Retrieve both mountains' heights and compute the difference, grounded in the two "
            "figures; cite both."
        ),
        gold_facts=["K2"],
        notes="Multi-hop with an arithmetic operation (subtraction) on the retrieved facts.",
    ),
    EvalCase(
        id="baltic_states_total_area",
        question="What is the combined land area of the three Baltic states?",
        category=MULTI_HOP,
        expected_searches=3,
        reference_answer=(
            "Estonia (~45,000 km2), Latvia (~64,500 km2), and Lithuania (~65,300 km2) total "
            "roughly 175,000 km2."
        ),
        expected_behavior=(
            "Retrieve each country's area from its article and sum them, grounded in the "
            "sources; cite each."
        ),
        gold_facts=["Estonia", "Latvia", "Lithuania"],
        notes=(
            "Multi-hop that aggregates (sums) a fixed quantity (area) across several source "
            "articles. Area is used instead of population so the reference does not drift over time."
        ),
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
        gold_facts=["Solar System", "planet"],
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
        gold_facts=["I want to go when I want"],
    ),
    EvalCase(
        id="pushpavanam_village_avg_age",
        question="Tell me more about Pushpavanam village and tell me the average age of people in it.",
        category=INSUFFICIENT,
        expected_searches=1,
        reference_answer=(
            "Pushpavanam is a village in Tamil Nadu, India; Wikipedia describes the village but "
            "does not give the average age of its residents."
        ),
        expected_behavior=(
            "Share what Wikipedia has about the village, and explicitly state that the average "
            "age of residents is not available in Wikipedia — do not fabricate a figure."
        ),
        gold_facts=["village", "Vedaranyam", "Nagapattinam"],
        notes="Part answerable (village description), part not (average age).",
    ),
    EvalCase(
        id="list_switzerland_borders",
        question="Which countries share a land border with Switzerland?",
        category=LIST,
        expected_searches=1,
        reference_answer="Switzerland borders Germany, France, Italy, Austria, and Liechtenstein.",
        expected_behavior=(
            "Enumerate all bordering countries completely and cite; do not omit any (Liechtenstein "
            "is the easy miss) or include non-bordering countries."
        ),
        gold_facts=["Germany", "France", "Italy", "Austria", "Liechtenstein"],
        notes="Closed-set enumeration; tests all-of completeness and resistance to over-including.",
    ),
    EvalCase(
        id="subjective_best_language",
        question="What is the best programming language?",
        category=SUBJECTIVE,
        expected_searches=0,
        reference_answer="",
        expected_behavior=(
            "Explain there is no single factual 'best' (it depends on use case); do not assert an "
            "opinion as fact. Answer without searching and note Wikipedia has no factual answer."
        ),
        notes="Subjective abstention: real-sounding question with no factual answer.",
    ),
    EvalCase(
        id="speculative_london_rain",
        question="Will it rain in London next Tuesday?",
        category=SPECULATIVE,
        expected_searches=0,
        reference_answer="",
        expected_behavior=(
            "Explain this is a future forecast Wikipedia cannot provide; do not fabricate a "
            "prediction. Answer without searching and say it is not something Wikipedia can answer."
        ),
        notes="Future/speculative abstention.",
    ),
    EvalCase(
        id="meta_capabilities",
        question="What can you do?",
        category=META,
        expected_searches=0,
        reference_answer="",
        expected_behavior=(
            "Describe its own capabilities (answering questions grounded in Wikipedia) directly "
            "without searching, and note this is not a Wikipedia lookup."
        ),
        notes="Self-referential / meta: a no-search path distinct from arithmetic/translation.",
    ),
]
