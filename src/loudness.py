"""Normalizacion de loudness segun estandar EBU R128 / ITU BS.1770."""
import numpy as np
import pyloudnorm as pyln


# Target LUFS estandar (mismo que usan Spotify y YouTube)
TARGET_LUFS = -14.0

# Cache de mediciones por filepath para no recalcular
_lufs_cache: dict = {}


def measure_lufs(y: np.ndarray, sr: int) -> float:
    """Mide el loudness integrado de una senal en LUFS.

    y puede ser mono (n,) o estereo (2, n) o (n, 2).
    Retorna LUFS (valor negativo, tipicamente entre -30 y -6).
    """
    # pyloudnorm espera (n,) mono o (n, channels) estereo
    if y.ndim == 1:
        signal = y
    elif y.shape[0] == 2 and y.shape[1] != 2:
        signal = y.T  # (2, n) -> (n, 2)
    else:
        signal = y

    meter = pyln.Meter(sr)
    try:
        lufs = meter.integrated_loudness(signal)
        return float(lufs)
    except Exception:
        return TARGET_LUFS  # fallback si falla


def normalize_to_target(
    y: np.ndarray,
    sr: int,
    target_lufs: float = TARGET_LUFS,
    max_gain_db: float = 6.0,
) -> np.ndarray:
    """Normaliza el audio al target LUFS, con limite de ganancia.

    max_gain_db: nunca subimos mas de esto (para evitar amplificar ruido en
    canciones muy bajas) ni bajamos mas de esto al reves.
    """
    current_lufs = measure_lufs(y, sr)
    gain_db = target_lufs - current_lufs

    # Clamp del gain para evitar cambios extremos
    gain_db = float(np.clip(gain_db, -max_gain_db, max_gain_db))
    gain_linear = 10 ** (gain_db / 20)

    return (y * gain_linear).astype(np.float32)


def normalize_cached(
    filepath: str,
    y: np.ndarray,
    sr: int,
    target_lufs: float = TARGET_LUFS,
    max_gain_db: float = 6.0,
) -> np.ndarray:
    """Como normalize_to_target pero usa cache por filepath para evitar remedir."""
    if filepath in _lufs_cache:
        current_lufs = _lufs_cache[filepath]
    else:
        current_lufs = measure_lufs(y, sr)
        _lufs_cache[filepath] = current_lufs

    gain_db = target_lufs - current_lufs
    gain_db = float(np.clip(gain_db, -max_gain_db, max_gain_db))
    gain_linear = 10 ** (gain_db / 20)
    return (y * gain_linear).astype(np.float32)