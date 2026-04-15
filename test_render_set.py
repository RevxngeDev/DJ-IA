"""Genera un set completo mezclado desde una setlist de Fase 2."""
from src.selector import generate_setlist, print_setlist
from src.mixer import render_set

# 1. Generar setlist (20 minutos para que la prueba no tarde una eternidad)
print("Generando setlist...")
setlist = generate_setlist(duration_minutes=20)
print_setlist(setlist)

# 2. Renderizar el set completo en un MP3
output = "my_first_dj_set.mp3"
render_set(
    setlist=setlist,
    output_path=output,
    crossfade_seconds=10.0,
    lead_in_seconds=12.0,
    tail_seconds=12.0,
)
print(f"\nArchivo generado: {output}")
print("Reproducelo en cualquier reproductor y disfruta tu primer set mezclado!")