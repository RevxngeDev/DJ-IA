"""Análisis de audio: BPM, key, beats, energía y metadata."""
import json
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np
from mutagen import File as MutagenFile

from src.camelot import to_camelot


def read_tags(filepath: str) -> dict:
    """Lee metadata (título, artista, álbum) de los tags ID3/MP4 del archivo.
    Si no puede leer los tags, devuelve un diccionario con valores None.
    """
    try:
        f = MutagenFile(filepath, easy=True)
        if not f:
            return {"title": None, "artist": None, "album": None}
        return {
            "title": f.get("title", [None])[0],
            "artist": f.get("artist", [None])[0],
            "album": f.get("album", [None])[0],
        }
    except Exception:
        return {"title": None, "artist": None, "album": None}


def estimate_key(y: np.ndarray, sr: int) -> tuple[int, int]:
    """Estima la tonalidad de la canción usando perfiles Krumhansl-Schmuckler.

    Retorna (key, mode) donde:
    - key: 0=C, 1=C#, 2=D, ..., 11=B
    - mode: 0=minor, 1=major
    """
    # Extraer el perfil cromático promedio de toda la canción
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)

    # Perfiles teóricos de Krumhansl (cómo "suena" cada tonalidad)
    major_profile = np.array(
        [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    )
    minor_profile = np.array(
        [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
    )

    # Probar las 24 tonalidades posibles y quedarnos con la mejor correlación
    best_score = -1.0
    best_key = 0
    best_mode = 1

    for shift in range(12):
        # Correlación con perfil mayor rotado
        major_corr = np.corrcoef(np.roll(major_profile, shift), chroma_mean)[0, 1]
        if major_corr > best_score:
            best_score = major_corr
            best_key = shift
            best_mode = 1

        # Correlación con perfil menor rotado
        minor_corr = np.corrcoef(np.roll(minor_profile, shift), chroma_mean)[0, 1]
        if minor_corr > best_score:
            best_score = minor_corr
            best_key = shift
            best_mode = 0

    return best_key, best_mode


def analyze_track(filepath: str) -> dict:
    """Analiza un archivo de audio y devuelve un diccionario con toda la info.

    Este diccionario tiene exactamente las columnas de la tabla tracks en SQLite,
    listo para pasar directo a insert_track().
    """
    # Cargar el audio: mono a 22050 Hz (estándar para análisis con librosa)
    # Esto funciona con MP3, M4A, FLAC, WAV, OGG gracias a ffmpeg
    y, sr = librosa.load(filepath, sr=22050, mono=True)

    # Duración total en segundos
    duration = librosa.get_duration(y=y, sr=sr)

    # Detección de BPM y posiciones de beats
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    # tempo puede venir como array en algunas versiones de librosa
    bpm = float(tempo) if np.isscalar(tempo) else float(tempo[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    # Downbeats: cada 4 beats (asumiendo 4/4, estándar en reggaetón/trap/pop)
    downbeats = beats[::4]

    # Detección de tonalidad
    key, mode = estimate_key(y, sr)
    camelot = to_camelot(key, mode)

    # Energía: basada en RMS (root mean square), normalizada entre 0 y 1
    rms = librosa.feature.rms(y=y).mean()
    energy = float(np.clip(rms * 10, 0, 1))

    # Danceability: basada en la regularidad del onset (ataque rítmico)
    # Un ritmo muy regular = alta danceability (bueno para reggaetón)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    mean_onset = onset_env.mean()
    if mean_onset > 0:
        danceability = float(np.clip(onset_env.std() / mean_onset, 0, 1))
    else:
        danceability = 0.0

    # Leer metadata del archivo
    tags = read_tags(filepath)

    return {
        "filepath": str(Path(filepath).resolve()),
        "title": tags.get("title") or Path(filepath).stem,
        "artist": tags.get("artist"),
        "album": tags.get("album"),
        "duration": round(duration, 2),
        "bpm": round(bpm, 1),
        "key": int(key),
        "mode": int(mode),
        "camelot": camelot,
        "energy": round(energy, 3),
        "danceability": round(danceability, 3),
        "beats_json": json.dumps([round(b, 3) for b in beats]),
        "downbeats_json": json.dumps([round(d, 3) for d in downbeats]),
        "analyzed_at": datetime.utcnow().isoformat(),
    }