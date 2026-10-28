"""Test suite for the 62-item Patwardhan Prakriti instrument + preserved end-to-end flows.
Run from backend/:  python -m pytest -v
All expected values are hand-calculated from the source questionnaire's documented scores.
"""
from fastapi.testclient import TestClient
from main import app
from services.prakriti_engine import get_questionnaire, section_max_scores

client = TestClient(app)


def _state(**over):
    base = dict(heart_rate=72, sleep_hours=7.5, sleep_quality=8, stress=3,
                energy=7, activity="moderate", mood="calm", symptoms=[])
    base.update(over)
    return base


def _qs():
    return client.get("/api/questionnaire").json()["questions"]


def _all(answer):
    return {q["id"]: answer for q in _qs()}


def _all_opposite():
    """Answer AGAINST every item's scoring direction -> raw score must be exactly 0."""
    return {q["id"]: ("no" if q["scoring_answer"] == "yes" else "yes") for q in _qs()}


def _maximize(section, base="no"):
    """Answer every item of `section` with its scoring direction; everything else with `base`."""
    a = {q["id"]: base for q in _qs()}
    for q in _qs():
        if q["section"] == section:
            a[q["id"]] = q["scoring_answer"]
    return a


# ---------- 1. Health & questionnaire structure ----------
def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

def test_exactly_62_unique_valid_items():
    data = client.get("/api/questionnaire").json()
    qs = data["questions"]
    assert len(qs) == 62
    ids = [q["id"] for q in qs]
    assert len(set(ids)) == 62
    counts = {}
    for q in qs:
        assert q["text"] and q["scoring_answer"] in ("yes", "no")
        assert isinstance(q["score"], (int, float)) and q["score"] > 0
        counts[q["section"]] = counts.get(q["section"], 0) + 1
    assert counts == {"kapha": 23, "pitta": 16, "vata": 23}   # matches the source sections
    assert data["provenance"]["status"] == "SOURCE-VERIFIED"

def test_section_max_scores_match_source():
    ms = section_max_scores(get_questionnaire())
    assert ms["kapha"] == 1440.0
    assert ms["vata"] == 960.0
    assert ms["pitta"] == 599.0   # source PRINTS 600 but its items sum to 599 — documented discrepancy

# ---------- 2. Scoring math (hand-computed expectations) ----------
def test_all_yes_raw_scores():
    # All 'yes': Vata items all score (960). Pitta: all except reverse P-5 -> 599-120=479.
    # Kapha: all except the 6 reverse items (60+40+120+30+30+120=400) -> 1440-400=1040.
    r = client.post("/api/prakriti/calculate", json={"answers": _all("yes")}).json()
    assert r["raw_scores"] == {"vata": 960.0, "pitta": 479.0, "kapha": 1040.0}
    # Source formula: 960/960=100.0 ; 479/599=79.97->80.0 ; 1040/1440=72.2
    assert r["source_percentages"] == {"vata": 100.0, "pitta": 80.0, "kapha": 72.2}
    # Normalized: total 2479 -> 38.7/19.3/41.9 -> largest remainder -> 39/19/42
    assert r["percentages"] == {"vata": 39.0, "pitta": 19.0, "kapha": 42.0}
    assert r["dominant"] == "kapha"

def test_all_no_hand_case():
    # All 'no': the 7 reverse items score -> kapha 400, pitta 120, vata 0. Total 520.
    # Normalized: 76.9/23.1/0 -> floors 76+23+0=99 -> remainder 1 -> kapha frac .923 largest -> 77.
    r = client.post("/api/prakriti/calculate", json={"answers": _all("no")}).json()
    assert r["raw_scores"] == {"vata": 0.0, "pitta": 120.0, "kapha": 400.0}
    assert r["percentages"] == {"vata": 0.0, "pitta": 23.0, "kapha": 77.0}
    assert r["source_percentages"] == {"vata": 0.0, "pitta": 20.0, "kapha": 27.8}  # 400/1440=27.78

def test_reverse_item_scores_on_no():
    # Baseline: opposite of every scoring direction -> raw 0 -> API must reject with no_scores.
    r = client.post("/api/prakriti/calculate", json={"answers": _all_opposite()})
    assert r.status_code == 400 and r.json()["error"]["code"] == "no_scores"
    # Flip ONLY K-5B to its scoring answer ('no'): exactly 60 raw kapha points.
    a = _all_opposite(); a["K-5B"] = "no"
    r = client.post("/api/prakriti/calculate", json={"answers": a}).json()
    assert r["raw_scores"]["kapha"] == 60.0
    assert r["raw_scores"]["pitta"] == 0.0 and r["raw_scores"]["vata"] == 0.0

