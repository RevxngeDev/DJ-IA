"""Transicion DJ profesional: crossfade con bass swap."""
import numpy as np

from src.audio_utils import apply_eq_3band


def crossfade_with_bass_swap(
    a: np.ndarray,
    b: np.ndarray,
    sr: int,
    duration_seconds: float = 20.0,
) -> np.ndarray:
    """Cruza dos buffers estereo con la tecnica de bass swap.

    Requisitos:
    - a y b deben tener shape (2, n_samples).
    - a y b deben estar ya alineados al mismo BPM y empezando en un downbeat.
    - a debe ser la cancion saliente; b la entrante.
    - Ambas deben tener al menos duration_seconds de duracion.

    Retorna un buffer (2, n) con la transicion completa y la cola de la entrante.
    """
    n = int(duration_seconds * sr)

    # Asegurar que ambos tengan al menos n samples
    if a.shape[1] < n or b.shape[1] < n:
        raise ValueError(
            f"Buffers muy cortos: a={a.shape[1]}, b={b.shape[1]}, "
            f"se necesitan al menos {n}"
        )

    # Tomar solo la parte que participa en el crossfade
    a_cross = a[:, :n].copy()
    b_cross = b[:, :n].copy()

    # ----- Curvas de ganancia para mids/highs (crossfade lineal) -----
    # Usamos curva equal-power (coseno) para que la suma de energia sea constante
    t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
    fade_out = np.cos(t)  # 1.0 -> 0.0
    fade_in = np.sin(t)   # 0.0 -> 1.0

    # ----- Curvas para lows (swap brusco en el medio) -----
    # Usamos una sigmoide centrada en n/2 para transicion rapida pero no discontinua
    swap_sharpness = 12.0  # mayor = swap mas brusco
    x = np.linspace(-1, 1, n, dtype=np.float32)
    sigmoid = 1.0 / (1.0 + np.exp(swap_sharpness * x))
    lows_out = sigmoid          # 1.0 -> 0.0 (cae en el medio)
    lows_in = 1.0 - sigmoid     # 0.0 -> 1.0 (sube en el medio)

    # ----- Aplicar EQ a cada buffer y sumar con sus ganancias -----
    # Separamos cada track en sus 3 bandas
    a_lows = apply_eq_3band(a_cross, sr, low_gain=1.0, mid_gain=0.0, high_gain=0.0)
    a_rest = apply_eq_3band(a_cross, sr, low_gain=0.0, mid_gain=1.0, high_gain=1.0)

    b_lows = apply_eq_3band(b_cross, sr, low_gain=1.0, mid_gain=0.0, high_gain=0.0)
    b_rest = apply_eq_3band(b_cross, sr, low_gain=0.0, mid_gain=1.0, high_gain=1.0)

    # Aplicar las curvas de ganancia sample a sample
    a_mix = a_lows * lows_out + a_rest * fade_out
    b_mix = b_lows * lows_in + b_rest * fade_in

    crossfade_region = (a_mix + b_mix).astype(np.float32)

    # ----- Concatenar con la cola de b (lo que viene despues del crossfade) -----
    b_tail = b[:, n:]
    result = np.concatenate([crossfade_region, b_tail], axis=1)

    # Proteccion contra clipping
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.98

    return result


def simple_crossfade(
    a: np.ndarray,
    b: np.ndarray,
    sr: int,
    duration_seconds: float = 6.0,
) -> np.ndarray:
    """Crossfade simple equal-power sin bass swap.
    Fallback para cuando las canciones son muy distintas o para pruebas rapidas.
    """
    n = int(duration_seconds * sr)
    if a.shape[1] < n or b.shape[1] < n:
        raise ValueError("Buffers muy cortos para el crossfade solicitado")

    a_cross = a[:, :n]
    b_cross = b[:, :n]

    t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
    fade_out = np.cos(t)
    fade_in = np.sin(t)

    crossfade = (a_cross * fade_out + b_cross * fade_in).astype(np.float32)
    b_tail = b[:, n:]
    result = np.concatenate([crossfade, b_tail], axis=1)

    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.98

    return result

