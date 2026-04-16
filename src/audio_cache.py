"""Cache en disco de audio decodificado para acelerar renders repetidos."""
import hashlib
from pathlib import Path

import numpy as np

from src.audio_utils import load_audio as _load_audio_uncached, DEFAULT_SR

CACHE_DIR = Path("data/audio_cache")


def _cache_key(filepath: str, sr: int) -> Path:
    """Genera la ruta del archivo de cache para un (filepath, sr) dado.

    Usamos hash del path + tamaño del archivo como key. Si el archivo cambia
    (distinto tamaño), el hash cambia y se regenera el cache automaticamente.
    """
    p = Path(filepath)
    size = p.stat().st_size if p.exists() else 0
    raw = f"{filepath}|{size}|{sr}".encode("utf-8")
    h = hashlib.sha1(raw).hexdigest()[:16]
    return CACHE_DIR / f"{h}.npy"


def load_audio_cached(filepath: str, sr: int = DEFAULT_SR) -> tuple[np.ndarray, int]:
    """Wrapper de load_audio con cache en disco transparente."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_key(filepath, sr)

    if cache_path.exists():
        try:
            y = np.load(cache_path)
            return y, sr
        except Exception:
            # Si el cache esta corrupto, lo borramos y recargamos
            cache_path.unlink(missing_ok=True)

    # No hay cache: cargamos normal y guardamos
    y, sr_out = _load_audio_uncached(filepath, sr)
    try:
        np.save(cache_path, y)
    except Exception:
        pass  # si no se puede escribir el cache, seguimos igual
    return y, sr_out


def clear_cache() -> int:
    """Borra todo el cache de audio. Retorna cuantos archivos elimino."""
    if not CACHE_DIR.exists():
        return 0
    files = list(CACHE_DIR.glob("*.npy"))
    for f in files:
        f.unlink(missing_ok=True)
    return len(files)


def cache_size_mb() -> float:
    """Devuelve el tamano total del cache en MB."""
    if not CACHE_DIR.exists():
        return 0.0
    total = sum(f.stat().st_size for f in CACHE_DIR.glob("*.npy"))
    return total / (1024 * 1024)