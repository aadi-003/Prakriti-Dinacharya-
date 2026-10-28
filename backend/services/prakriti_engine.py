"""Prakriti scoring engine — 62-item binary (Yes/No) instrument by Patwardhan et al. (BHU).

Source-faithful method (all documented in rules/questionnaire.json provenance):
  raw[d]        = sum of scores of items in section d whose answer matches scoring_answer
  max[d]        = sum of ALL item scores in section d (computed from the data, not hardcoded)
  source_pct[d] = 100 * raw[d] / max[d]        <- the instrument's documented formula
  percentages   = largest-remainder normalization of raw to sum 100   <- DERIVED, app-level only
                  (used by the donut chart and the Vikriti/recommendation engines; NOT part
                  of the instrument. Kept under the existing 'percentages' field so the
                  API contract and downstream engines stay unchanged.)
Known source discrepancy: PDF prints Pitta total = 600, items sum to 599. Denominator = 599.
"""
from .constants import DOSHA_NAMES
from .errors import AppError
from .rule_engine import DOSHAS, load_rules, largest_remainder, validate_questionnaire

QUESTIONNAIRE_FILE = "questionnaire.json"
DUAL_THRESHOLD_PCT = 15.0  # app-level convention (source defines no classification rule)

_YES = {"yes", "y", "true", "1"}
_NO = {"no", "n", "false", "0"}


def get_questionnaire() -> dict:
    return validate_questionnaire(load_rules(QUESTIONNAIRE_FILE))


def _normalize_answer(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _YES:
            return "yes"
        if v in _NO:
            return "no"
    return None


def _ranked(pct: dict):
    return sorted(DOSHAS, key=lambda d: (-pct[d], d))


def _type_label(pct: dict) -> str:
    ranked = _ranked(pct)
    first, second = ranked[0], ranked[1]
    if pct[first] - pct[second] < DUAL_THRESHOLD_PCT:
        return f"{DOSHA_NAMES[first]}–{DOSHA_NAMES[second]} (dual)"
    return f"{DOSHA_NAMES[first]} dominant"


def section_max_scores(questionnaire: dict) -> dict:
    """Denominator per dosha: the sum of its items' scores, computed from the data."""
    max_scores = {d: 0.0 for d in DOSHAS}
    for item in questionnaire["questions"]:
        max_scores[item["section"]] += float(item["score"])
    return max_scores


def calculate_prakriti(answers: dict, questionnaire: dict = None, require_all: bool = True) -> dict:
    q = questionnaire or get_questionnaire()
    items = q["questions"]
    imap = {item["id"]: item for item in items}

    unknown = sorted(k for k in answers if k not in imap)
    if unknown:
        raise AppError(400, "unknown_question", "Answers contain unknown question ids.", {"unknown": unknown})

    missing = [item["id"] for item in items if item["id"] not in answers]
    if require_all and missing:
        raise AppError(400, "missing_answers", "Some questions were not answered.", {"missing": missing})

    raw = {d: 0.0 for d in DOSHAS}
    answered = 0
    for item in items:
        if item["id"] not in answers:
            continue
        norm = _normalize_answer(answers[item["id"]])
        if norm is None:
            raise AppError(400, "invalid_answer",
                           f"Answer for '{item['id']}' must be 'yes' or 'no'.",
                           {"question": item["id"], "received": answers[item["id"]]})
        answered += 1
        if norm == item["scoring_answer"]:
            raw[item["section"]] += float(item["score"])

    if answered == 0:
        raise AppError(400, "no_answers", "At least one question must be answered.")
    if sum(raw.values()) <= 0:
        raise AppError(400, "no_scores",
                       "None of your answers matched any constitutional trait, so no Prakriti "
                       "distribution can be computed. Please review your answers.")

    max_scores = section_max_scores(q)
    source_percentages = {d: round(100.0 * raw[d] / max_scores[d], 1) for d in DOSHAS}
    percentages = largest_remainder(raw)
    ranked = _ranked(percentages)

    return {
        "percentages": percentages,                 # existing contract: normalized, sums to 100
        "source_percentages": source_percentages,   # NEW: the instrument's own formula output
        "raw_scores": {d: raw[d] for d in DOSHAS},  # NEW: additive
        "max_scores": {d: max_scores[d] for d in DOSHAS},  # NEW: additive
        "dominant": ranked[0],                      # existing contract
        "secondary": ranked[1],
        "dosha_type": _type_label(percentages),
        "category_scores": {d: raw[d] for d in DOSHAS},  # existing field, same meaning (raw points)
        "answered_count": answered,
        "total_questions": len(items),
        "missing": missing,
        "scoring_method": ("Patwardhan et al. 62-item binary checklist. source% = 100 x raw/max "
                           "(max: kapha 1440, pitta 599, vata 960). 'percentages' is a normalized "
                           "display distribution used by downstream engines — see README."),
    }