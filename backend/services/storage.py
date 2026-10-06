"""Optional, privacy-safe SQLite logging of ANONYMIZED summaries. Off by default (SAVE_ASSESSMENTS)."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _db_path() -> Path:
    default_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir = Path(os.getenv("DATA_DIR", str(default_dir)))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "assessments.db"


def save_assessment_summary(prakriti: dict, vikriti: dict, environment: dict) -> bool:
    """
    Stores ONLY: timestamp, dosha percentages, dominant/focus dosha, season, weather.
    Never stores: names, identifiers, coordinates, raw answers.
    """
    if os.getenv("SAVE_ASSESSMENTS", "false").strip().lower() not in ("1", "true", "yes"):
        return False
    pct = prakriti["percentages"]
    focus = max(pct, key=lambda d: pct[d] - prakriti["percentages"][d]) if False else prakriti["dominant"]
    conn = sqlite3.connect(str(_db_path()))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS assessment_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            dominant_prakriti TEXT, vata REAL, pitta REAL, kapha REAL,
            season TEXT, weather TEXT, temperature REAL, humidity REAL)""")
        conn.execute(
            "INSERT INTO assessment_summaries (created_at, dominant_prakriti, vata, pitta, kapha, "
            "season, weather, temperature, humidity) VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), prakriti["dominant"],
             pct["vata"], pct["pitta"], pct["kapha"],
             environment.get("season"), environment.get("weather"),
             environment.get("temperature"), environment.get("humidity")))
        conn.commit()
    finally:
        conn.close()
    return True