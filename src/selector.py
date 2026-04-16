"""Selector IA: genera setlists optimas aplicando reglas de mezcla profesional."""
import math
import random
from typing import Optional

from src.database import get_conn
from src.camelot import compatible_camelots


from src.config import (
    BPM_TOLERANCE,
    ENERGY_WEIGHT,
    BPM_WEIGHT,
    CAMELOT_PERFECT_BONUS,
    CAMELOT_OK_PENALTY,
    SAME_ALBUM_PENALTY,
    STAGNATION_PENALTY,
    ARTIST_DIVERSITY_BONUS,
    ENERGY_MIN,
    ENERGY_MAX,
    ENERGY_END,
    ENERGY_PEAK_POSITION_DEFAULT,
)


def load_library() -> list[dict]:
    """Carga todos los tracks analizados desde SQLite."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filepath, title, artist, album, duration, bpm, "
            "camelot, energy, danceability FROM tracks WHERE bpm IS NOT NULL"
        ).fetchall()
    return [dict(r) for r in rows]


def target_energy_for_position(
    position: float,
    peak_position: float = ENERGY_PEAK_POSITION_DEFAULT,
) -> float:
    """Curva de energia tipo arco: sube hasta el peak y luego baja."""
    if position <= peak_position:
        t = position / peak_position
        return ENERGY_MIN + (ENERGY_MAX - ENERGY_MIN) * (t ** 0.8)
    else:
        t = (position - peak_position) / (1 - peak_position)
        return ENERGY_MAX - (ENERGY_MAX - ENERGY_END) * (t ** 1.2)

def bpm_compatible(bpm_a: float, bpm_b: float) -> bool:
    """Dos BPMs son compatibles si estan dentro de +-BPM_TOLERANCE."""
    if bpm_a == 0 or bpm_b == 0:
        return False
    ratio = bpm_b / bpm_a
    return (1 - BPM_TOLERANCE) <= ratio <= (1 + BPM_TOLERANCE)


def score_candidate(
    current: dict,
    candidate: dict,
    target_energy: float,
    compat_camelots: list[str],
    tolerance_multiplier: float = 1.0,
    recent_camelots: list[str] = None,
    recent_artists: list[str] = None,
) -> Optional[float]:
    """Calcula el score de una cancion candidata como siguiente del set."""
    effective_tolerance = BPM_TOLERANCE * tolerance_multiplier
    if current["bpm"] == 0 or candidate["bpm"] == 0:
        return None
    ratio = candidate["bpm"] / current["bpm"]
    if not ((1 - effective_tolerance) <= ratio <= (1 + effective_tolerance)):
        return None

    score = 10.0

    # Compatibilidad armonica
    if candidate["camelot"] in compat_camelots:
        score += CAMELOT_PERFECT_BONUS
    else:
        score -= CAMELOT_OK_PENALTY

    # Penalizacion por estancarse en la misma Camelot
    if recent_camelots:
        same_count = sum(1 for c in recent_camelots[-2:] if c == candidate["camelot"])
        if same_count >= 2:
            score -= STAGNATION_PENALTY

    # Energia
    energy_diff = abs((candidate["energy"] or 0.5) - target_energy)
    score -= energy_diff * ENERGY_WEIGHT * 10

    # BPM
    bpm_diff_pct = abs(ratio - 1.0)
    score -= bpm_diff_pct * BPM_WEIGHT * 50

    # Mismo album consecutivo
    if current.get("album") and candidate.get("album") == current["album"]:
        score -= SAME_ALBUM_PENALTY

    # Bonus por artista no repetido recientemente
    if recent_artists and candidate.get("artist"):
        if candidate["artist"] not in recent_artists[-3:]:
            score += ARTIST_DIVERSITY_BONUS
    return score

def generate_setlist(
    duration_minutes: float = 30,
    seed_track_id: Optional[int] = None,
    peak_position: float = 0.65,
) -> list[dict]:
    """Genera una setlist ordenada segun reglas de mezcla profesional.

    duration_minutes: duracion deseada total del set.
    seed_track_id: ID del track inicial. Si es None, elige uno con energia baja aleatoriamente.
    peak_position: posicion (0-1) donde debe caer el pico de energia.
    """
    library = load_library()
    if not library:
        raise RuntimeError("Biblioteca vacia. Corre run_ingest.py primero.")

    by_id = {t["id"]: t for t in library}
    target_duration_sec = duration_minutes * 60

    # Elegir semilla: si no se pasa, una con energia baja (para empezar suave)
    if seed_track_id is not None:
        if seed_track_id not in by_id:
            raise ValueError(f"Track {seed_track_id} no existe")
        current = by_id[seed_track_id]
    else:
        low_energy = sorted(library, key=lambda t: t["energy"] or 1.0)[:15]
        current = random.choice(low_energy)

    setlist = [{**current, "reason": "INICIO"}]
    used_ids = {current["id"]}
    elapsed = current["duration"] or 180

    while elapsed < target_duration_sec:
        position = elapsed / target_duration_sec
        target_energy = target_energy_for_position(position, peak_position)
        compat = compatible_camelots(current["camelot"])

        # Candidatos: todos los que no se han usado
        candidates = [t for t in library if t["id"] not in used_ids]
        if not candidates:
            break

        # Historial reciente para evitar estancamiento
        recent_camelots = [t["camelot"] for t in setlist[-3:]]
        recent_artists = [t.get("artist") for t in setlist[-3:] if t.get("artist")]

        # Intentar con tolerancia normal, luego relajada
        best = None
        for tolerance_mult in [1.0, 1.5, 2.0]:
            scored = []
            for cand in candidates:
                s = score_candidate(
                    current, cand, target_energy, compat, tolerance_mult,
                    recent_camelots=recent_camelots,
                    recent_artists=recent_artists,
                )
                if s is not None:
                    scored.append((s, cand))
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                best = scored[0]
                break

        if best is None:
            # Nadie compatible, cortamos el set aqui
            break

        score, next_track = best
        reason = _describe_transition(current, next_track, target_energy)
        setlist.append({**next_track, "reason": reason})
        used_ids.add(next_track["id"])
        elapsed += next_track["duration"] or 180
        current = next_track

    return setlist


def _describe_transition(current: dict, next_track: dict, target_energy: float) -> str:
    """Genera una descripcion legible de la transicion para debug/UI."""
    parts = []

    # Camelot
    if next_track["camelot"] == current["camelot"]:
        parts.append("misma key")
    elif next_track["camelot"] in compatible_camelots(current["camelot"]):
        parts.append(f"Camelot {current['camelot']}->{next_track['camelot']}")
    else:
        parts.append(f"key forzada {current['camelot']}->{next_track['camelot']}")

    # BPM
    bpm_delta = next_track["bpm"] - current["bpm"]
    if abs(bpm_delta) < 1:
        parts.append("mismo BPM")
    else:
        sign = "+" if bpm_delta > 0 else ""
        parts.append(f"BPM {sign}{bpm_delta:.1f}")

    # Energia
    e_delta = (next_track["energy"] or 0.5) - (current["energy"] or 0.5)
    if abs(e_delta) > 0.05:
        sign = "+" if e_delta > 0 else ""
        parts.append(f"energy {sign}{e_delta:.2f}")

    return " | ".join(parts)


def print_setlist(setlist: list[dict]) -> None:
    """Imprime una setlist de forma legible."""
    print("\n=== SETLIST GENERADO ===\n")
    total_sec = 0
    for i, t in enumerate(setlist, 1):
        dur = t.get("duration") or 0
        total_sec += dur
        dur_str = f"{int(dur // 60)}:{int(dur % 60):02d}"
        title = (t["title"] or "?")[:38]
        artist = (t["artist"] or "?")[:18]
        print(
            f"{i:2d}. {title:38s} | {artist:18s} | "
            f"{t['bpm']:5.1f} BPM | {t['camelot']:4s} | "
            f"E={t['energy']:.2f} | {dur_str} | {t['reason']}"
        )
    total_min = total_sec / 60
    print(f"\nDuracion total: {total_min:.1f} minutos ({len(setlist)} tracks)")