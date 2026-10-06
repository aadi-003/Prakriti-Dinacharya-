"""Prakriti scoring engine — separated completely from the UI."""
from .constants import DOSHA_NAMES
from .errors import AppError
from .rule_engine import DOSHAS, load_rules, largest_remainder, validate_questionnaire

QUESTIONNAIRE_FILE = "questionnaire.json"
DUAL_THRESHOLD_PCT = 15.0  # documented: if top two doshas differ by < 15 points -> dual type


def get_questionnaire() -> dict:
    return validate_questionnaire(load_rules(QUESTIONNAIRE_FILE))


def _ranked(pct: dict):
    return sorted(DOSHAS, key=lambda d: (-pct[d], d))  # deterministic tie-break (alphabetical)


def _type_label(pct: dict) -> str:
    ranked = _ranked(pct)
    first, second = ranked[0], ranked[1]
    if pct[first] - pct[second] < DUAL_THRESHOLD_PCT:
        return f"{DOSHA_NAMES[first]}–{DOSHA_NAMES[second]} (dual)"
    return f"{DOSHA_NAMES[first]} dominant"

def calculate_prakriti(answers: dict, questionnaire: dict = None, require_all: bool = True) -> dict:
    """
    Score questionnaire answers.

    Scoring policy:
      * Each selected option adds its score (default 1) to its mapped dosha.
      * Unanswered questions are excluded from the denominator when
        require_all=False.
      * When require_all=True, missing questions are rejected.
      * Invalid provided option indexes are rejected before missing-answer
        validation so that the client receives the correct error.
      * Percentages use largest-remainder rounding and always sum to 100.
    """
    q = questionnaire or get_questionnaire()
    questions = q["questions"]
    qmap = {item["id"]: item for item in questions}

    # ---------------------------------------------------------
    # 1. Check for unknown question IDs
    # ---------------------------------------------------------
    unknown = sorted(k for k in answers if k not in qmap)
    if unknown:
        raise AppError(
            400,
            "unknown_question",
            "Answers contain unknown question ids.",
            {"unknown": unknown},
        )

    # ---------------------------------------------------------
    # 2. Validate every answer that WAS provided
    #    This must happen before checking missing answers.
    # ---------------------------------------------------------
    for item in questions:
        qid = item["id"]

        if qid not in answers:
            continue

        idx = answers[qid]
        opts = item["options"]

        if (
            isinstance(idx, bool)
            or not isinstance(idx, int)
            or not (0 <= idx < len(opts))
        ):
            raise AppError(
                400,
                "invalid_option",
                f"Answer for '{qid}' is not a valid option index.",
                {
                    "question": qid,
                    "received": idx,
                    "valid_range": [0, len(opts) - 1],
                },
            )

    # ---------------------------------------------------------
    # 3. Check missing answers
    # ---------------------------------------------------------
    missing = [
        item["id"]
        for item in questions
        if item["id"] not in answers
    ]

    if require_all and missing:
        raise AppError(
            400,
            "missing_answers",
            "Some questions were not answered.",
            {"missing": missing},
        )

    # ---------------------------------------------------------
    # 4. Calculate scores
    # ---------------------------------------------------------
    scores = {d: 0.0 for d in DOSHAS}
    answered = 0

    for item in questions:
        qid = item["id"]

        if qid not in answers:
            continue

        idx = answers[qid]
        opt = item["options"][idx]

        scores[opt["dosha"]] += float(opt.get("score", 1))
        answered += 1

    if answered == 0:
        raise AppError(
            400,
            "no_answers",
            "At least one question must be answered.",
        )

    # ---------------------------------------------------------
    # 5. Convert scores to percentages
    # ---------------------------------------------------------
    percentages = largest_remainder(scores)
    ranked = _ranked(percentages)

    return {
        "percentages": percentages,
        "dominant": ranked[0],
        "secondary": ranked[1],
        "dosha_type": _type_label(percentages),
        "category_scores": {
            d: scores[d] for d in DOSHAS
        },
        "answered_count": answered,
        "total_questions": len(questions),
        "missing": missing,
    }