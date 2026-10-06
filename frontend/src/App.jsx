import { useEffect, useState } from "react";
import { api } from "./api";

const SYMPTOMS = ["bloating","gas","constipation","dry_skin","restlessness","acidity",
  "heartburn","headache","loose_stools","congestion","sluggishness","body_ache"];
const MOODS = ["calm","anxious","restless","irritable","low","sluggish","focused"];
const SEASONS = ["Winter","Summer","Monsoon","Autumn","Spring"];
const WEATHERS = ["clear","partly cloudy","cloudy","fog","drizzle","rain","thunderstorm","snow"];
const STEPS = ["Welcome","Disclaimer","Prakriti Quiz","Your Prakriti","Current State","Environment","Your Plan"];
const DOSHA_COLOR = { vata:"#7c9cf5", pitta:"#f5a25c", kapha:"#6fbf9b" };
const ARROW = { elevated:"↑", reduced:"↓", stable:"→" };

/* ---------- small shared components ---------- */
function Stepper({ step }) {
  return (
    <div className="stepper">
      {STEPS.map((s, i) => (
        <span key={s} className={i === step ? "on" : i < step ? "done" : ""}>{i + 1}. {s}</span>
      ))}
    </div>
  );
}
function Banner({ message }) { return message ? <div className="banner">⚠️ {message}</div> : null; }

function Donut({ p }) {
  const C = 2 * Math.PI * 45; let off = 0;
  return (
    <svg viewBox="0 0 120 120" width="180" height="180">
      <circle cx="60" cy="60" r="45" fill="none" stroke="#eef0f5" strokeWidth="16" />
      {Object.entries(p).map(([k, v]) => {
        const len = (C * v) / 100;
        const el = <circle key={k} cx="60" cy="60" r="45" fill="none" stroke={DOSHA_COLOR[k]}
          strokeWidth="16" strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-off}
          transform="rotate(-90 60 60)" />;
        off += len; return el;
      })}
      <text x="60" y="64" textAnchor="middle" fontSize="10" fill="#69758a">Prakriti</text>
    </svg>
  );
}
const List = ({ items }) => <ul className="clean">{items.map((t, i) => <li key={i}>{t}</li>)}</ul>;

