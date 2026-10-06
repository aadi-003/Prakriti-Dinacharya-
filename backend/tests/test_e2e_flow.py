"""Compact but real test suite: API health, validation, engines, and two-persona end-to-end flow.
Run from the backend/ directory with:  python -m pytest -v
"""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _all_answers(option_index: int) -> dict:
    """Pick the same option index for every question (0=vata, 1=pitta, 2=kapha)."""
    questions = client.get("/api/questionnaire").json()["questions"]
    return {item["id"]: option_index for item in questions}


def _state(**over):
    base = dict(heart_rate=72, sleep_hours=7.5, sleep_quality=8, stress=3,
                energy=7, activity="moderate", mood="calm", symptoms=[])
    base.update(over)
    return base


# ---------- 1. Health & questionnaire ----------
def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

def test_questionnaire_structure():
    data = client.get("/api/questionnaire").json()
    assert len(data["questions"]) == 20
    for q in data["questions"]:
        assert len(q["options"]) == 3
        assert {o["dosha"] for o in q["options"]} == {"vata", "pitta", "kapha"}
    assert "provenance" in data  # transparency flag must reach the client

# ---------- 2. Prakriti scoring ----------
def test_prakriti_all_vata_answers():
    result = client.post("/api/prakriti/calculate", json={"answers": _all_answers(0)}).json()
    assert result["percentages"]["vata"] == 100.0
    assert result["dominant"] == "vata"
    assert sum(result["percentages"].values()) == 100

def test_prakriti_missing_answers_rejected():
    r = client.post("/api/prakriti/calculate", json={"answers": {"body_frame": 0}})
    assert r.status_code == 400 and r.json()["error"]["code"] == "missing_answers"

def test_prakriti_invalid_option_rejected():
    r = client.post("/api/prakriti/calculate", json={"answers": {"body_frame": 9}})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_option"

# ---------- 3. Vikriti ----------
def test_stress_and_poor_sleep_elevate_vata():
    payload = {"prakriti_percentages": {"vata": 60, "pitta": 30, "kapha": 10},
               "current_state": _state(stress=9, sleep_quality=2, sleep_hours=5, mood="anxious")}
    v = client.post("/api/vikriti/calculate", json=payload).json()
    assert v["tendencies"]["vata"]["tendency"] == "elevated"
    assert "poor_sleep_high_stress" in v["fired_rules"]
    assert len(v["explanations"]) >= 1   # system explains WHY

# ---------- 4. Input validation (edge cases) ----------
def test_invalid_vitals_rejected():
    for bad in [0, 250]:                      # HR edge cases
        r = client.post("/api/vikriti/calculate",
                        json={"prakriti_percentages": {"vata": 34, "pitta": 33, "kapha": 33},
                              "current_state": _state(heart_rate=bad)})
        assert r.status_code == 422
    for field, val in [("stress", 11), ("stress", -1), ("sleep_hours", 0), ("sleep_hours", 24)]:
        r = client.post("/api/vikriti/calculate",
                        json={"prakriti_percentages": {"vata": 34, "pitta": 33, "kapha": 33},
                              "current_state": _state(**{field: val})})
        assert r.status_code == 422, f"{field}={val} should be rejected"

# ---------- 5. Environment ----------
def test_environment_manual_hot_dry_fires_vata_rule():
    r = client.post("/api/environment",
                    json={"mode": "manual", "temperature": 34, "humidity": 20,
                          "weather": "clear", "season": "Summer"})
    body = r.json()
    assert r.status_code == 200 and "hot_dry" in body["influences_fired"]
    assert body["explanations"]

# ---------- 6. End-to-end: two very different personas ----------
def test_two_personas_get_different_plans():
    env_vata = {"mode": "manual", "temperature": 36, "humidity": 18, "weather": "clear", "season": "Summer"}
    env_kapha = {"mode": "manual", "temperature": 12, "humidity": 80, "weather": "rain", "season": "Winter"}

    user_vata = client.post("/api/assessment", json={
        "answers": _all_answers(0), "current_state": _state(stress=9, sleep_hours=5,
        sleep_quality=2, mood="anxious"), "environment": env_vata}).json()
    user_kapha = client.post("/api/assessment", json={
        "answers": _all_answers(2), "current_state": _state(energy=2, activity="low",
        mood="sluggish", sleep_hours=10), "environment": env_kapha}).json()

    assert user_vata["recommendations"]["focus_dosha"] == "vata"
    assert user_kapha["recommendations"]["focus_dosha"] == "kapha"
    # The plans must genuinely differ, not be hardcoded:
    assert user_vata["recommendations"]["exercise"]["type"] != user_kapha["recommendations"]["exercise"]["type"]
    assert user_vata["recommendations"]["diet"]["favor_tastes"] != user_kapha["recommendations"]["diet"]["favor_tastes"]
    # Structure sanity:
    assert len(user_vata["recommendations"]["timeline"]) >= 12
    assert user_vata["recommendations"]["pathya"] and user_vata["recommendations"]["apathya"]
    assert "disclaimer" in user_vata and "not a medical diagnostic tool" in user_vata["disclaimer"]

def test_assessment_missing_manual_env_rejected():
    r = client.post("/api/assessment", json={
        "answers": _all_answers(0), "current_state": _state(),
        "environment": {"mode": "manual"}})   # manual mode but no temperature/humidity
    assert r.status_code == 422