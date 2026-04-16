"""Motor de mezcla (wrapper de compatibilidad).

La logica real esta en src/renderer.py (clase SetRenderer).
Este modulo mantiene la funcion render_set() para que los scripts
y la app de Streamlit sigan funcionando sin cambios.
"""
from src.renderer import SetRenderer


def render_set(
    setlist: list[dict],
    output_path: str,
    crossfade_seconds: float = 10.0,
    lead_in_seconds: float = 12.0,
    tail_seconds: float = 12.0,
    verbose: bool = True,
    progress_callback=None,
) -> None:
    """Genera un set mezclado. Wrapper sobre SetRenderer."""
    renderer = SetRenderer(
        setlist=setlist,
        crossfade_seconds=crossfade_seconds,
        lead_in_seconds=lead_in_seconds,
        tail_seconds=tail_seconds,
        verbose=verbose,
        progress_callback=progress_callback,
    )
    renderer.render(output_path)