def test_mixed_kapha_pitta_hand_case():
    # Maximize kapha (1440) + pitta (599), vata all 'no' (vata has no reverse items -> 0).
    # Total 2039 -> 70.6/29.4/0 -> floors 70+29+0=99 -> remainder 1 -> kapha frac .62 largest -> 71.
    answers = _all("no")
    for q in _qs():
        if q["section"] in ("kapha", "pitta"):
            answers[q["id"]] = q["scoring_answer"]

    r = client.post("/api/prakriti/calculate", json={"answers": answers}).json()
    assert r["percentages"] == {"vata": 0.0, "pitta": 29.0, "kapha": 71.0}
    assert r["source_percentages"] == {"vata": 0.0, "pitta": 100.0, "kapha": 100.0}
    assert r["dominant"] == "kapha" and r["secondary"] == "pitta"
    assert r["dosha_type"] == "Kapha dominant"

# ---------- 3. Error handling ----------
def test_missing_answers_rejected():
    answers = _all("no"); answers.pop("K-1")
    r = client.post("/api/prakriti/calculate", json={"answers": answers})
    body = r.json()
    assert r.status_code == 400 and body["error"]["code"] == "missing_answers"
    assert len(body["error"]["details"]["missing"]) == 1

def test_invalid_answer_rejected():
    a = _all("yes"); a["K-2"] = "maybe"
    r = client.post("/api/prakriti/calculate", json={"answers": a})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_answer"

def test_unknown_question_rejected():
    a = _all("yes"); a["BOGUS-ID"] = "yes"
    r = client.post("/api/prakriti/calculate", json={"answers": a})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unknown_question"

# ---------- 4. Preserved downstream flows (two-persona e2e) ----------
def test_two_personas_get_different_plans():
    env_vata = {"mode": "manual", "temperature": 36, "humidity": 18, "weather": "clear", "season": "Summer"}
    env_kapha = {"mode": "manual", "temperature": 12, "humidity": 80, "weather": "rain", "season": "Winter"}

    # Vata user: maximize vata. Base 'no' elsewhere scores the reverse items:
    # kapha 400 + pitta 120 -> raw {960,120,400}, total 1480 -> 64.9/8.1/27.0 -> 65/8/27.
    uv = client.post("/api/assessment", json={
        "answers": _maximize("vata"), "current_state": _state(stress=9, sleep_hours=5,
        sleep_quality=2, mood="anxious"), "environment": env_vata}).json()
    # Kapha user: maximize kapha -> raw {0,120,1440}, total 1560 -> 0/7.7/92.3 -> 0/8/92.
    uk = client.post("/api/assessment", json={
        "answers": _maximize("kapha"), "current_state": _state(energy=2, activity="low",
        mood="sluggish", sleep_hours=10), "environment": env_kapha}).json()

    assert uv["prakriti"]["dominant"] == "vata"
    assert uv["prakriti"]["percentages"] == {"vata": 65.0, "pitta": 8.0, "kapha": 27.0}
    assert uk["prakriti"]["dominant"] == "kapha"
    assert uk["prakriti"]["percentages"] == {"vata": 0.0, "pitta": 8.0, "kapha": 92.0}
    assert uv["recommendations"]["focus_dosha"] == "vata"
    assert uk["recommendations"]["focus_dosha"] == "kapha"
    # Contract preservation: old fields still present, new fields additive
    for key in ("prakriti", "vikriti", "environment", "recommendations", "explanations",
                "generated_at", "disclaimer"):
        assert key in uv
    for key in ("percentages", "dominant", "secondary", "dosha_type", "category_scores",
                "answered_count", "total_questions", "source_percentages", "raw_scores", "max_scores"):
        assert key in uv["prakriti"]
    assert uv["recommendations"]["exercise"]["type"] != uk["recommendations"]["exercise"]["type"]
    assert len(uv["recommendations"]["timeline"]) >= 12
    assert "not a medical diagnostic tool" in uv["disclaimer"]

# ---------- 5. Untouched subsystems (regression) ----------
def test_stress_and_poor_sleep_elevate_vata():
    payload = {"prakriti_percentages": {"vata": 60, "pitta": 30, "kapha": 10},
               "current_state": _state(stress=9, sleep_quality=2, sleep_hours=5, mood="anxious")}
    v = client.post("/api/vikriti/calculate", json=payload).json()
    assert v["tendencies"]["vata"]["tendency"] == "elevated"

def test_invalid_vitals_rejected():
    for bad in [0, 250]:
        r = client.post("/api/vikriti/calculate",
                        json={"prakriti_percentages": {"vata": 34, "pitta": 33, "kapha": 33},
                              "current_state": _state(heart_rate=bad)})
        assert r.status_code == 422

def test_environment_manual_hot_dry_fires_vata_rule():
    r = client.post("/api/environment",
                    json={"mode": "manual", "temperature": 34, "humidity": 20,
                          "weather": "clear", "season": "Summer"})
    assert r.status_code == 200 and "hot_dry" in r.json()["influences_fired"]

def test_assessment_missing_manual_env_rejected():
    r = client.post("/api/assessment", json={
        "answers": _maximize("vata"), "current_state": _state(),
        "environment": {"mode": "manual"}})
    assert r.status_code == 422