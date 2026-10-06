"""Hybrid rule-based Dinacharya recommendation engine. All content lives in rules/*.json."""
from .constants import DOSHA_NAMES, DISCLAIMER
from .rule_engine import DOSHAS, load_rules

RAIN_WEATHER = ("rain", "drizzle", "thunderstorm")
FOCUS_DELTA_THRESHOLD = 3.0   # documented: Vikriti share must rise >= 3 points over baseline to become the focus
MAX_LIST = 8


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        key = str(it).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(str(it))
    return out


def _fmt_time(minutes: int) -> str:
    minutes = int(minutes) % 1440
    h, m = divmod(minutes, 60)
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def _parse_hhmm(s: str) -> int:
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _fmt(template: str, ctx: dict) -> str:
    try:
        return str(template).format_map(_SafeDict(ctx))
    except Exception:
        return str(template)


def _pick(detail, dosha: str) -> str:
    if isinstance(detail, dict):
        return detail.get(dosha) or detail.get("default") or ""
    return detail


def generate_recommendations(prakriti: dict, vikriti: dict, environment: dict,
                             state: dict, prefs: dict = None) -> dict:
    prefs = prefs or {}
    routine_r = load_rules("routine_rules.json")
    diet_r = load_rules("diet_rules.json")
    ex_r = load_rules("exercise_rules.json")
    sleep_r = load_rules("sleep_rules.json")
    music_r = load_rules("music_rules.json")
    seasonal_r = load_rules("seasonal_rules.json")

    prak_pct, vik_pct = prakriti["percentages"], vikriti["percentages"]
    deltas = {d: vik_pct[d] - prak_pct[d] for d in DOSHAS}

    # ---- Focus dosha: biggest baseline-relative rise, else dominant Prakriti ----
    focus = max(DOSHAS, key=lambda d: (deltas[d], -DOSHAS.index(d)))
    if deltas[focus] < FOCUS_DELTA_THRESHOLD:
        focus = prakriti["dominant"]
    focus_label = DOSHA_NAMES[focus]

    season = environment.get("season", "Summer")
    seasonal = seasonal_r["seasons"].get(season, seasonal_r["seasons"]["default"])

    # ---------------- Exercise ----------------
    ex = ex_r[focus]
    duration = ex["duration_minutes"]
    adjustments = []
    if state["energy"] <= 3:
        duration = max(10, round(duration * 0.7))
        adjustments.append({"text": "Energy is low today, so the session was shortened and kept gentle.",
                            "rule": "energy_low"})
    if state["activity"] == "high":
        adjustments.append({"text": "You were already highly active today — keep the main session light.",
                            "rule": "activity_high"})
    temp = environment.get("temperature")
    weather = environment.get("weather")
    if isinstance(temp, (int, float)) and temp >= 32:
        adjustments.append({"text": "It is hot outside — exercise early or indoors, and hydrate well.",
                            "rule": "hot_weather"})
    if weather in RAIN_WEATHER:
        adjustments.append({"text": "Rainy conditions — choose indoor alternatives today.",
                            "rule": "rainy_weather"})
    if state["heart_rate"] >= 90:
        adjustments.append({"text": "The heart rate you entered is on the higher side — keep intensity "
                                    "comfortable (conversation pace).", "rule": "high_hr"})
    exercise = {"type": ex["type"], "duration_minutes": duration, "intensity": ex["intensity"],
                "examples": ex["examples"], "note": ex["note"], "adjustments": adjustments,
                "reason": f"{focus_label} responds best to {ex['type'].lower()} — adjusted for today's "
                          f"energy, activity, weather and heart-rate input."}

    # ---------------- Sleep ----------------
    sl = sleep_r[focus]
    bedtime_min = _parse_hhmm(sl["bedtime"])
    routine = list(sl["routine"])
    sleep_adj = []
    if state["sleep_hours"] < 6 or state["sleep_quality"] <= 4:
        bedtime_min -= 20
        sleep_adj.append("You reported short or poor sleep — bedtime is set slightly earlier tonight, "
                         "with an extended wind-down.")
        routine += sl.get("poor_sleep_routine", [])
    if state["stress"] >= 7:
        routine += sl.get("high_stress_routine", [])
        sleep_adj.append("High stress noted — a slow-breathing step was added to your bedtime routine.")
    bedtime_str = _fmt_time(bedtime_min)

    # ---------------- Music / Raga ----------------
    mu = music_r["by_dosha"][focus]
    season_music = music_r["by_season"].get(season)
    music = {"goal": mu["goal"],
             "ragas": _dedupe(list(mu["evening"]) + list(mu["night"])),
             "season_ragas": season_music["ragas"] if season_music else [],
             "season_note": season_music["note"] if season_music else None,
             "instruments": mu["instruments"], "note": mu["note"],
             "work_focus": music_r["work_focus"]["suggestion"],
             "when": "During the evening relaxation block and for 15–20 minutes before bed."}

    # ---------------- Diet ----------------
    dt = diet_r[focus]
    diet = {"favor_tastes": dt["favor_tastes"],
            "breakfast": dt["breakfast"], "lunch": dt["lunch"], "dinner": dt["dinner"],
            "guidance": _dedupe(list(dt["guidance"]) + [seasonal["diet_note"]])}
    if prefs.get("diet") in ("vegan", "vegetarian"):
        diet["guidance"].append(f"{prefs['diet'].capitalize()} preference noted — swap dairy suggestions "
                                "for plant-based alternatives you tolerate well.")

    # ---------------- Pathya / Apathya (conflict-free: apathya wins) ----------------
    apathya = _dedupe(list(dt["avoid"]) + list(seasonal["apathya"]))
    if state["stress"] >= 7:
        apathya.append("Excess caffeine (coffee / energy drinks), especially after 2 PM")
    if state["sleep_hours"] < 6 or state["sleep_quality"] <= 4:
        apathya.append("Screens in the last hour before bed")
    pathya_raw = (list(dt["favor"]) + list(seasonal["pathya"]) +
                  [f"Regular meal and sleep times (key for {focus_label} balance)"])
    apathya_set = {a.lower() for a in apathya}
    pathya = [p for p in _dedupe(pathya_raw) if p.lower() not in apathya_set]
    pathya, apathya = pathya[:MAX_LIST + 2], apathya[:MAX_LIST + 2]

    # ---------------- Hydration ----------------
    target = 2.0
    tips = []
    if isinstance(temp, (int, float)) and temp >= 32:
        target += 0.5
        tips.append("Hot weather — increase your fluid intake.")
    if state["activity"] == "high":
        target += 0.25
        tips.append("High-activity day — sip extra water.")
    if weather in RAIN_WEATHER:
        tips.append("Rainy weather — prefer boiled and cooled water.")
    if focus == "vata":
        tips.append("Prefer warm water; sip throughout the day.")
    elif focus == "pitta":
        tips.append("Room-temperature to cool water; coconut water and fennel infusion are good choices.")
    else:
        tips.append("Warm water with ginger, or a spoon of honey in warm (not hot) water.")
    hydration = {"target_litres": round(target, 2), "tips": tips,
                 "reason": "Hydration target adapts to temperature and your activity level."}

    # ---------------- Calming practices & lifestyle ----------------
    calming = list(routine_r["calming_practices"][focus])
    if state["stress"] >= 7:
        calming.append("4-7-8 breathing: inhale 4s, hold 7s, exhale 8s — repeat 4 rounds, twice today.")
    lifestyle = list(routine_r["lifestyle"][focus]) + [seasonal["lifestyle_note"]]
    if state["stress"] >= 7:
        lifestyle.append("Schedule two 10-minute quiet-breathing breaks into your workday.")

    # ---------------- Timeline ----------------
    wake_min = _parse_hhmm(routine_r["wake_times"].get(focus, routine_r["wake_times"]["default"]))
    ctx = {"wake_time": _fmt_time(wake_min), "bedtime": bedtime_str,
           "focus_label": focus_label, "season": season,
           "exercise_summary": f"{exercise['type']} — about {exercise['duration_minutes']} minutes "
                               f"({exercise['intensity']}). Try: {', '.join(exercise['examples'][:2])}.",
           "music_summary": "Suggested for this evening: " +
                            ", ".join((music["ragas"] + music["season_ragas"])[:2]),
           "sleep_prep_summary": " · ".join(routine[:4])}

    timeline = []
    for b in routine_r["blocks"]:
        if b.get("use_bedtime"):
            t, sort_key = bedtime_str, bedtime_min + 1
        elif "bedtime_offset" in b:
            t, sort_key = _fmt_time(bedtime_min - b["bedtime_offset"]), bedtime_min - b["bedtime_offset"]
        else:
            t = _fmt_time(wake_min + b["offset"])
            sort_key = wake_min + b["offset"]
        timeline.append({"time": t, "sort_key": sort_key, "title": b["title"],
                         "detail": _fmt(_pick(b["detail"], focus), ctx),
                         "reason": _fmt(b["reason"], ctx), "tag": b.get("tag", "routine")})
    timeline.sort(key=lambda x: x["sort_key"])
    for b in timeline:
        b.pop("sort_key")

    # ---------------- Explanations (WHY) ----------------
    explanations = [
        f"Baseline Prakriti: Vata {prak_pct['vata']:.0f}% · Pitta {prak_pct['pitta']:.0f}% · "
        f"Kapha {prak_pct['kapha']:.0f}% ({prakriti.get('dosha_type', '')}).",
        vikriti["summary"],
    ]
    explanations += [f"Environment: {e}" for e in environment.get("explanations", [])]
    if deltas[focus] >= FOCUS_DELTA_THRESHOLD:
        explanations.append(f"Today's plan focuses on balancing {focus_label} — the dosha whose share rose "
                            f"the most compared with your baseline (+{deltas[focus]:.1f} points).")
    else:
        explanations.append(f"No dosha is strongly elevated today, so the plan follows your dominant "
                            f"Prakriti ({focus_label}).")
    explanations += [a["text"] for a in adjustments] + sleep_adj
    explanations.append("Every suggestion comes from a transparent, documented rule set inspired by "
                        "classical Dinacharya and Ritucharya guidance — the rule files can be inspected "
                        "and edited directly.")

    profile = {
        "prakriti_percentages": prak_pct, "prakriti_type": prakriti.get("dosha_type"),
        "dominant": prakriti["dominant"], "vikriti_percentages": vik_pct,
        "tendencies": {d: vikriti["tendencies"][d]["tendency"] for d in DOSHAS},
        "focus_dosha": focus,
        "environment": {k: environment.get(k) for k in
                        ("season", "temperature", "humidity", "weather", "location_label", "status")},
    }

    return {"profile": profile, "focus_dosha": focus, "timeline": timeline, "diet": diet,
            "exercise": exercise, "hydration": hydration, "pathya": pathya, "apathya": apathya,
            "sleep": {"bedtime": bedtime_str, "routine": routine, "adjustments": sleep_adj},
            "music": music, "calming_practices": calming, "lifestyle": lifestyle,
            "explanations": explanations, "disclaimer": DISCLAIMER}