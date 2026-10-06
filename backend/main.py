"""FastAPI application — Prakriti–Vikriti Dinacharya API (educational wellness prototype)."""
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models.schemas import (PrakritiRequest, VikritiRequest,
                            EnvironmentRequest, AssessmentRequest)
from services.constants import DISCLAIMER
from services.errors import AppError
from services import prakriti_engine, vikriti_engine, environment_engine, recommendation_engine
from services.storage import save_assessment_summary

app = FastAPI(
    title="Prakriti–Vikriti Dinacharya API",
    version="1.0.0",
    description="Educational wellness prototype. NOT a medical diagnostic tool.",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"code": exc.code, "message": exc.message,
                                           "details": exc.details}})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500,
                        content={"error": {"code": "internal_error",
                                           "message": "Something went wrong on the server.",
                                           "details": None}})


@app.get("/")
def root():
    return {"service": "prakriti-dinacharya-api", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat(), "version": "1.0.0"}


@app.get("/api/questionnaire")
def get_questionnaire():
    q = prakriti_engine.get_questionnaire()
    return {"title": q.get("title"), "instructions": q.get("instructions"),
            "estimated_minutes": q.get("estimated_minutes", 5),
            "sections": q.get("sections", []), "questions": q["questions"],
            "provenance": q.get("provenance"), "disclaimer": DISCLAIMER}


@app.post("/api/prakriti/calculate")
def prakriti(req: PrakritiRequest):
    return prakriti_engine.calculate_prakriti(req.answers)


@app.post("/api/vikriti/calculate")
def vikriti(req: VikritiRequest):
    return vikriti_engine.estimate_vikriti(req.prakriti_percentages, req.current_state.model_dump())


@app.post("/api/environment")
def environment(req: EnvironmentRequest):
    return environment_engine.resolve_environment(req)


def _full_assessment(req: AssessmentRequest) -> dict:
    prak = prakriti_engine.calculate_prakriti(req.answers)
    state = req.current_state.model_dump()
    vik = vikriti_engine.estimate_vikriti(prak["percentages"], state)
    env = environment_engine.resolve_environment(req.environment)
    recs = recommendation_engine.generate_recommendations(prak, vik, env, state, req.preferences)
    save_assessment_summary(prak, vik, env)
    return {"prakriti": prak, "vikriti": vik, "environment": env,
            "recommendations": recs, "explanations": recs["explanations"],
            "generated_at": datetime.now(timezone.utc).isoformat(), "disclaimer": DISCLAIMER}


@app.post("/api/recommendations")
def recommendations(req: AssessmentRequest):
    return _full_assessment(req)["recommendations"]


@app.post("/api/assessment")
def assessment(req: AssessmentRequest):
    return _full_assessment(req)