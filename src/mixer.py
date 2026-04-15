"""Motor de mezcla: encadena una setlist en un solo audio continuo."""
from pathlib import Path

import numpy as np

from src.audio_utils import load_audio, save_audio
from src.beat_align import (
    calculate_stretch_ratio,
    time_stretch_track,
    find_exit_point,
    find_entry_point,
    seconds_to_samples,
)
from src.transition import mix_two_tracks


def render_set(
    setlist: list[dict],
    output_path: str,
    crossfade_seconds: float = 10.0,
    lead_in_seconds: float = 12.0,
    tail_seconds: float = 12.0,
    verbose: bool = True,
    progress_callback=None,
) -> None:
    """Toma una setlist de Fase 2 y genera un audio continuo mezclado.

    Estrategia: render incremental. Cada nueva cancion se mezcla solo con la
    "cola" del acumulado (desde el exit point hacia adelante), preservando
    intacto todo el audio anterior.
    """
    if len(setlist) < 2:
        raise ValueError("La setlist necesita al menos 2 canciones")

    if verbose:
        print(f"\n=== Renderizando set de {len(setlist)} tracks ===\n")

    # --- Paso 1: calcular BPMs objetivo (curva suave) ---
    target_bpms = []
    for i, track in enumerate(setlist):
        natural_bpm = track["bpm"]
        if i == 0:
            target_bpms.append(natural_bpm)
        else:
            prev_target = target_bpms[i - 1]
            target_bpms.append((prev_target + natural_bpm) / 2.0)

    # --- Paso 2: cargar y stretchear cada audio ---
    sr = None
    audios = []
    for i, track in enumerate(setlist):
        if verbose:
            print(f"[{i+1}/{len(setlist)}] Cargando: {track['title'][:45]}")
            if progress_callback:
                progress_callback(
                stage="loading",
                current=i + 1,
                total=len(setlist),
                message=f"Cargando: {track['title']}",
            )
        y, file_sr = load_audio(track["filepath"])
        if sr is None:
            sr = file_sr
        ratio = calculate_stretch_ratio(track["bpm"], target_bpms[i])
        if abs(ratio - 1.0) > 0.001:
            if verbose:
                print(f"         stretch ratio: {ratio:.4f} "
                      f"({track['bpm']:.1f} -> {target_bpms[i]:.1f} BPM)")
            y = time_stretch_track(y, sr, ratio)
        audios.append(y)

    # --- Paso 3: calcular exit y entry points (en audio stretched) ---
    exit_samples = []
    entry_samples = []
    for i, track in enumerate(setlist):
        ratio_used = target_bpms[i] / track["bpm"]
        exit_t = find_exit_point(track, bars_before_end=8) / ratio_used
        entry_t = find_entry_point(track, bars_from_start=16) / ratio_used
        exit_samples.append(seconds_to_samples(exit_t, sr))
        entry_samples.append(seconds_to_samples(entry_t, sr))

    # --- Paso 4: construir el set incrementalmente ---
    if verbose:
        print(f"\n=== Aplicando transiciones ===\n")

    # Empezamos con audios[0] desde el principio hasta su exit_sample.
    # Despues, cada iteracion:
    #   - Toma el ultimo track previo desde su entry (o principio, si es el primero)
    #     hasta su exit, y lo mezcla con el siguiente.
    #   - El resultado se concatena al "cuerpo acumulado".

    # preserved: la parte del set ya resuelta (que no se va a tocar mas)
    # current_tail: la "cola activa" que va a mezclarse con el siguiente track.
    # En la primera iteracion, current_tail = audios[0] completo.

    # Para el primer track, "lo preservado" es vacio y current_tail es audios[0]
    preserved_parts = []
    current_tail = audios[0]
    current_tail_exit = exit_samples[0]  # exit point dentro de current_tail

    for i in range(len(setlist) - 1):
        if verbose:
            print(f"Transicion {i+1}: {setlist[i]['title'][:30]} -> {setlist[i+1]['title'][:30]}")
            if progress_callback:
                progress_callback(
                stage="mixing",
                current=i + 1,
                total=len(setlist) - 1,
                message=f"Transición {i+1}/{len(setlist)-1}",
            )

        b_entry = entry_samples[i + 1]
        is_last = (i == len(setlist) - 2)

        # Lead-in: para la primera transicion, queremos que suene desde el principio
        # del primer track (o con un lead-in de lead_in_seconds antes del exit).
        # Para transiciones intermedias, el "lead-in" ya esta implicito en current_tail
        # (que contiene todo desde el entry del ultimo track hasta su exit), asi que
        # no agregamos mas lead-in aqui.
        if i == 0:
            lead_in = lead_in_seconds
        else:
            # La parte previa al exit de current_tail ya es el "lead-in" natural
            # desde el entry del track anterior. Solo le damos 0 de lead-in adicional
            # porque mix_two_tracks empezara a procesar desde current_tail_exit.
            lead_in = 0.0

        current_tail_tail = tail_seconds if is_last else 0.0

        # Antes de mezclar, preservamos la parte de current_tail ANTES del exit
        # menos el lead-in (que mix_two_tracks va a procesar).
        lead_n_samples = int(lead_in * sr)
        preserve_end = current_tail_exit - lead_n_samples
        if preserve_end > 0:
            preserved_parts.append(current_tail[:, :preserve_end])
            # Recortamos current_tail para que mix_two_tracks solo procese desde ahi
            current_tail_trimmed = current_tail[:, preserve_end:]
            a_exit_trimmed = current_tail_exit - preserve_end
        else:
            current_tail_trimmed = current_tail
            a_exit_trimmed = current_tail_exit

        mixed = mix_two_tracks(
            a=current_tail_trimmed,
            b=audios[i + 1],
            sr=sr,
            a_exit_sample=a_exit_trimmed,
            b_entry_sample=b_entry,
            crossfade_seconds=crossfade_seconds,
            lead_in_seconds=lead_in,
            tail_seconds=current_tail_tail,
        )

        if is_last:
            # Ultima transicion: mixed ya incluye el tail final, lo preservamos todo
            preserved_parts.append(mixed)
            current_tail = None
        else:
            # Transicion intermedia: mixed contiene (lead_in + crossfade + resto_de_b).
            # "Resto de b" arranca en el sample (a_exit_trimmed + cf_n) dentro de mixed,
            # que corresponde al sample (b_entry + cf_n) de audios[i+1].
            # De eso, lo que esta antes del proximo exit lo vamos a preservar en la
            # siguiente iteracion; por ahora todo esto es el nuevo current_tail.
            current_tail = mixed
            # El proximo exit dentro del nuevo current_tail:
            # mixed[:a_exit_trimmed + cf_n] corresponde a (final del crossfade).
            # Desde ahi, audios[i+1] continua desde b_entry + cf_n.
            # El exit de audios[i+1] esta en exit_samples[i+1] (coord de audios[i+1]).
            # Dentro de mixed esta en: (a_exit_trimmed + cf_n) + (exit_samples[i+1] - (b_entry + cf_n))
            #                       = a_exit_trimmed + exit_samples[i+1] - b_entry
            cf_samples = int(crossfade_seconds * sr)
            current_tail_exit = a_exit_trimmed + exit_samples[i + 1] - b_entry

            # Validacion de seguridad
            if current_tail_exit >= current_tail.shape[1]:
                if verbose:
                    print(f"  AVISO: exit recalculado fuera de rango, usando final - crossfade")
                current_tail_exit = current_tail.shape[1] - cf_samples - sr  # 1s de margen

        total_so_far = sum(p.shape[1] for p in preserved_parts)
        if current_tail is not None:
            total_so_far += current_tail.shape[1]
        if verbose:
            print(f"             largo acumulado total: {total_so_far / sr:.1f}s")

    # --- Paso 5: concatenar y guardar ---
    final = np.concatenate(preserved_parts, axis=1)

    total_min = final.shape[1] / sr / 60
    if verbose:
        print(f"\n=== Set final: {total_min:.1f} minutos ===")
        print(f"Guardando en {output_path}...")
        if progress_callback:
            progress_callback(
            stage="saving",
            current=1,
            total=1,
            message="Guardando MP3...",
        ) 
    save_audio(output_path, final, sr)
    if verbose:
        print("Listo.")