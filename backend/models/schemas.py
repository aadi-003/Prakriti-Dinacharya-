"""Pydantic v2 request models — all input validation lives here (realistic ranges, clear errors)."""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from services.vikriti_engine import MOODS, ACTIVITIES, SYMPTOMS
from services.environment_engine import SEASONS, ALLOWED_WEATHER


class PrakritiRequest(BaseModel):
    answers: dict


class CurrentState(BaseModel):
    # All values are MANUAL entries (browsers cannot reliably read heart rate / sleep sensors).
    heart_rate: int = Field(ge=30, le=220, description="Manually measured heart rate (BPM)")
    sleep_hours: float = Field(gt=0, le=16, description="Last night's sleep duration in hours")
    sleep_quality: int = Field(ge=1, le=10)
    stress: int = Field(ge=1, le=10)
    energy: int = Field(ge=1, le=10)
    activity: Literal["low", "moderate", "high"]
    mood: Literal["calm", "anxious", "restless", "irritable", "low", "sluggish", "focused"]
    symptoms: List[str] = []

    @field_validator("symptoms")
    @classmethod
    def check_symptoms(cls, v):
        allowed = set(SYMPTOMS)
        bad = [s for s in v if s not in allowed]
        if bad:
            raise ValueError(f"Unknown symptoms {bad}. Allowed values: {sorted(allowed)}")
        if len(v) > 12:
            raise ValueError("At most 12 symptoms are allowed")
        return v


class VikritiRequest(BaseModel):
    prakriti_percentages: dict
    current_state: CurrentState

    @model_validator(mode="after")
    def check_percentages(self):
        p = self.prakriti_percentages
        if set(p.keys()) != {"vata", "pitta", "kapha"}:
            raise ValueError("prakriti_percentages must contain exactly 'vata', 'pitta' and 'kapha'")
        for d, v in p.items():
            if not isinstance(v, (int, float)) or not (0 <= v <= 100):
                raise ValueError(f"{d} percentage must be a number between 0 and 100")
        if not (99 <= sum(p.values()) <= 101):
            raise ValueError("prakriti_percentages must sum to approximately 100")
        return self


class EnvironmentRequest(BaseModel):
    mode: Literal["auto", "city", "manual"] = "manual"
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    city: Optional[str] = Field(default=None, min_length=1, max_length=80)
    temperature: Optional[float] = Field(default=None, ge=-50, le=60)
    humidity: Optional[float] = Field(default=None, ge=0, le=100)
    weather: Optional[str] = None
    season: Optional[str] = None
    month: Optional[int] = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def check_mode_fields(self):
        if self.mode == "auto" and (self.latitude is None or self.longitude is None):
            raise ValueError("mode 'auto' requires latitude and longitude")
        if self.mode == "city" and not self.city:
            raise ValueError("mode 'city' requires a city name")
        if self.mode == "manual" and (self.temperature is None or self.humidity is None):
            raise ValueError("mode 'manual' requires temperature and humidity")
        if self.weather is not None and self.weather not in ALLOWED_WEATHER:
            raise ValueError(f"weather must be one of {list(ALLOWED_WEATHER)}")
        if self.season is not None and self.season not in SEASONS:
            raise ValueError(f"season must be one of {list(SEASONS)}")
        return self


class AssessmentRequest(BaseModel):
    answers: dict
    current_state: CurrentState
    environment: EnvironmentRequest
    preferences: dict = {}