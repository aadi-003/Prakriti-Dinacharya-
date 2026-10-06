Personalized Prakriti–Vikriti & Dinacharya Recommendation System
Educational wellness prototype inspired by Ayurvedic concepts. This is NOT a medicaldiagnostic tool. It does not diagnose disease, does not clinically determine doshas, anddoes not replace professional medical advice. All outputs are general wellness suggestionsgenerated from a transparent, editable rule set.

1. Project Overview
This application estimates a user's baseline constitution (Prakriti) from a self-assessmentquestionnaire, estimates their current-day imbalance tendencies (Vikriti) from manuallyentered physiological/wellness inputs, factors in seasonal/environmental conditions, andgenerates a personalized daily routine (Dinacharya) including diet, exercise, sleep,Pathya (do's), Apathya (don'ts), and traditional Indian classical raga suggestions.

Every recommendation is traceable: the UI includes a "Why these recommendations?" section andevery timeline block shows its reason. No black-box model is used.

2. Problem Statement
Classical Ayurvedic daily-routine guidance (Dinacharya, Ritucharya) is generic — the sameadvice for everyone. This project demonstrates how that guidance can be personalizedtransparently by combining three inputs: long-term constitution (Prakriti), short-termstate (Vikriti), and environment (season/weather) — using an explainable rule engine insteadof an opaque ML model.

3. Features
20-question, 4-section Prakriti questionnaire with dosha-mapped scoring
Dynamic Vata/Pitta/Kapha percentage calculation (always sums to exactly 100%) with donut chart
Rule-based Vikriti estimation with ↑/→/↓ tendencies vs baseline
Environment input three ways: manual (always works), city name, or browser GPS + liveweather (Open-Meteo, no API key) — with graceful fallback if any of these fail
Full Dinacharya timeline (wake-up → sleep) with per-block reasoning
Diet (breakfast/lunch/dinner), exercise (auto-adjusted for energy/weather/heart rate),hydration target, sleep routine, Pathya, Apathya, calming practices, raga suggestions
Complete input validation with human-readable error messages
Automated test suite (10 tests) including a two-persona end-to-end test proving plansdiffer between users
4. Architecture
Questionnaire JSON ──► Prakriti Engine ──► Prakriti Profile (V/P/K %)                                                │Current-state inputs ──► Vikriti Engine ──► Tendencies (↑/→/↓)                                                │Environment (GPS/city/manual) ──► Environment Engine                                                │                                Recommendation Engine (rules/*.json)                                                │                                Personalized Dinacharya + Explanations
The scoring logic is fully separated from the UI. All domain content (questions, thresholds,diet text, ragas, timeline blocks) lives in editable JSON files under backend/rules/ —changes take effect on the next request, no restart needed.

5. Tech Stack
Layer	Technology
Backend	Python 3.10+, FastAPI, Pydantic v2
Frontend	React 18 + Vite 5 (plain CSS)
Data	JSON rule files; optional anonymized SQLite log
Weather	Open-Meteo API (keyless)
Tests	pytest + FastAPI TestClient
No authentication, no accounts, no personal data collection.

6. Folder Structure
prakriti-dinacharya/├── README.md├── requirements.txt├── .env.example├── data/                          # used only if SAVE_ASSESSMENTS=true├── backend/│   ├── main.py                    # FastAPI app + all endpoints│   ├── pytest.ini│   ├── models/│   │   └── schemas.py             # Pydantic validation (all input rules)│   ├── services/│   │   ├── constants.py           # disclaimer text│   │   ├── errors.py              # AppError exception│   │   ├── rule_engine.py         # JSON loading, condition evaluation, % math│   │   ├── prakriti_engine.py     # questionnaire scoring│   │   ├── vikriti_engine.py      # current-state estimation│   │   ├── environment_engine.py  # season resolution + weather fetching│   │   ├── recommendation_engine.py│   │   └── storage.py             # optional anonymized SQLite summary log│   ├── rules/                     # ← ALL editable domain configuration│   │   ├── questionnaire.json│   │   ├── vikriti_rules.json│   │   ├── seasonal_rules.json│   │   ├── diet_rules.json│   │   ├── exercise_rules.json│   │   ├── sleep_rules.json│   │   ├── music_rules.json│   │   └── routine_rules.json│   └── tests/│       └── test_e2e_flow.py       # 10 tests incl. two-persona end-to-end└── frontend/    ├── index.html    ├── package.json    ├── vite.config.js             # proxies /api → localhost:8000    └── src/        ├── main.jsx        ├── api.js                 # backend client        ├── styles.css        └── App.jsx                # all 7 UI screens
7. How Prakriti Scoring Works
Each questionnaire option is mapped to one dosha with a score (default 1). The user'sselected options are summed per dosha, then converted to percentages:

percentage(dosha) = round(dosha_points / total_points × 100)
Integer rounding uses the largest-remainder method, so the three percentages always sumto exactly 100 (avoids 33/33/33 = 99). If the top two doshas differ by less than 15percentage points, the type is labeled a dual type (e.g., "Vata–Pitta (dual)").

Worked example — 20 answers: Vata chosen 12×, Pitta 6×, Kapha 2× → 60% / 30% / 10%,"Vata dominant", secondary Pitta. Nothing is hardcoded; results come only from the answers.

Scoring policy: unanswered questions are rejected by the API (HTTP 400missing_answers); option indices outside the valid range are rejected (HTTP 400invalid_option).

8. How Vikriti Estimation Works
A transparent, documented rule system (all rules visible in rules/vikriti_rules.json,each with a plain-English explanation string):

Current-state inputs (heart rate, sleep hours/quality, stress, energy, activity, mood,symptoms) are matched against rule conditions (operators: min, max, equals,in, contains).
Each fired rule adds points to a dosha — max 10 points per dosha.
raw[dosha] = baseline_percentage + points × 6 (the 6 is point_scale, configurable).
Raw values are normalized to 100%.
A dosha is labeled elevated if its Vikriti share exceeds baseline by ≥ 5 points,reduced if lower by ≥ 5, otherwise stable.
Worked example — baseline 60/30/10, poor sleep + high stress + anxious mood firesshort_sleep (+2 Vata), poor_sleep_high_stress (+3 Vata), high_stress (+2 Vata),mood_anxious (+2 Vata) = 9 points → raw Vata 114 → normalized 74% Vata / 19% / 7% →"Vata ↑". The engine returns the fired rule IDs and their explanations so the user sees WHY.

9. How Environment Affects Recommendations
Season: auto-derived from the current month using a simplified Indian calendar(Dec–Feb Winter, Mar–May Summer, Jun–Sep Monsoon, Oct–Nov Autumn). The user can overrideit manually (Spring is available only via manual override).
Weather: three modes — manual (temperature + humidity + condition typed by user),city (geocoded via Open-Meteo, weather fetched), auto (browser GPS → weather fetched).If fetching fails, status becomes unavailable, the app still works, and the UI shows anote asking for manual entry. Precise coordinates are never stored — only a city-level label.
Influence rules (in rules/seasonal_rules.json): e.g., temp ≥ 32 & humidity ≤ 35fires hot_dry (Vata +2, Pitta +1); temp ≤ 20 & humidity ≥ 70 fires cold_damp(Kapha +2, Vata +1). Fired rules are reported with explanations.
Season also contributes its own Pathya/Apathya lists and diet/lifestyle notes (e.g., Monsoonfavors boiled water and warm light food).

10. Recommendation Engine
Hybrid rule-based engine (recommendation_engine.py + 7 JSON rule files). Key logic:

Focus dosha = the dosha whose Vikriti share rose the most vs baseline (if ≥ +3 points),otherwise the dominant Prakriti. All per-dosha content (diet/exercise/sleep/music/routine)is selected by this focus.
Exercise base duration per dosha (Vata 25 / Pitta 35 / Kapha 45 min), then adjusted:shortened ~30% if energy ≤ 3; indoor alternatives if raining; heat and high-heart-ratewarnings added; every adjustment is recorded as text + rule id.
Sleep: per-dosha bedtime; shifted 20 min earlier if sleep < 6 h or quality ≤ 4; extrawind-down steps appended for poor sleep or stress ≥ 7.
Pathya/Apathya: union of focus-dosha and seasonal lists; Apathya wins on conflicts;stress/poor-sleep add their own entries (e.g., caffeine cutoff after 2 PM).
Hydration target starts at 2.0 L, +0.5 if temp ≥ 32, +0.25 if high activity.
Ragas: per-dosha evening/night suggestions + season-specific ragas (e.g., Miyan kiMalhar in Monsoon). Presented as traditional listening suggestions, not therapy.
11. Installation
Prerequisites: Python 3.10+, Node.js 18+.

# 1. Backend setupcd backendpython -m venv venvsource venv/bin/activate          # Windows: venv\Scripts\activatepip install -r ../requirements.txt# 2. Frontend setup (new terminal)cd frontendnpm install
12. Environment Variables
Copy .env.example to .env if you want to change defaults. In development you don'tneed any of them — defaults work.

Variable	Default	Meaning
SAVE_ASSESSMENTS	false	If true, saves ANONYMIZED summaries (dosha %s, season, weather — never names, IDs, or coordinates) to SQLite
DATA_DIR	./data	Where the SQLite file is written
VITE_API_URL	(empty)	Frontend: leave empty in dev (Vite proxy handles it)
13. How to Run Backend
cd backendsource venv/bin/activate          # Windows: venv\Scripts\activateuvicorn main:app --reload --port 8000
Health check: http://localhost:8000/api/health
Interactive API docs: http://localhost:8000/docs
14. How to Run Frontend
cd frontendnpm run dev
Open http://localhost:5173. Start the backend FIRST.

15. How to Run Tests
cd backendsource venv/bin/activatepython -m pytest -v               # use "python -m", not bare "pytest"
Expected: 10 passed — covers questionnaire structure, dynamic percentage math, missing/invalid answer rejection, Vikriti elevation logic, edge cases (HR 0 & 250, sleep 0 & 24,stress −1 & 11), environmental rules, and a two-persona end-to-end flow.

16. Sample Test Users
User 1 — Vata	User 2 — Pitta	User 3 — Kapha
Questionnaire	1st option on all 20	2nd option on all 20	3rd option on all 20
Heart rate	72	95	72
Sleep	5 h, quality 2	7.5 h, quality 8	10 h, quality 8
Stress / Energy	9 / 7	6 / 7	4 / 2
Activity / Mood	moderate / anxious	high / irritable	low / sluggish
Environment	Summer, 36 °C, 18%, clear	Monsoon, 31 °C, 75%, rain	Winter, 12 °C, 80%, rain
Expected Prakriti	Vata 100%	Pitta 100%	Kapha 100%
Expected focus	vata (elevated by poor sleep + stress)	pitta	kapha
Expected plan	gentle short exercise, warm grounding food, earlier bedtime	cooling food, no midday sun	vigorous exercise, light spiced food, no naps
Users 1 and 3 are automated in the tests; User 2 can be clicked through in the UI.

17. Limitations
Questionnaire provenance: the questionnaire was reconstructed from the standardclassical Prakriti attribute set; it is NOT a verified transcription of the referencequestionnaire image. The provenance flag in rules/questionnaire.json marks this, andthe UI displays it. Replace the file's content with the verified questionnaire — theformat supports drop-in updates.
Rules encode classical Ayurvedic-inspired wellness heuristics, not clinically validatedthresholds. Physiological inputs (e.g., heart rate) are user-reported proxies.
This prototype uses a transparent rule-based recommendation engine rather than claimingmedically validated machine-learning predictions.
Single-day snapshot: nothing tracks the user over time. Manual inputs are subject touser error. Weather needs internet; GPS needs browser permission.
18. Disclaimer
This application is an educational wellness prototype inspired by Ayurvedic concepts(Prakriti, Vikriti, Dinacharya, Ritucharya). It is not a medical diagnostic tool, it doesnot diagnose disease, and it does not replace professional medical advice, diagnosis, ortreatment. Physiological and environmental inputs are used only to generate general,personalized wellness suggestions from a transparent rule set. If you have health concerns,consult a qualified professional.

19. Future Improvements
Admin UI for editing rule files without touching JSON
Multi-day tracking with optional (consented) anonymized data for explainable clustering
PDF/export of the generated Dinacharya
Region-calibrated season maps; i18n (Hindi/regional languages)
Verified questionnaire transcription as the primary data source