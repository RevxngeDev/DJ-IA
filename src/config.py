"""Configuracion centralizada del DJ IA.

Todos los parametros ajustables del sistema estan aqui. Modificar este archivo
cambia el comportamiento sin tocar el resto del codigo.
"""

# =============================================================================
# AUDIO Y SAMPLE RATE
# =============================================================================
DEFAULT_SR = 44100  # Hz, sample rate de procesamiento (calidad CD)


# =============================================================================
# SELECTOR IA (selector.py)
# =============================================================================
# Tolerancia de BPM para considerar dos canciones compatibles (+- ratio)
BPM_TOLERANCE = 0.06  # 6%

# Pesos para el score del selector
ENERGY_WEIGHT = 2.0
BPM_WEIGHT = 1.5
CAMELOT_PERFECT_BONUS = 3.0
CAMELOT_OK_PENALTY = 1.5
SAME_ALBUM_PENALTY = 1.0
STAGNATION_PENALTY = 4.0  # penaliza repetir misma key 2+ veces seguidas
ARTIST_DIVERSITY_BONUS = 0.5

# Curva de energia del set
ENERGY_PEAK_POSITION_DEFAULT = 0.65  # donde cae el pico (0.0 - 1.0)
ENERGY_MIN = 0.45  # energia al inicio
ENERGY_MAX = 0.95  # energia en el pico
ENERGY_END = 0.55  # energia al final


# =============================================================================
# MOTOR DE MEZCLA (mixer.py, transition.py)
# =============================================================================
# Duraciones por defecto (segundos)
CROSSFADE_SECONDS_DEFAULT = 10.0
LEAD_IN_SECONDS_DEFAULT = 12.0
TAIL_SECONDS_DEFAULT = 12.0

# Puntos de transicion
EXIT_BARS_BEFORE_END = 8   # downbeats antes del final donde sacar A
ENTRY_BARS_FROM_START = 16  # downbeats despues del inicio donde entrar B

# EQ de 3 bandas (Hz)
EQ_LOW_CUT = 250.0   # frontera entre lows y mids
EQ_HIGH_CUT = 4000.0  # frontera entre mids y highs

# Curvas de transicion (bass swap y voces)
BASS_SWAP_SHARPNESS = 12.0  # mayor = swap mas brusco
HIGHS_OUT_FADE_FRACTION = 0.7  # los highs de A llegan a 0 al 70% del crossfade
MIDS_OUT_FADE_FRACTION = 0.4   # los mids de A caen al 40% del crossfade
MIDS_IN_START_FRACTION = 0.4   # los mids de B empiezan a entrar al 40%
MIDS_IN_RAMP_FRACTION = 0.5    # tardan otro 50% en llegar a full

# Time-stretch limits (rubberband)
MAX_STRETCH_RATIO = 1.08  # +8%
MIN_STRETCH_RATIO = 0.92  # -8%

# Tempo folding (analyzer.py)
TARGET_BPM_CENTER = 95.0   # centro musical del reggaeton
BPM_VALID_MIN = 75.0       # rango aceptable de BPM
BPM_VALID_MAX = 130.0


# =============================================================================
# LOUDNESS (loudness.py)
# =============================================================================
TARGET_LUFS = -14.0        # estandar Spotify/YouTube
MAX_GAIN_DB = 6.0          # nunca subimos/bajamos mas de esto


# =============================================================================
# LIMITER (limiter.py)
# =============================================================================
LIMITER_THRESHOLD_DB = -1.0
LIMITER_LOOKAHEAD_MS = 5.0
LIMITER_RELEASE_MS = 50.0


# =============================================================================
# CACHE (audio_cache.py)
# =============================================================================
from pathlib import Path
CACHE_DIR = Path("data/audio_cache")