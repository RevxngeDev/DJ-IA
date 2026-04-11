"""Escanea la carpeta de música y analiza cada archivo nuevo."""
import sys
import time
from pathlib import Path

from tqdm import tqdm

from src.database import init_db, insert_track, track_exists, count_tracks
from src.analyzer import analyze_track

# Extensiones de audio soportadas
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".wav", ".ogg"}


def scan_folder(folder: str) -> list[str]:
    """Busca recursivamente todos los archivos de audio en la carpeta."""
    files = [
        str(p)
        for p in Path(folder).rglob("*")
        if p.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files)


def main(folder: str = "music"):
    print(f"\n=== DJ IA Latino - Analizador de Biblioteca ===\n")

    # Inicializar la base de datos (crea la tabla si no existe)
    init_db()
    print(f"Base de datos lista. Tracks existentes: {count_tracks()}")

    # Escanear carpeta
    files = scan_folder(folder)
    print(f"Archivos de audio encontrados en '{folder}/': {len(files)}")

    if not files:
        print("\nNo se encontraron archivos. Asegurate de poner tus MP3s en la carpeta 'music/'.")
        print("Puede tener subcarpetas (por ejemplo music/Un Verano Sin Ti/track.mp3).")
        return

    # Filtrar los que ya fueron analizados
    new_files = [f for f in files if not track_exists(f)]
    skipped = len(files) - len(new_files)

    if skipped > 0:
        print(f"Ya analizados previamente (se omiten): {skipped}")

    if not new_files:
        print("\nTodos los archivos ya fueron analizados. Nada nuevo que procesar.")
        print(f"Total en la biblioteca: {count_tracks()} tracks")
        return

    print(f"Nuevos por analizar: {len(new_files)}")
    print(f"\nIniciando analisis (cada track tarda ~10-30 segundos)...\n")

    # Analizar cada archivo nuevo
    success = 0
    errors = 0
    start_time = time.time()

    for filepath in tqdm(new_files, desc="Analizando", unit="track"):
        try:
            data = analyze_track(filepath)
            insert_track(data)
            success += 1
        except Exception as e:
            errors += 1
            tqdm.write(f"  ERROR en {Path(filepath).name}: {e}")

    # Resumen final
    elapsed = time.time() - start_time
    print(f"\n=== Analisis completado ===")
    print(f"Exitosos: {success}")
    print(f"Errores: {errors}")
    print(f"Tiempo total: {elapsed:.1f} segundos")
    print(f"Total en la biblioteca: {count_tracks()} tracks")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "music"
    main(folder)