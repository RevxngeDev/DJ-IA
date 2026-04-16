"""Helpers de bajo nivel para carga, guardado y procesamiento de audio."""
from pathlib import Path

import numpy as np
import soundfile as sf
from pydub import AudioSegment
from scipy.signal import butter, sosfilt


# Sample rate estándar para el mixer (calidad CD)
DEFAULT_SR = 44100


def load_audio(filepath: str, sr: int = DEFAULT_SR) -> tuple[np.ndarray, int]:
    """Carga un archivo de audio como array estereo float32.

    Retorna (y, sr) donde y tiene shape (2, n_samples) para estereo
    o (n_samples,) si el archivo es mono.

    Soporta MP3, M4A, FLAC, WAV, OGG via pydub + ffmpeg.
    """
    # pydub maneja todos los formatos via ffmpeg
    audio = AudioSegment.from_file(filepath)

    # Forzamos al sample rate deseado y a estereo
    audio = audio.set_frame_rate(sr).set_channels(2)

    # Convertir a numpy: pydub da int16 o int32, lo pasamos a float32 en rango [-1, 1]
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    max_val = float(1 << (8 * audio.sample_width - 1))
    samples = samples / max_val

    # Reshape a (n_samples, 2) y luego transponer a (2, n_samples) para trabajar por canal
    samples = samples.reshape(-1, 2).T
    return samples, sr


def save_audio(filepath: str, y: np.ndarray, sr: int = DEFAULT_SR) -> None:
    """Guarda un array como archivo de audio. Detecta formato por extension.

    y puede tener shape (n,) para mono, (2, n) para estereo, o (n, 2).
    """
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    # Normalizar shape a (n_samples, n_channels) que es lo que espera soundfile
    if y.ndim == 1:
        out = y
    elif y.shape[0] == 2 and y.shape[1] != 2:
        out = y.T  # (2, n) -> (n, 2)
    else:
        out = y

    # Clip para evitar distorsion si algo se sale de [-1, 1]
    out = np.clip(out, -1.0, 1.0)

    ext = Path(filepath).suffix.lower()

    if ext == ".wav":
        sf.write(filepath, out, sr, subtype="PCM_16")
    elif ext == ".mp3":
        # Para MP3: guardamos primero como WAV temporal y convertimos con pydub
        tmp_wav = str(Path(filepath).with_suffix(".tmp.wav"))
        sf.write(tmp_wav, out, sr, subtype="PCM_16")
        audio = AudioSegment.from_wav(tmp_wav)
        audio.export(filepath, format="mp3", bitrate="320k")
        Path(tmp_wav).unlink(missing_ok=True)
    else:
        sf.write(filepath, out, sr)


def apply_fade(y: np.ndarray, fade_in_samples: int = 0, fade_out_samples: int = 0) -> np.ndarray:
    """Aplica fade-in al inicio y fade-out al final del buffer.

    y puede ser mono (n,) o estereo (2, n).
    """
    out = y.copy()
    n = out.shape[-1]

    if fade_in_samples > 0:
        fade_in_samples = min(fade_in_samples, n)
        ramp = np.linspace(0.0, 1.0, fade_in_samples, dtype=np.float32)
        if out.ndim == 1:
            out[:fade_in_samples] *= ramp
        else:
            out[:, :fade_in_samples] *= ramp

    if fade_out_samples > 0:
        fade_out_samples = min(fade_out_samples, n)
        ramp = np.linspace(1.0, 0.0, fade_out_samples, dtype=np.float32)
        if out.ndim == 1:
            out[-fade_out_samples:] *= ramp
        else:
            out[:, -fade_out_samples:] *= ramp

    return out


def _butter_filter(y: np.ndarray, sr: int, cutoff, btype: str, order: int = 4) -> np.ndarray:
    """Aplica un filtro Butterworth (lowpass, highpass o bandpass)."""
    nyq = sr / 2
    if isinstance(cutoff, (list, tuple)):
        wn = [c / nyq for c in cutoff]
    else:
        wn = cutoff / nyq
    sos = butter(order, wn, btype=btype, output="sos")

    if y.ndim == 1:
        return sosfilt(sos, y).astype(np.float32)
    else:
        # Aplicar canal por canal
        return np.stack([sosfilt(sos, ch).astype(np.float32) for ch in y])


def apply_eq_3band(
    y: np.ndarray,
    sr: int,
    low_gain: float = 1.0,
    mid_gain: float = 1.0,
    high_gain: float = 1.0,
    low_cut: float = 250.0,
    high_cut: float = 4000.0,
) -> np.ndarray:
    """EQ de 3 bandas estilo mixer DJ.

    Separa en graves (<low_cut), medios (low_cut..high_cut) y agudos (>high_cut),
    aplica ganancias independientes y vuelve a sumar.

    Los gains son multiplicadores lineales:
    - 1.0 = banda sin cambio
    - 0.0 = banda muda (kill)
    - 0.5 = banda a la mitad (-6 dB aproximado)

    Para un "bass kill" clasico de DJ: apply_eq_3band(y, sr, low_gain=0.0).
    """
    lows = _butter_filter(y, sr, low_cut, "low")
    highs = _butter_filter(y, sr, high_cut, "high")
    mids = _butter_filter(y, sr, [low_cut, high_cut], "band")

    return (lows * low_gain + mids * mid_gain + highs * high_gain).astype(np.float32)

def split_3band(
    y: np.ndarray,
    sr: int,
    low_cut: float = 250.0,
    high_cut: float = 4000.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Separa una senal en sus 3 bandas: lows, mids, highs.

    Mas eficiente que llamar apply_eq_3band 3 veces, porque calcula los
    3 filtros una sola vez. Util cuando necesitamos las 3 bandas separadas
    para aplicar ganancias independientes despues.

    Retorna (lows, mids, highs), cada uno con la misma forma que y.
    """
    lows = _butter_filter(y, sr, low_cut, "low")
    highs = _butter_filter(y, sr, high_cut, "high")
    mids = _butter_filter(y, sr, [low_cut, high_cut], "band")
    return lows, mids, highs