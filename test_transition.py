"""Prueba la transicion DJ completa entre dos canciones (v2)."""
from src.database import get_conn
from src.beat_align import (
    calculate_stretch_ratio,
    time_stretch_track,
    find_exit_point,
    find_entry_point,
    seconds_to_samples,
)
from src.audio_utils import load_audio, save_audio
from src.transition import mix_two_tracks

CROSSFADE_SECONDS = 10.0
LEAD_IN_SECONDS = 10.0
TAIL_SECONDS = 15.0

# Elegimos 2 canciones compatibles
with get_conn() as conn:
    rows = conn.execute(
        "SELECT * FROM tracks WHERE bpm BETWEEN 90 AND 100 "
        "ORDER BY bpm LIMIT 2"
    ).fetchall()

a_track = dict(rows[0])
b_track = dict(rows[1])
print(f"Saliente (A): {a_track['title']} - {a_track['bpm']:.1f} BPM - {a_track['camelot']}")
print(f"Entrante (B): {b_track['title']} - {b_track['bpm']:.1f} BPM - {b_track['camelot']}")
print()

# Puntos de transicion en segundos
exit_t = find_exit_point(a_track, bars_before_end=8)
entry_t = find_entry_point(b_track, bars_from_start=16)
print(f"A exit point: {exit_t:.2f}s")
print(f"B entry point: {entry_t:.2f}s")
print()

# Cargar audio
print("Cargando audio...")
a_audio, sr = load_audio(a_track["filepath"])
b_audio, _ = load_audio(b_track["filepath"])

# Stretch de B para igualar BPM de A
ratio = calculate_stretch_ratio(b_track["bpm"], a_track["bpm"])
print(f"Aplicando stretch a B: ratio={ratio:.4f}")
b_stretched = time_stretch_track(b_audio, sr, ratio)

# Ajustar el entry point al nuevo tempo
entry_t_new = entry_t / ratio

# Convertir a samples
a_exit_sample = seconds_to_samples(exit_t, sr)
b_entry_sample = seconds_to_samples(entry_t_new, sr)

# Mezclar
print("Mezclando con bass swap...")
mix = mix_two_tracks(
    a_audio, b_stretched, sr,
    a_exit_sample=a_exit_sample,
    b_entry_sample=b_entry_sample,
    crossfade_seconds=CROSSFADE_SECONDS,
    lead_in_seconds=LEAD_IN_SECONDS,
    tail_seconds=TAIL_SECONDS,
)
print(f"Resultado: {mix.shape[1] / sr:.1f} segundos")

save_audio("test_transition.wav", mix, sr)
print("\nGuardado: test_transition.wav")
print(f"\nEstructura:")
print(f"  0:00 -> {LEAD_IN_SECONDS:.0f}s    Lead-in de A a volumen pleno")
print(f"  {LEAD_IN_SECONDS:.0f}s -> {LEAD_IN_SECONDS + CROSSFADE_SECONDS:.0f}s  Crossfade con bass swap")
print(f"  {LEAD_IN_SECONDS + CROSSFADE_SECONDS:.0f}s -> fin   Tail de B")