/* ---------- main app ---------- */
export default function App() {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [questionnaire, setQuestionnaire] = useState(null);
  const [answers, setAnswers] = useState({});
  const [prakriti, setPrakriti] = useState(null);
  const [state, setState] = useState({ heart_rate: 72, sleep_hours: 7, sleep_quality: 6,
    stress: 4, energy: 6, activity: "moderate", mood: "calm", symptoms: [] });
  const [envMode, setEnvMode] = useState("manual");
  const [city, setCity] = useState("");
  const [env, setEnv] = useState({ temperature: 28, humidity: 60, weather: "clear", season: "" });
  const [plan, setPlan] = useState(null);

  const go = (n) => { setError(null); setStep(n); window.scrollTo(0, 0); };
  const set = (obj, patch) => setState({ ...obj, ...patch });

  useEffect(() => {
    if (step === 2 && !questionnaire && !busy) {
      setBusy(true);
      api.getQuestionnaire().then(setQuestionnaire).catch((e) => setError(e.message)).finally(() => setBusy(false));
    }
  }, [step]);

  async function submitQuiz() {
    setBusy(true); setError(null);
    try { setPrakriti(await api.calculatePrakriti(answers)); go(3); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  function getGeo() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject(new Error("Geolocation is not supported by this browser."));
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
        () => reject(new Error("Location permission denied or unavailable — please use manual or city mode.")),
        { timeout: 8000 });
    });
  }

  async function finish() {
    setBusy(true); setError(null);
    try {
      let environment;
      if (envMode === "manual") {
        environment = { mode: "manual", temperature: Number(env.temperature),
          humidity: Number(env.humidity), weather: env.weather,
          ...(env.season ? { season: env.season } : {}), month: new Date().getMonth() + 1 };
      } else if (envMode === "city") {
        environment = { mode: "city", city };
      } else {
        environment = { mode: "auto", ...(await getGeo()) };   // throws → caught below
      }
      setPlan(await api.fullAssessment({ answers, current_state: state, environment, preferences: {} }));
      go(6);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const startOver = () => { setPlan(null); setPrakriti(null); setAnswers({}); setQuestionnaire(null); go(0); };

  /* ---------- screens ---------- */
  const screens = {
    0: () => (
      <div className="card">
        <h1>Prakriti–Vikriti & Dinacharya</h1>
        <p>A personalized daily-routine wellness planner inspired by Ayurvedic concepts.
           Answer a short constitutional questionnaire, share how you feel today, add your
           environment — and get a transparent, rule-based daily plan with diet, exercise,
           sleep, pathya/apathya and raga suggestions.</p>
        <p className="muted">Takes about 5 minutes. No personal data (name, email, phone) is collected.</p>
        <button className="btn" onClick={() => go(1)}>Get started →</button>
      </div>),
    1: () => (
      <div className="card">
        <h2>Disclaimer — please read</h2>
        <div className="disclaimer-box">
          This application is an <b>educational wellness prototype</b> inspired by Ayurvedic
          concepts (Prakriti, Vikriti, Dinacharya, Ritucharya). It is <b>not a medical
          diagnostic tool</b>, does not diagnose disease, and does not replace professional
          medical advice, diagnosis, or treatment. All suggestions come from a transparent,
          editable rule set and are intended as general wellness guidance. If you have health
          concerns, consult a qualified professional.
        </div>
        <button className="btn" onClick={() => go(2)}>I understand — continue</button>
      </div>),
    2: () => (
      <div>
        {!questionnaire ? <div className="card">{busy ? "Loading questionnaire…" : <Banner message={error} />}</div> : (
          <>
            <div className="card">
              <h2>{questionnaire.title}</h2>
              <p className="muted">{questionnaire.instructions}</p>
              <p className="muted">Answered: {Object.keys(answers).length} / {questionnaire.questions.length}</p>
              {questionnaire.provenance?.status && (
                <div className="disclaimer-box">
                  <b>Note:</b> {questionnaire.provenance.status} — {questionnaire.provenance.note}
                </div>)}
            </div>
            {(questionnaire.sections || []).map((sec) => (
              <div className="card" key={sec.id}>
                <h2>{sec.title}</h2>
                <p className="muted">{sec.description}</p>
                {sec.question_ids.map((qid) => {
                  const q = questionnaire.questions.find((x) => x.id === qid);
                  if (!q) return null;
                  return (
                    <div key={qid}>
                      <label className="field">{q.question_text}</label>
                      {q.options.map((o, i) => (
                        <label className="option" key={i}>
                          <input type="radio" name={qid} checked={answers[qid] === i}
                                 onChange={() => setAnswers({ ...answers, [qid]: i })} />
                          <span>{o.text}</span>
                        </label>))}
                    </div>);
                })}
              </div>))}
            <Banner message={error} />
            <button className="btn" disabled={busy || Object.keys(answers).length !== questionnaire.questions.length}
                    onClick={submitQuiz}>
              {busy ? "Calculating…" : "Calculate my Prakriti →"}
            </button>
          </>)}
      </div>),
    3: () => (
      <div className="card">
        <h2>Your Prakriti (computed from your answers)</h2>
        <div className="donut-row">
          <Donut p={prakriti.percentages} />
          <div className="legend">
            {Object.entries(prakriti.percentages).map(([d, v]) => (
              <div key={d}><span className="dot" style={{ background: DOSHA_COLOR[d] }} />{d[0].toUpperCase() + d.slice(1)}: <b>{v}%</b></div>))}
          </div>
        </div>
        <p><b>Constitution type:</b> {prakriti.dosha_type}</p>
        <p className="muted">Dominant: {prakriti.dominant} · Secondary: {prakriti.secondary} ·
           Scored from {prakriti.answered_count}/{prakriti.total_questions} questions. These percentages are
           calculated dynamically from your responses — nothing is hardcoded.</p>
        <button className="btn" onClick={() => go(4)}>Continue to current state →</button>
      </div>),
    4: () => (
      <div className="card">
        <h2>How do you feel today? <span className="muted">(manual entry)</span></h2>
        <p className="muted">Browsers cannot automatically read heart rate or sleep — all values below are
           <b> manually entered by you</b> and can be edited anytime.</p>
        <label className="field">Heart rate (BPM, 30–220)</label>
        <input type="number" min="30" max="220" value={state.heart_rate}
               onChange={(e) => set(state, { heart_rate: +e.target.value })} />
        <label className="field">Sleep last night (hours, 0.5–16)</label>
        <input type="number" min="0.5" max="16" step="0.5" value={state.sleep_hours}
               onChange={(e) => set(state, { sleep_hours: +e.target.value })} />
        {["sleep_quality", "stress", "energy"].map((k) => (
          <div key={k}>
            <label className="field">{k.replace("_", " ")} (1–10): <b>{state[k]}</b></label>
            <input type="range" min="1" max="10" value={state[k]}
                   onChange={(e) => set(state, { [k]: +e.target.value })} />
          </div>))}
        <label className="field">Physical activity today</label>
        <select value={state.activity} onChange={(e) => set(state, { activity: e.target.value })}>
          {["low", "moderate", "high"].map((a) => <option key={a}>{a}</option>)}
        </select>
        <label className="field">Current mood</label>
        <select value={state.mood} onChange={(e) => set(state, { mood: e.target.value })}>
          {MOODS.map((m) => <option key={m}>{m}</option>)}
        </select>
        <label className="field">Any of these today? (optional)</label>
        <div className="chips">
          {SYMPTOMS.map((s) => (
            <span key={s} className={`chip ${state.symptoms.includes(s) ? "on" : ""}`}
                  onClick={() => set(state, { symptoms: state.symptoms.includes(s)
                    ? state.symptoms.filter((x) => x !== s) : [...state.symptoms, s] })}>{s}</span>))}
        </div>
        <Banner message={error} />
        <button className="btn" onClick={() => go(5)}>Continue to environment →</button>
      </div>),
    5: () => (
      <div className="card">
        <h2>Your environment</h2>
        <p className="muted">Optional: with your permission we fetch current weather for an approximate
           location. Nothing is stored, and the plan works perfectly without it.</p>
        {[["manual", "Manual entry (always works)"], ["city", "Weather by city name"],
          ["auto", "Use my approximate location (GPS)"]].map(([m, label]) => (
          <label className="option" key={m}>
            <input type="radio" checked={envMode === m} onChange={() => { setEnvMode(m); setError(null); }} />
            <span>{label}</span>
          </label>))}
        {envMode === "manual" && (
          <>
            <label className="field">Temperature (°C)</label>
            <input type="number" value={env.temperature} onChange={(e) => setEnv({ ...env, temperature: +e.target.value })} />
            <label className="field">Humidity (%)</label>
            <input type="number" min="0" max="100" value={env.humidity} onChange={(e) => setEnv({ ...env, humidity: +e.target.value })} />
            <label className="field">Weather</label>
            <select value={env.weather} onChange={(e) => setEnv({ ...env, weather: e.target.value })}>
              {WEATHERS.map((w) => <option key={w}>{w}</option>)}
            </select>
            <label className="field">Season (optional — auto from month if blank)</label>
            <select value={env.season} onChange={(e) => setEnv({ ...env, season: e.target.value })}>
              <option value="">Auto</option>
              {SEASONS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </>)}
        {envMode === "city" && (<>
          <label className="field">City</label>
          <input type="text" placeholder="e.g. Pune" value={city} onChange={(e) => setCity(e.target.value)} />
        </>)}
        <Banner message={error} />
        <button className="btn" disabled={busy || (envMode === "city" && !city.trim())}
                onClick={finish}>{busy ? "Analyzing…" : "Generate my Dinacharya →"}</button>
      </div>),
    6: () => {
      const r = plan.recommendations, t = r.exercise;
      return (
        <div>
          <div className="card">
            <h2>Today's Dinacharya</h2>
            <p><b>Prakriti:</b> {Object.entries(r.profile.prakriti_percentages).map(([d, v]) => `${d} ${v}%`).join(" · ")}</p>
            <p><b>Current tendencies:</b> {Object.entries(r.profile.tendencies).map(([d, v]) => `${d} ${ARROW[v]}`).join(" · ")}</p>
            <p><b>Environment:</b> {r.profile.environment.season}, {r.profile.environment.temperature}°C,
               {r.profile.environment.humidity}% humidity, {r.profile.environment.weather} · Focus today: <b>{r.focus_dosha}</b></p>
          </div>
          <div className="card"><h2>🕑 Daily timeline</h2>
            {r.timeline.map((b, i) => (
              <div className="timeline-item" key={i}>
                <time>{b.time}</time><div><b>{b.title}</b> <span className="pill">{b.tag}</span><br />
                <span>{b.detail}</span><br /><span className="muted">Why: {b.reason}</span></div></div>))}
          </div>
          <div className="grid2">
            <div className="card"><h2>🍽 Diet</h2>
              <p className="muted">Favour tastes: {r.diet.favor_tastes.join(", ")}</p>
              <p><b>Breakfast:</b><List items={r.diet.breakfast} /></p>
              <p><b>Lunch:</b><List items={r.diet.lunch} /></p>
              <p><b>Dinner:</b><List items={r.diet.dinner} /></p>
              <p><b>Guidance:</b><List items={r.diet.guidance} /></p>
            </div>
            <div className="card"><h2>🏃 Exercise</h2>
              <p><b>{t.type}</b> — ~{t.duration_minutes} min, {t.intensity}</p>
              <List items={t.examples} /><p className="muted">{t.note}</p>
              {t.adjustments.length > 0 && <p><b>Adjusted today:</b><List items={t.adjustments.map((a) => a.text)} /></p>}
              <p className="muted">Why: {t.reason}</p>
              <h2>💧 Hydration</h2>
              <p>Target: <b>{r.hydration.target_litres} L</b></p><List items={r.hydration.tips} />
              <h2>😴 Sleep</h2>
              <p>Bedtime: <b>{r.sleep.bedtime}</b></p><List items={r.sleep.routine} />
              {r.sleep.adjustments.length > 0 && <List items={r.sleep.adjustments} />}
            </div>
          </div>
          <div className="grid2">
            <div className="card"><h2>✅ Pathya (do)</h2><List items={r.pathya} /></div>
            <div className="card"><h2>🚫 Apathya (avoid)</h2><List items={r.apathya} /></div>
          </div>
          <div className="card"><h2>🎵 Music / Raga</h2>
            <p><b>Goal:</b> {r.music.goal}</p>
            <p>{r.music.ragas.concat(r.music.season_ragas).map((x) => <span className="pill" key={x}>{x}</span>)}</p>
            <p className="muted">Instruments: {r.music.instruments.join(", ")} · {r.music.note} · {r.music.when}</p>
            <p className="muted">For focus work: {r.music.work_focus.suggestion}</p>
            <h2>🧘 Calming practices</h2><List items={r.calming_practices} />
            <h2>🌿 Lifestyle</h2><List items={r.lifestyle} />
          </div>
          <div className="card"><h2>❓ Why these recommendations?</h2><List items={r.explanations} /></div>
          <footer className="card disclaimer-box">{r.disclaimer}
            <br /><br /><button className="btn secondary" onClick={startOver}>Start a new assessment</button>
          </footer>
        </div>);
    },
  };

  return (
    <div className="container">
      <Stepper step={step} />
      {screens[step]()}
      {busy && step !== 6 && <p className="muted">Working…</p>}
    </div>
  );
}