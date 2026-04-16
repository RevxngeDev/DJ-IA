"""SetRenderer: clase que orquesta la generacion de un set mezclado completo."""
import numpy as np

from src.audio_cache import load_audio_cached as load_audio
from src.audio_utils import save_audio, DEFAULT_SR
from src.beat_align import (
    calculate_stretch_ratio,
    time_stretch_track,
    find_exit_point,
    find_entry_point,
    seconds_to_samples,
)
from src.loudness import normalize_cached
from src.limiter import soft_limiter
from src.transition import mix_two_tracks
from src.config import (
    CROSSFADE_SECONDS_DEFAULT,
    LEAD_IN_SECONDS_DEFAULT,
    TAIL_SECONDS_DEFAULT,
    EXIT_BARS_BEFORE_END,
    ENTRY_BARS_FROM_START,
    LIMITER_THRESHOLD_DB,
)


class SetRenderer:
    """Toma una setlist y genera un audio continuo mezclado."""

    def __init__(
        self,
        setlist: list[dict],
        crossfade_seconds: float = CROSSFADE_SECONDS_DEFAULT,
        lead_in_seconds: float = LEAD_IN_SECONDS_DEFAULT,
        tail_seconds: float = TAIL_SECONDS_DEFAULT,
        verbose: bool = True,
        progress_callback=None,
    ):
        if len(setlist) < 2:
            raise ValueError("La setlist necesita al menos 2 canciones")

        self.setlist = setlist
        self.crossfade_seconds = crossfade_seconds
        self.lead_in_seconds = lead_in_seconds
        self.tail_seconds = tail_seconds
        self.verbose = verbose
        self.progress_callback = progress_callback

        # Se llenan durante el render
        self.sr = DEFAULT_SR
        self.audios = []
        self.target_bpms = []
        self.exit_samples = []
        self.entry_samples = []

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def _progress(self, stage: str, current: int, total: int, message: str):
        if self.progress_callback:
            self.progress_callback(
                stage=stage, current=current, total=total, message=message,
            )

    # -----------------------------------------------------------------
    # Paso 1: calcular BPMs objetivo
    # -----------------------------------------------------------------
    def _compute_target_bpms(self):
        self.target_bpms = []
        for i, track in enumerate(self.setlist):
            if i == 0:
                self.target_bpms.append(track["bpm"])
            else:
                prev = self.target_bpms[i - 1]
                self.target_bpms.append((prev + track["bpm"]) / 2.0)

    # -----------------------------------------------------------------
    # Paso 2: cargar audios, normalizar y stretchear
    # -----------------------------------------------------------------
    def _load_and_prepare(self):
        self.audios = []
        n = len(self.setlist)

        for i, track in enumerate(self.setlist):
            self._log(f"[{i+1}/{n}] Cargando: {track['title'][:45]}")
            self._progress("loading", i + 1, n, f"Cargando: {track['title']}")

            y, sr = load_audio(track["filepath"])
            self.sr = sr

            # Normalizar loudness
            y = normalize_cached(track["filepath"], y, sr)

            # Time-stretch
            ratio = calculate_stretch_ratio(track["bpm"], self.target_bpms[i])
            if abs(ratio - 1.0) > 0.001:
                self._log(
                    f"         stretch: {ratio:.4f} "
                    f"({track['bpm']:.1f} -> {self.target_bpms[i]:.1f} BPM)"
                )
                y = time_stretch_track(y, sr, ratio)

            self.audios.append(y)

    # -----------------------------------------------------------------
    # Paso 3: calcular puntos de exit y entry
    # -----------------------------------------------------------------
    def _compute_points(self):
        self.exit_samples = []
        self.entry_samples = []

        for i, track in enumerate(self.setlist):
            ratio_used = self.target_bpms[i] / track["bpm"]
            exit_t = find_exit_point(track, EXIT_BARS_BEFORE_END) / ratio_used
            entry_t = find_entry_point(track, ENTRY_BARS_FROM_START) / ratio_used
            self.exit_samples.append(seconds_to_samples(exit_t, self.sr))
            self.entry_samples.append(seconds_to_samples(entry_t, self.sr))

    # -----------------------------------------------------------------
    # Paso 4: aplicar una transicion individual
    # -----------------------------------------------------------------
    def _apply_transition(
        self,
        current: np.ndarray,
        i: int,
        last_track_origin: int,
    ) -> tuple[np.ndarray, list[np.ndarray], int]:
        """Aplica la transicion entre track i e i+1.

        Retorna (nuevo_current_tail, partes_preservadas, nuevo_last_track_origin).
        """
        n_transitions = len(self.setlist) - 1
        is_last = (i == n_transitions - 1)

        self._log(
            f"Transicion {i+1}: "
            f"{self.setlist[i]['title'][:30]} -> {self.setlist[i+1]['title'][:30]}"
        )
        self._progress(
            "mixing", i + 1, n_transitions,
            f"Transición {i+1}/{n_transitions}",
        )

        # Exit del track i dentro de current
        a_exit_in_current = last_track_origin + self.exit_samples[i]

        # Validaciones de seguridad
        cf_samples = int(self.crossfade_seconds * self.sr)
        if a_exit_in_current >= current.shape[1]:
            a_exit_in_current = current.shape[1] - cf_samples - self.sr
        if a_exit_in_current < 0:
            a_exit_in_current = int(current.shape[1] * 0.8)

        b_entry = self.entry_samples[i + 1]
        lead_in = self.lead_in_seconds if i == 0 else 0.0
        tail = self.tail_seconds if is_last else 0.0

        # Preservar la parte antes del exit (menos el lead-in)
        lead_n_samples = int(lead_in * self.sr)
        preserve_end = a_exit_in_current - lead_n_samples
        preserved = []

        if preserve_end > 0:
            preserved.append(current[:, :preserve_end])
            current_trimmed = current[:, preserve_end:]
            a_exit_trimmed = a_exit_in_current - preserve_end
        else:
            current_trimmed = current
            a_exit_trimmed = a_exit_in_current

        mixed = mix_two_tracks(
            a=current_trimmed,
            b=self.audios[i + 1],
            sr=self.sr,
            a_exit_sample=a_exit_trimmed,
            b_entry_sample=b_entry,
            crossfade_seconds=self.crossfade_seconds,
            lead_in_seconds=lead_in,
            tail_seconds=tail,
        )

        new_origin = a_exit_in_current - b_entry

        return mixed, preserved, new_origin

    # -----------------------------------------------------------------
    # Paso 5: orquestar todo
    # -----------------------------------------------------------------
    def render(self, output_path: str):
        """Genera el set completo y lo guarda como archivo de audio."""
        n = len(self.setlist)
        self._log(f"\n=== Renderizando set de {n} tracks ===\n")

        # Preparacion
        self._compute_target_bpms()
        self._load_and_prepare()
        self._compute_points()

        self._log(f"\n=== Aplicando transiciones ===\n")

        # Mezcla incremental
        preserved_parts = []
        current_tail = self.audios[0]
        last_track_origin = 0

        for i in range(n - 1):
            mixed, preserved, new_origin = self._apply_transition(
                current_tail, i, last_track_origin,
            )

            preserved_parts.extend(preserved)

            if i == n - 2:
                # Ultima transicion: mixed incluye el tail, todo va a preserved
                preserved_parts.append(mixed)
                current_tail = None
            else:
                current_tail = mixed
                last_track_origin = new_origin

            total_so_far = sum(p.shape[1] for p in preserved_parts)
            if current_tail is not None:
                total_so_far += current_tail.shape[1]
            self._log(f"             largo acumulado: {total_so_far / self.sr:.1f}s")

        # Concatenar
        final = np.concatenate(preserved_parts, axis=1)

        # Limiter final
        self._log("\nAplicando limiter final...")
        self._progress("saving", 1, 1, "Aplicando limiter y guardando...")
        final = soft_limiter(final, self.sr, threshold_db=LIMITER_THRESHOLD_DB)

        total_min = final.shape[1] / self.sr / 60
        self._log(f"=== Set final: {total_min:.1f} minutos ===")
        self._log(f"Guardando en {output_path}...")
        save_audio(output_path, final, self.sr)
        self._log("Listo.")