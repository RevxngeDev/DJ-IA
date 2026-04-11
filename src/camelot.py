"""Utilidades del Camelot Wheel para mezcla armónica entre canciones."""

# Mapeo de (key, mode) a notación Camelot.
# key: 0=C, 1=C#/Db, 2=D, 3=D#/Eb, 4=E, 5=F, 6=F#/Gb, 7=G, 8=G#/Ab, 9=A, 10=A#/Bb, 11=B
# mode: 0=minor, 1=major
KEY_TO_CAMELOT = {
    (0, 1): "8B",   (0, 0): "5A",    # C major / A minor
    (1, 1): "3B",   (1, 0): "12A",   # Db major / Bb minor
    (2, 1): "10B",  (2, 0): "7A",    # D major / B minor
    (3, 1): "5B",   (3, 0): "2A",    # Eb major / C minor
    (4, 1): "12B",  (4, 0): "9A",    # E major / Db minor
    (5, 1): "7B",   (5, 0): "4A",    # F major / D minor
    (6, 1): "2B",   (6, 0): "11A",   # Gb major / Eb minor
    (7, 1): "9B",   (7, 0): "6A",    # G major / E minor
    (8, 1): "4B",   (8, 0): "1A",    # Ab major / F minor
    (9, 1): "11B",  (9, 0): "8A",    # A major / Gb minor
    (10, 1): "6B",  (10, 0): "3A",   # Bb major / G minor
    (11, 1): "1B",  (11, 0): "10A",  # B major / Ab minor
}


def to_camelot(key: int, mode: int) -> str:
    """Convierte (key, mode) en notación Camelot. Devuelve 'Unknown' si no se reconoce."""
    return KEY_TO_CAMELOT.get((key, mode), "Unknown")


def compatible_camelots(camelot: str) -> list[str]:
    """Devuelve la lista de Camelots compatibles para mezcla armónica.

    Reglas clásicas de DJ:
    - Misma key (mezcla perfecta)
    - +1 en el número (subida energética)
    - -1 en el número (bajada energética)
    - Cambio de letra, mismo número (cambio de modo mayor/menor)
    """
    if camelot == "Unknown":
        return []

    num = int(camelot[:-1])
    letter = camelot[-1]
    other_letter = "A" if letter == "B" else "B"

    plus_one = ((num % 12) + 1)
    minus_one = ((num - 2) % 12) + 1

    return [
        camelot,                        # misma key
        f"{plus_one}{letter}",          # +1
        f"{minus_one}{letter}",         # -1
        f"{num}{other_letter}",         # cambio de modo
    ]