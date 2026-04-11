"""Esquema y operaciones básicas de la base de datos SQLite."""
import sqlite3
from pathlib import Path

DB_PATH = Path("data/library.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    title TEXT,
    artist TEXT,
    album TEXT,
    duration REAL,
    bpm REAL,
    key INTEGER,
    mode INTEGER,
    camelot TEXT,
    energy REAL,
    danceability REAL,
    beats_json TEXT,
    downbeats_json TEXT,
    analyzed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_camelot ON tracks(camelot);
CREATE INDEX IF NOT EXISTS idx_bpm ON tracks(bpm);
"""


def get_conn() -> sqlite3.Connection:
    """Abre una conexión a la base de datos, creando la carpeta data/ si no existe."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # para acceder a las columnas por nombre
    return conn


def init_db() -> None:
    """Crea la tabla tracks y sus índices si no existen."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def track_exists(filepath: str) -> bool:
    """Verifica si un archivo ya fue analizado previamente."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM tracks WHERE filepath = ?", (filepath,)
        ).fetchone()
        return row is not None


def insert_track(data: dict) -> None:
    """Inserta o reemplaza un track analizado en la base de datos."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    with get_conn() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO tracks ({cols}) VALUES ({placeholders})",
            tuple(data.values()),
        )
        conn.commit()


def count_tracks() -> int:
    """Devuelve cuántos tracks hay analizados. Útil para debugging."""
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]