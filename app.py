"""DJ IA Latino - Interfaz web con Streamlit."""
from pathlib import Path

import pandas as pd
import streamlit as st

from src.database import get_conn
from src.selector import generate_setlist
from src.mixer import render_set

# --- Configuracion ---
st.set_page_config(
    page_title="DJ IA Latino",
    page_icon="🎧",
    layout="wide",
)

st.title("🎧 DJ IA Latino")
st.caption("Tu DJ personal con IA para música latina")

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# --- Cargar biblioteca ---
@st.cache_data(ttl=60)
def load_library():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, artist, album, bpm, camelot, energy, "
            "danceability, duration FROM tracks ORDER BY artist, title"
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


library = load_library()

# --- Sidebar ---
st.sidebar.header("🎛️ Controles del DJ")

duration_min = st.sidebar.slider(
    "Duración del set (minutos)", 10, 90, 30, 5
)

peak_position = st.sidebar.slider(
    "Posición del pico de energía", 0.3, 0.9, 0.65, 0.05,
    help="0.65 = el momento más intenso cae al 65% del set.",
)

seed_option = st.sidebar.radio(
    "Canción de inicio", ["Aleatoria (energía baja)", "Elegir yo"],
)

seed_id = None
if seed_option == "Elegir yo":
    options = {f"{row['title']} — {row['artist']}": row["id"]
               for _, row in library.iterrows()}
    selected_label = st.sidebar.selectbox("Canción semilla", list(options.keys()))
    seed_id = options[selected_label]

generate_btn = st.sidebar.button(
    "🎵 Generar setlist", type="primary", use_container_width=True
)

st.sidebar.divider()
st.sidebar.subheader("⚙️ Opciones de mezcla")
crossfade_sec = st.sidebar.slider("Duración crossfade (seg)", 4, 20, 10)

# --- Resumen biblioteca ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Tracks", len(library))
col2.metric("BPM promedio", f"{library['bpm'].mean():.1f}")
col3.metric("Artistas", library["artist"].nunique())
col4.metric("Duración total", f"{library['duration'].sum() / 3600:.1f} h")

st.divider()

# --- Estado persistente ---
if "setlist" not in st.session_state:
    st.session_state.setlist = None
if "mix_path" not in st.session_state:
    st.session_state.mix_path = None

# --- Generar setlist ---
if generate_btn:
    with st.spinner("El DJ está pensando..."):
        try:
            st.session_state.setlist = generate_setlist(
                duration_minutes=duration_min,
                seed_track_id=seed_id,
                peak_position=peak_position,
            )
            st.session_state.mix_path = None  # invalida el mix anterior
        except Exception as e:
            st.error(f"Error generando el set: {e}")
            st.session_state.setlist = None

# --- Mostrar setlist ---
if st.session_state.setlist:
    setlist = st.session_state.setlist

    st.subheader("🎶 Setlist generado")

    rows = []
    for i, t in enumerate(setlist, 1):
        dur_min = int(t["duration"] // 60)
        dur_sec = int(t["duration"] % 60)
        rows.append({
            "#": i,
            "Título": t["title"],
            "Artista": t["artist"] or "?",
            "BPM": f"{t['bpm']:.1f}",
            "Key": t["camelot"],
            "Energía": f"{t['energy']:.2f}",
            "Duración": f"{dur_min}:{dur_sec:02d}",
            "Transición": t.get("reason", ""),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True,
                 hide_index=True, height=400)

    total_sec = sum(t["duration"] for t in setlist)
    avg_bpm = sum(t["bpm"] for t in setlist) / len(setlist)
    peak_energy = max(t["energy"] for t in setlist)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tracks", len(setlist))
    m2.metric("Duración", f"{total_sec / 60:.1f} min")
    m3.metric("BPM promedio", f"{avg_bpm:.1f}")
    m4.metric("Pico energía", f"{peak_energy:.2f}")

    # Curva de energia (solo si hay al menos 2 tracks con datos validos)
    if len(setlist) >= 2:
        energy_df = pd.DataFrame({
            "Track #": list(range(1, len(setlist) + 1)),
            "Energía": [float(t["energy"]) for t in setlist],
            "BPM": [float(t["bpm"]) for t in setlist],
        }).set_index("Track #")
        st.line_chart(energy_df)

    st.divider()

    # --- Render del mix ---
    st.subheader("🎚️ Mezclar el set")

    mix_col1, mix_col2 = st.columns([2, 3])
    with mix_col1:
        render_btn = st.button(
            "🎛️ Renderizar mix", type="primary", use_container_width=True
        )
        st.caption(f"Tarda ~{len(setlist) * 25}s aproximadamente")

    if render_btn:
        output_path = OUTPUT_DIR / f"dj_set_{duration_min}min.mp3"

    with st.status("🎛️ Renderizando mix...", expanded=True) as status_box:
        def on_progress(stage, current, total, message):
            status_box.update(label=f"🎛️ {message}")
            st.write(f"• {message}")

        try:
            render_set(
                setlist=setlist,
                output_path=str(output_path),
                crossfade_seconds=crossfade_sec,
                lead_in_seconds=12.0,
                tail_seconds=12.0,
                verbose=False,
                progress_callback=on_progress,
            )
            status_box.update(label="✅ ¡Mix listo!", state="complete", expanded=False)
            st.session_state.mix_path = str(output_path)
        except Exception as e:
            status_box.update(label=f"❌ Error: {e}", state="error")
            st.exception(e)

    # --- Reproductor y descarga ---
    if st.session_state.mix_path and Path(st.session_state.mix_path).exists():
        st.divider()
        st.subheader("▶️ Reproductor")

        mix_file = Path(st.session_state.mix_path)
        size_mb = mix_file.stat().st_size / (1024 * 1024)

        audio_bytes = mix_file.read_bytes()
        st.audio(audio_bytes, format="audio/mp3")

        dl_col1, dl_col2 = st.columns([1, 3])
        with dl_col1:
            st.download_button(
                label="⬇️ Descargar MP3",
                data=audio_bytes,
                file_name=mix_file.name,
                mime="audio/mp3",
                use_container_width=True,
            )
        with dl_col2:
            st.caption(f"📁 {mix_file.name} • {size_mb:.1f} MB")

else:
    st.info("👈 Genera un setlist primero para poder mezclarlo.")

st.divider()

with st.expander("📀 Ver toda mi biblioteca"):
    st.dataframe(
        library[["title", "artist", "bpm", "camelot", "energy", "danceability"]]
        .rename(columns={
            "title": "Título", "artist": "Artista", "bpm": "BPM",
            "camelot": "Key", "energy": "Energía", "danceability": "Bailable",
        }),
        use_container_width=True, height=400,
    )