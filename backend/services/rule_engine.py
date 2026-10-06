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
    """Structural validation so malformed questionnaire data fails loudly, never silently."""
    if not isinstance(q, dict) or not isinstance(q.get("questions"), list) or not q["questions"]:
        raise AppError(500, "questionnaire_malformed",
                       "Questionnaire must contain a non-empty 'questions' list.")
    seen = set()
    for i, item in enumerate(q["questions"]):
        qid = item.get("id")
        if not qid or qid in seen:
            raise AppError(500, "questionnaire_malformed", f"Question #{i + 1} has a missing or duplicate id.")
        seen.add(qid)
        opts = item.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            raise AppError(500, "questionnaire_malformed", f"Question '{qid}' needs at least 2 options.")
        doshas = set()
        for o in opts:
            if not o.get("text") or o.get("dosha") not in DOSHAS:
                raise AppError(500, "questionnaire_malformed",
                               f"Question '{qid}' has an option missing text or a valid dosha.")
            doshas.add(o["dosha"])
        if len(doshas) != len(opts):
            raise AppError(500, "questionnaire_malformed",
                           f"Question '{qid}' has multiple options mapped to the same dosha.")
    return q