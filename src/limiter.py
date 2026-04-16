"""Soft limiter para masterizacion final del mix (version vectorizada)."""
import numpy as np
from scipy.ndimage import maximum_filter1d


def soft_limiter(
    y: np.ndarray,
    sr: int,
    threshold_db: float = -1.0,
    lookahead_ms: float = 5.0,
    release_ms: float = 50.0,
) -> np.ndarray:
    """Soft limiter con lookahead, vectorizado con scipy.

    threshold_db: nivel maximo permitido (en dBFS). -1.0 es estandar.
    lookahead_ms: anticipacion para suavizar la reduccion.
    release_ms: cuanto tarda en soltar la reduccion despues de un pico.
    """
    threshold = 10 ** (threshold_db / 20)

    # Envolvente: maximo absoluto entre canales (mantiene imagen estereo)
    if y.ndim == 1:
        envelope = np.abs(y)
    else:
        envelope = np.max(np.abs(y), axis=0)

    n = len(envelope)
    lookahead_samples = max(1, int((lookahead_ms / 1000) * sr))

    # Maximo movil hacia adelante usando maximum_filter1d (super rapido en C)
    # origin = -lookahead_samples//2 desplaza la ventana hacia adelante
    window_size = lookahead_samples
    max_envelope = maximum_filter1d(envelope, size=window_size, origin=-(window_size // 2))

    # Target gain por sample
    target_gain = np.where(
        max_envelope > threshold,
        threshold / np.maximum(max_envelope, 1e-9),
        1.0,
    ).astype(np.float32)

    # Aplicar release exponencial (vectorizado con loop simple, mucho mas rapido
    # que el anterior porque ya no recalcula maximos en cada paso)
    release_samples = max(1, int((release_ms / 1000) * sr))
    release_coeff = float(np.exp(-1.0 / release_samples))

    smoothed = np.empty(n, dtype=np.float32)
    smoothed[0] = target_gain[0]
    current = float(target_gain[0])
    for i in range(1, n):
        target = float(target_gain[i])
        if target < current:
            current = target
        else:
            current = target + (current - target) * release_coeff
        smoothed[i] = current

    if y.ndim == 1:
        return (y * smoothed).astype(np.float32)
    else:
        return (y * smoothed).astype(np.float32)