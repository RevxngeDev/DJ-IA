"""Prueba los helpers de audio con una cancion real."""
import numpy as np
from src.audio_utils import load_audio, save_audio, apply_fade, apply_eq_3band
from src.database import get_conn

# Toma una cancion cualquiera de la DB
with get_conn() as conn:
    row = conn.execute("SELECT filepath, title FROM tracks LIMIT 1").fetchone()

filepath = row["filepath"]
title = row["title"]
print(f"Probando con: {title}")
print(f"Ruta: {filepath}\n")

# 1. Cargar
print("1. Cargando audio...")
y, sr = load_audio(filepath)
print(f"   Shape: {y.shape}, SR: {sr}, dtype: {y.dtype}")
print(f"   Duracion: {y.shape[1] / sr:.1f} segundos")
print(f"   Rango: [{y.min():.3f}, {y.max():.3f}]")

# 2. Tomar los primeros 10 segundos para probar
segment = y[:, :sr * 10]
print(f"\n2. Segmento de prueba: 10 segundos ({segment.shape[1]} samples)")

# 3. Aplicar fade in de 2 segundos y fade out de 2 segundos
print("\n3. Aplicando fades (2s in, 2s out)...")
with_fade = apply_fade(segment, fade_in_samples=sr * 2, fade_out_samples=sr * 2)

# 4. Guardar como WAV para verificar que se puede reproducir
save_audio("test_output_fade.wav", with_fade, sr)
print("   Guardado: test_output_fade.wav")

# 5. Aplicar bass kill (graves a 0)
print("\n4. Aplicando bass kill (graves a 0)...")
no_bass = apply_eq_3band(segment, sr, low_gain=0.0, mid_gain=1.0, high_gain=1.0)
save_audio("test_output_no_bass.wav", no_bass, sr)
print("   Guardado: test_output_no_bass.wav")

# 6. Aplicar high kill (solo graves y medios)
print("\n5. Aplicando solo graves (highs=0, mids=0)...")
only_bass = apply_eq_3band(segment, sr, low_gain=1.0, mid_gain=0.0, high_gain=0.0)
save_audio("test_output_only_bass.wav", only_bass, sr)
print("   Guardado: test_output_only_bass.wav")

print("\nListo. Reproduce los 3 archivos .wav y escucha las diferencias:")
print("  - test_output_fade.wav       -> original con fades")
print("  - test_output_no_bass.wav    -> sin graves (voz y agudos)")
print("  - test_output_only_bass.wav  -> solo graves (sub bajo)")