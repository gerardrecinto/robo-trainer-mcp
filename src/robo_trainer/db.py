from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

_DB_PATH = Path.home() / ".robo-trainer" / "data.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS food_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    meal_type   TEXT,
    food_name   TEXT NOT NULL,
    grams       REAL,
    calories    REAL,
    protein_g   REAL,
    carbs_g     REAL,
    fat_g       REAL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS nutrition_goals (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    calories    REAL DEFAULT 2500,
    protein_g   REAL DEFAULT 180,
    carbs_g     REAL DEFAULT 300,
    fat_g       REAL DEFAULT 80,
    updated_at  TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO nutrition_goals (id) VALUES (1);

CREATE TABLE IF NOT EXISTS training_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    exercise    TEXT NOT NULL,
    set_number  INTEGER DEFAULT 1,
    weight_kg   REAL,
    reps        INTEGER,
    rpe         REAL,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sleep_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,
    hours       REAL NOT NULL,
    quality     INTEGER,
    hrv_ms      REAL,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS mood_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,
    mood        INTEGER,
    energy      INTEGER,
    stress      INTEGER,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS event_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT NOT NULL,
    event_name          TEXT NOT NULL,
    implement_weight_kg REAL,
    reps                INTEGER,
    time_seconds        REAL,
    distance_meters     REAL,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);
"""


def init_db(path: Path = _DB_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(_SCHEMA)
    return path


@contextmanager
def get_conn(path: Path = _DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
