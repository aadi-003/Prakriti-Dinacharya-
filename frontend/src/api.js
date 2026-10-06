const BASE = import.meta.env.VITE_API_URL || "";

async function handle(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.error?.message || `Request failed (${res.status})`);
  return body;
}
const post = (path, data) =>
  fetch(`${BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(data) }).then(handle);

export const api = {
  health: () => fetch(`${BASE}/api/health`).then(handle),
  getQuestionnaire: () => fetch(`${BASE}/api/questionnaire`).then(handle),
  calculatePrakriti: (answers) => post("/api/prakriti/calculate", { answers }),
  fullAssessment: (payload) => post("/api/assessment", payload),
};