"""Genera un set completo mezclado desde una setlist de Fase 2."""
import time

from src.selector import generate_setlist
from src.mixer import render_set

print("Generando setlist...")
setlist = generate_setlist(duration_minutes=20)

output = "my_first_dj_set.mp3"
start = time.time()
render_set(
    setlist=setlist,
    output_path=output,
    crossfade_seconds=10.0,
    lead_in_seconds=12.0,
    tail_seconds=12.0,
)
elapsed = time.time() - start
print(f"\nTiempo total: {elapsed:.1f} segundos ({elapsed / 60:.2f} min)")