def mix_two_tracks(
    a: np.ndarray,
    b: np.ndarray,
    sr: int,
    a_exit_sample: int,
    b_entry_sample: int,
    crossfade_seconds: float = 16.0,
    lead_in_seconds: float = 10.0,
    tail_seconds: float = 15.0,
) -> np.ndarray:
    """Mezcla dos canciones completas produciendo: lead-in de A + crossfade + tail de B.

    a, b: buffers estereo (2, n) ya alineados en BPM.
    a_exit_sample: indice en 'a' donde empieza el crossfade (debe ser un downbeat).
    b_entry_sample: indice en 'b' donde empieza el crossfade (debe ser un downbeat).
    crossfade_seconds: duracion del crossfade con bass swap.
    lead_in_seconds: cuanto de A suena solo antes del crossfade.
    tail_seconds: cuanto de B suena solo despues del crossfade.

    La clave: la region de lead-in de A tambien pasa por el EQ sumado,
    para que no haya discontinuidad de amplitud al entrar al crossfade.
    """
    cf_n = int(crossfade_seconds * sr)
    lead_n = int(lead_in_seconds * sr)
    tail_n = int(tail_seconds * sr)

    # --- Recortar A: lead_in + crossfade, terminando en a_exit_sample + cf_n ---
    a_start = max(0, a_exit_sample - lead_n)
    a_end = a_exit_sample + cf_n
    if a_end > a.shape[1]:
        raise ValueError(
            f"A no tiene suficiente audio despues del exit point. "
            f"Se necesitan {cf_n} samples pero hay {a.shape[1] - a_exit_sample}"
        )
    a_slice = a[:, a_start:a_end]  # shape: (2, lead_n + cf_n) aprox

    # Ajustar lead_n real si a_start se recorto al inicio
    real_lead_n = a_exit_sample - a_start

    # Si tail_n == 0 estamos en transicion intermedia de un set: dejamos TODO
    # el resto de b disponible para que la siguiente transicion pueda tomar
    # su lead-in y exit point desde ahi.
    if tail_n == 0:
        b_slice = b[:, b_entry_sample:]
    else:
        b_end = b_entry_sample + cf_n + tail_n
        if b_end > b.shape[1]:
            b_end = b.shape[1]
        b_slice = b[:, b_entry_sample:b_end]

    if b_slice.shape[1] < cf_n:
        raise ValueError(
            f"B no tiene suficiente audio desde entry point. "
            f"Se necesitan al menos {cf_n} samples pero hay {b_slice.shape[1]}"
        )

    # --- Construir curvas de ganancia sobre el total real_lead_n + cf_n ---
    total_a = real_lead_n + cf_n

    # --- Curvas de transicion ---
    # A muere del todo antes de que termine el crossfade para evitar que su cola
    # residual siga sonando de fondo. El ultimo ~30% del crossfade es solo B.

    idx = np.linspace(0, 1, cf_n, dtype=np.float32)

    # Highs de A: cae linealmente pero llega a 0 al 70% del crossfade
    # Highs de B: entra normal desde el principio
    highs_out_cf = np.clip(1.0 - idx / 0.7, 0.0, 1.0).astype(np.float32)
    highs_in_cf = np.sin(idx * np.pi / 2)

    # Mids (voces): A cae fuerte al 40%, B entra desde el 40%.
    # Pequeno solape que rellena el hueco sin chocar voces.
    mids_out_cf = np.clip(1.0 - idx / 0.4, 0.0, 1.0).astype(np.float32)
    mids_in_cf = np.clip((idx - 0.4) / 0.5, 0.0, 1.0).astype(np.float32)

    # Lows (bombo y bajo): bass swap clasico en el medio
    swap_sharpness = 12.0
    x = np.linspace(-1, 1, cf_n, dtype=np.float32)
    sigmoid = 1.0 / (1.0 + np.exp(swap_sharpness * x))
    lows_out_cf = sigmoid
    lows_in_cf = 1.0 - sigmoid

    # Durante el lead-in, A esta a volumen pleno en todas las bandas
    ones_lead = np.ones(real_lead_n, dtype=np.float32)
    a_lows_gain = np.concatenate([ones_lead, lows_out_cf])
    a_mids_gain = np.concatenate([ones_lead, mids_out_cf])
    a_highs_gain = np.concatenate([ones_lead, highs_out_cf])

    # --- Separar A en 3 bandas y aplicar las curvas ---
    a_lows = apply_eq_3band(a_slice, sr, low_gain=1.0, mid_gain=0.0, high_gain=0.0)
    a_mids = apply_eq_3band(a_slice, sr, low_gain=0.0, mid_gain=1.0, high_gain=0.0)
    a_highs = apply_eq_3band(a_slice, sr, low_gain=0.0, mid_gain=0.0, high_gain=1.0)
    a_mix = a_lows * a_lows_gain + a_mids * a_mids_gain + a_highs * a_highs_gain

    # --- Separar la zona de crossfade de B y aplicar curvas ---
    b_cf = b_slice[:, :cf_n]
    b_cf_lows = apply_eq_3band(b_cf, sr, low_gain=1.0, mid_gain=0.0, high_gain=0.0)
    b_cf_mids = apply_eq_3band(b_cf, sr, low_gain=0.0, mid_gain=1.0, high_gain=0.0)
    b_cf_highs = apply_eq_3band(b_cf, sr, low_gain=0.0, mid_gain=0.0, high_gain=1.0)
    b_cf_mix = (
        b_cf_lows * lows_in_cf
        + b_cf_mids * mids_in_cf
        + b_cf_highs * highs_in_cf
    )

    # --- Combinar: lead-in de A (solo) + (a_mix_crossfade + b_cf_mix) + tail de B ---
    # La parte de lead-in ya esta en a_mix, solo hay que sumarle b_cf_mix en los ultimos cf_n
    result_head = a_mix.copy()
    result_head[:, real_lead_n:] += b_cf_mix

    # Tail de B: desde cf_n en adelante
    b_tail = b_slice[:, cf_n:]

    result = np.concatenate([result_head, b_tail], axis=1)

    # Proteccion contra clipping
    peak = float(np.max(np.abs(result)))
    if peak > 1.0:
        result = result / peak * 0.98

    return result.astype(np.float32)