"""Prueba la alineacion de beats con dos canciones reales de la DB."""
from src.database import get_conn
from src.beat_align import (
    calculate_stretch_ratio,
    time_stretch_track,
    find_exit_point,
    find_entry_point,
)
from src.audio_utils import load_audio, save_audio

# Tomamos dos canciones con BPM distintos para forzar un stretch
with get_conn() as conn:
    rows = conn.execute(
        "SELECT * FROM tracks WHERE bpm BETWEEN 90 AND 100 ORDER BY bpm LIMIT 2"
    ).fetchall()

t1 = dict(rows[0])
t2 = dict(rows[1])

print(f"Track 1: {t1['title']} - {t1['bpm']:.1f} BPM")
print(f"Track 2: {t2['title']} - {t2['bpm']:.1f} BPM")
print()

# 1. Calcular el ratio necesario para llevar t2 al BPM de t1
ratio = calculate_stretch_ratio(t2["bpm"], t1["bpm"])
print(f"Ratio para alinear t2 -> t1: {ratio:.4f}")
print(f"  (t2 sonara a {t2['bpm'] * ratio:.1f} BPM despues del stretch)")
print()

# 2. Puntos de transicion
exit_t = find_exit_point(t1, bars_before_end=16)
entry_t = find_entry_point(t2, bars_from_start=16)
print(f"Exit point de t1: {exit_t:.2f}s (de {t1['duration']:.1f}s total)")
print(f"Entry point de t2: {entry_t:.2f}s (de {t2['duration']:.1f}s total)")
print()

# 3. Cargar t2, aplicarle el stretch y guardar 15 segundos desde el entry point
print("Cargando t2 y aplicando stretch...")
y, sr = load_audio(t2["filepath"])
y_stretched = time_stretch_track(y, sr, ratio)
print(f"  Original:  {y.shape[1]} samples")
print(f"  Stretched: {y_stretched.shape[1]} samples")

# Nota: el entry_point original en segundos hay que ajustarlo al stretch
entry_t_stretched = entry_t / ratio
start_sample = int(entry_t_stretched * sr)
segment = y_stretched[:, start_sample : start_sample + sr * 15]

save_audio("test_stretched_entry.wav", segment, sr)
print(f"\nGuardado: test_stretched_entry.wav")
print("Reproducelo y deberias oir t2 entrando desde un downbeat, con su nuevo tempo.")