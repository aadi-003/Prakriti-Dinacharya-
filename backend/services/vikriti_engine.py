"""Vikriti estimation engine — transparent, rule-based, fully documented in vikriti_rules.json."""
from .constants import DOSHA_NAMES
from .rule_engine import DOSHAS, apply_rules, largest_remainder, load_rules

RULES_FILE = "vikriti_rules.json"

MOODS = ("calm", "anxious", "restless", "irritable", "low", "sluggish", "focused")
ACTIVITIES = ("low", "moderate", "high")
SYMPTOMS = ("bloating", "gas", "constipation", "dry_skin", "restlessness",
            "acidity", "heartburn", "headache", "loose_stools",
            "congestion", "sluggishness", "body_ache")


def _summary(prakriti_pct: dict, tendencies: dict, fired: list) -> str:
    base = " / ".join(f"{DOSHA_NAMES[d]} {prakriti_pct[d]:.0f}%" for d in DOSHAS)
    if not fired:
        return (f"Your current inputs are broadly consistent with your baseline ({base}); "
                "no dosha tendency is strongly elevated right now.")
    top = max(DOSHAS, key=lambda d: (tendencies[d]["delta"], -DOSHAS.index(d)))
    drivers = [r["explanation"] for r in fired][:3]
    return (f"Compared with your baseline ({base}), your current inputs contributed most to an elevated "
            f"{DOSHA_NAMES[top]} tendency. " + " ".join(drivers))


def estimate_vikriti(prakriti_pct: dict, state: dict) -> dict:
    """
    Blend baseline Prakriti with rule-driven current-state signals.

    Method (documented):
      1. Every fired rule adds points to a dosha (capped per dosha).
      2. raw[d] = baseline_pct[d] + points[d] * point_scale
      3. raw is normalized to 100 (largest remainder).
      4. tendency arrows compare the normalized Vikriti share against the baseline share.
    """
    rules = load_rules(RULES_FILE)
    ctx = dict(state)
    points, fired = apply_rules(rules["rules"], ctx, cap=rules.get("max_points_per_dosha", 10))
    scale = float(rules.get("point_scale", 6.0))

    raw = {d: float(prakriti_pct[d]) + points[d] * scale for d in DOSHAS}
    percentages = largest_remainder(raw)

    th = rules.get("tendency_thresholds", {"up": 5.0, "down": 5.0})
    tendencies = {}
    for d in DOSHAS:
        delta = round(percentages[d] - prakriti_pct[d], 1)
        tendency = "stable"
        if delta >= th["up"]:
            tendency = "elevated"
        elif delta <= th["down"]:
            tendency = "reduced"
        tendencies[d] = {"percentage": percentages[d], "delta": delta,
                         "tendency": tendency, "rule_points": points[d]}

    return {
        "percentages": percentages,
        "tendencies": tendencies,
        "rule_points": points,
        "fired_rules": [r["id"] for r in fired],
        "explanations": [r["explanation"] for r in fired],
        "summary": _summary(prakriti_pct, tendencies, fired),
    }