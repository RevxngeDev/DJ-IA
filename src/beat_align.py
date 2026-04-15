"""Alineacion de beats, time-stretch y calculo de puntos de entrada/salida."""
import json

import numpy as np
import pyrubberband as pyrb


def calculate_stretch_ratio(source_bpm: float, target_bpm: float) -> float:
    """Calcula el ratio de time-stretch para llevar source_bpm a target_bpm.

    Un ratio > 1.0 acelera la cancion (mas BPM).
    Un ratio < 1.0 la frena (menos BPM).

    Limitamos a un rango razonable (+-8%) para evitar artefactos audibles.
    """
    if source_bpm <= 0 or target_bpm <= 0:
        return 1.0
    ratio = target_bpm / source_bpm
    # Clamp a +-8% para mantener calidad sonora
    return float(np.clip(ratio, 0.92, 1.08))


def time_stretch_track(y: np.ndarray, sr: int, ratio: float) -> np.ndarray:
    """Aplica time-stretch via rubberband. Mantiene el pitch original.

    ratio: cuanto mas rapido (>1) o mas lento (<1) debe sonar.
    y puede ser mono (n,) o estereo (2, n).
    """
    if abs(ratio - 1.0) < 0.001:
        return y  # sin cambio perceptible, ahorro de CPU

    if y.ndim == 1:
        # pyrubberband espera (n_samples,) o (n_samples, n_channels)
        return pyrb.time_stretch(y, sr, ratio).astype(np.float32)
    else:
        # Nuestro formato es (2, n), pyrubberband quiere (n, 2)
        y_transposed = y.T
        stretched = pyrb.time_stretch(y_transposed, sr, ratio)
        return stretched.T.astype(np.float32)


def get_beats_and_downbeats(track: dict) -> tuple[list[float], list[float]]:
    """Extrae las listas de beats y downbeats desde el dict de un track de DB."""
    beats = json.loads(track["beats_json"]) if track.get("beats_json") else []
    downbeats = json.loads(track["downbeats_json"]) if track.get("downbeats_json") else []
    return beats, downbeats


def find_exit_point(track: dict, bars_before_end: int = 16) -> float:
    """Encuentra el downbeat donde debe iniciar la transicion de salida.

    bars_before_end: cuantos compases antes del final de la cancion.
    Por defecto 16 compases = ~42 segundos a 92 BPM.

    Retorna el tiempo en segundos del downbeat elegido.
    """
    _, downbeats = get_beats_and_downbeats(track)
    duration = track.get("duration", 0)

    if not downbeats or duration <= 0:
        # Fallback: punto 80% del track
        return duration * 0.80

    # Duracion aproximada de 1 compas en segundos
    bpm = track.get("bpm", 95)
    bar_seconds = (60.0 / bpm) * 4  # 4 beats por compas
    target_time = duration - (bars_before_end * bar_seconds)

    # Buscar el downbeat mas cercano al target, que no sea demasiado temprano
    target_time = max(target_time, duration * 0.5)  # nunca antes del 50% del track

    # Elegir el downbeat mas cercano al target
    closest = min(downbeats, key=lambda db: abs(db - target_time))
    return closest


def find_entry_point(track: dict, bars_from_start: int = 16) -> float:
    """Encuentra el downbeat donde debe empezar a sonar la cancion entrante.

    bars_from_start: cuantos compases saltar desde el inicio (para pasar el intro).
    Por defecto 16 compases = primera seccion musical clara.

    Retorna el tiempo en segundos del downbeat elegido.
    """
    _, downbeats = get_beats_and_downbeats(track)
    duration = track.get("duration", 0)

    if not downbeats or duration <= 0:
        return 0.0

    bpm = track.get("bpm", 95)
    bar_seconds = (60.0 / bpm) * 4
    target_time = bars_from_start * bar_seconds

    # No pasarnos del 40% de la cancion
    target_time = min(target_time, duration * 0.4)

    closest = min(downbeats, key=lambda db: abs(db - target_time))
    return closest


def seconds_to_samples(seconds: float, sr: int) -> int:
    """Convierte segundos a indice de sample."""
    return int(round(seconds * sr))