"""Generic, reusable rule primitives: JSON loading, condition evaluation, percentage math."""
import json
import math
from pathlib import Path

from .errors import AppError

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
DOSHAS = ("vata", "pitta", "kapha")


def load_rules(filename: str) -> dict:
    """Load a JSON rules file. Read at request time so rule edits take effect without a restart."""
    path = RULES_DIR / filename
    if not path.exists():
        raise AppError(500, "rules_missing", f"Rules file '{filename}' not found on server.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise AppError(500, "rules_malformed", f"Rules file '{filename}' is not valid JSON.", {"error": str(e)})


def condition_matches(conditions: dict, ctx: dict) -> bool:
    """
    Evaluate a rule's conditions against a feature context.
    Supported operators: min, max, equals, in (value in list), contains (list contains value).
    A condition on a missing/None field evaluates to False (rule simply does not fire).
    """
    for field, ops in conditions.items():
        if field not in ctx:
            return False
        value = ctx[field]
        if not isinstance(ops, dict):
            raise AppError(500, "rules_malformed", f"Conditions for field '{field}' must be an object.")
        for op, target in ops.items():
            if value is None:
                return False
            if op == "min":
                if value < target:
                    return False
            elif op == "max":
                if value > target:
                    return False
            elif op == "equals":
                if value != target:
                    return False
            elif op == "in":
                if value not in target:
                    return False
            elif op == "contains":
                if not isinstance(value, (list, tuple)) or target not in value:
                    return False
            else:
                raise AppError(500, "rules_malformed", f"Unknown condition operator '{op}'.")
    return True


def apply_rules(rules: list, ctx: dict, cap: int = 10):
    """Fire all matching rules; accumulate dosha points with a per-dosha cap. Returns (points, fired_rules)."""
    points = {d: 0 for d in DOSHAS}
    fired = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise AppError(500, "rules_malformed", "Every rule must be an object.")
        try:
            if condition_matches(rule.get("conditions", {}), ctx):
                for d, pts in (rule.get("effect") or {}).items():
                    if d in points and isinstance(pts, (int, float)):
                        points[d] = int(min(cap, points[d] + pts))
                fired.append(rule)
        except AppError:
            raise
        except Exception as e:
            raise AppError(500, "rules_malformed",
                           f"Malformed rule '{rule.get('id', '?')}'.", {"error": str(e)})
    return points, fired


def largest_remainder(scores: dict) -> dict:
    """
    Convert raw scores into integer percentages that always sum to exactly 100,
    using the largest-remainder method (avoids 33/33/33 = 99 problems).
    """
    total = sum(scores.values())
    if total <= 0:
        raise AppError(400, "zero_scores", "Total score is zero; cannot compute percentages.")
    exact = {k: v * 100.0 / total for k, v in scores.items()}
    floors = {k: int(math.floor(v)) for k, v in exact.items()}
    remainder = 100 - sum(floors.values())
    order = sorted(exact, key=lambda k: (exact[k] - floors[k], k), reverse=True)
    for i in range(remainder):
        floors[order[i % len(order)]] += 1
    return {k: float(floors[k]) for k in floors}


def validate_questionnaire(q: dict) -> dict:
    """Structural validation for the binary-checklist questionnaire format."""
    if not isinstance(q, dict) or not isinstance(q.get("questions"), list) or not q["questions"]:
        raise AppError(500, "questionnaire_malformed",
                       "Questionnaire must contain a non-empty 'questions' list.")
    if q.get("format") != "binary_checklist":
        raise AppError(500, "questionnaire_malformed",
                       "Questionnaire 'format' must be 'binary_checklist'.")
    seen = set()
    for i, item in enumerate(q["questions"]):
        qid = item.get("id")
        if not qid or qid in seen:
            raise AppError(500, "questionnaire_malformed", f"Question #{i + 1} has a missing or duplicate id.")
        seen.add(qid)
        if item.get("section") not in DOSHAS:
            raise AppError(500, "questionnaire_malformed", f"Question '{qid}' has an invalid section.")
        if not item.get("text"):
            raise AppError(500, "questionnaire_malformed", f"Question '{qid}' has no text.")
        if item.get("scoring_answer") not in ("yes", "no"):
            raise AppError(500, "questionnaire_malformed", f"Question '{qid}' needs scoring_answer 'yes' or 'no'.")
        score = item.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or score <= 0:
            raise AppError(500, "questionnaire_malformed", f"Question '{qid}' needs a positive numeric score.")
    for sec in q.get("sections", []):
        for qid in sec.get("question_ids", []):
            if qid not in seen:
                raise AppError(500, "questionnaire_malformed",
                               f"Section '{sec.get('id')}' references unknown question '{qid}'.")
    return q