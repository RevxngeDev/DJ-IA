"""Limpia los tags de la biblioteca: quita sufijos de sitios de descarga,
normaliza espacios y arregla mayusculas raras.

Solo modifica los campos title, artist y album EN LA BASE DE DATOS.
NO toca los archivos MP3 originales (los tags ID3 quedan intactos).
"""
import re
import sqlite3

from src.database import get_conn

# Patrones de basura que aparecen en titulos de sitios de descarga
GARBAGE_PATTERNS = [
    r"\s*-\s*MusicLife\d*\.[Cc][Oo][Mm]\s*$",
    r"\s*-\s*musiclife\d*\.com\s*$",
    r"\s*\(\s*www\.[^\)]+\)\s*",
    r"\s*-\s*www\.[^\s]+\s*$",
    r"\s*\[\s*www\.[^\]]+\]\s*",
    r"\s*-\s*MP3XD\s*$",
    r"\s*-\s*Descargar\s*$",
    r"\s*\(?Official\s*(Music\s*)?Video\)?\s*$",
    r"\s*\(?Audio\s*Oficial\)?\s*$",
    r"\s*\(?Lyric\s*Video\)?\s*$",
]


def clean_string(s: str) -> str:
    """Aplica todos los patrones de limpieza a un string."""
    if not s:
        return s
    cleaned = s
    for pattern in GARBAGE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)
    # Normalizar espacios multiples
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Quitar guiones colgantes al final
    cleaned = re.sub(r"\s*-\s*$", "", cleaned).strip()
    return cleaned


def main():
    print("=== Limpieza de tags ===\n")

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, artist, album FROM tracks"
        ).fetchall()

        changed = 0
        examples = []

        for row in rows:
            old_title = row["title"]
            old_artist = row["artist"]
            old_album = row["album"]

            new_title = clean_string(old_title) if old_title else old_title
            new_artist = clean_string(old_artist) if old_artist else old_artist
            new_album = clean_string(old_album) if old_album else old_album

            if (new_title, new_artist, new_album) != (old_title, old_artist, old_album):
                conn.execute(
                    "UPDATE tracks SET title = ?, artist = ?, album = ? WHERE id = ?",
                    (new_title, new_artist, new_album, row["id"]),
                )
                changed += 1
                if len(examples) < 10:
                    examples.append((old_title, new_title))

        conn.commit()

    print(f"Tracks revisados: {len(rows)}")
    print(f"Tracks limpiados: {changed}\n")

    if examples:
        print("Ejemplos de cambios:")
        for old, new in examples:
            print(f"  ANTES: {old}")
            print(f"  AHORA: {new}\n")

    print("Listo. Recarga la app de Streamlit (F5) para ver los cambios.")


if __name__ == "__main__":
    main()