import argparse
import re
import shutil
import time
from pathlib import Path

from config.settings import INPUT_DIR, OUTPUT_DIR, STORE_NAME, KEEP_ORIGINAL_AUDIO
from agents.vision_agent import analyze_video_content
from agents.copy_agent import generate_marketing_copy
from services.tts_service import generate_voiceover
from services.video_service import get_media_duration, merge_video_with_voiceover


def _slugify(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip())
    return clean.strip("_")[:60] or "video_producto"


def process_single_video(
    video_path: Path,
    extra_context: str = "",
    keep_original_audio: bool = KEEP_ORIGINAL_AUDIO,
    archive_input: bool = False,
) -> None:
    t0 = time.perf_counter()
    slug = _slugify(video_path.stem)
    product_out_dir = OUTPUT_DIR / slug
    product_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 65}")
    print(f"PROCESANDO: {video_path.name}")
    print(f"{'=' * 65}")

    # 1. Medir duración exacta del video original
    video_duration = get_media_duration(video_path)
    print(f"-> Duración detectada: {video_duration:.2f} segundos")

    # 2. Agente de Visión (Gemini File API con proxy 480p)
    visual_report = analyze_video_content(video_path)
    if extra_context.strip():
        visual_report += f"\n\n5. DATOS ADICIONALES DE TIENDA:\n{extra_context.strip()}"

    # 3. Agente Copywriter (Ollama local llama3.1:8b + validación Pydantic)
    print("-> Redactando guion de audio y copys para TikTok / Reels...")
    marketing = generate_marketing_copy(visual_report, video_duration)

    # 4. Síntesis de voz (edge-tts)
    audio_path = product_out_dir / "voiceover.mp3"
    audio_duration = generate_voiceover(marketing.guion_audio, audio_path)
    print(f"-> Locución generada: {audio_duration:.2f} segundos ({audio_path.name})")

    # 5. Ensamblado final con FFmpeg
    final_video_path = product_out_dir / "video_final.mp4"
    merge_video_with_voiceover(
        video_path=video_path,
        audio_path=audio_path,
        output_video_path=final_video_path,
        keep_original_audio=keep_original_audio,
    )

    # 6. Guardar copys listos para copiar y pegar
    copys_path = product_out_dir / "copys.txt"
    copys_text = (
        f"====================================================\n"
        f"TIKTOK (Máximo 5 hashtags)\n"
        f"====================================================\n"
        f"{marketing.descripcion_tiktok}\n\n"
        f"====================================================\n"
        f"META BUSINESS SUITE - REELS (Facebook / Instagram)\n"
        f"====================================================\n"
        f"{marketing.descripcion_reels}\n\n"
        f"====================================================\n"
        f"GUION DE AUDIO LOCUTADO ({audio_duration:.1f}s)\n"
        f"====================================================\n"
        f"{marketing.guion_audio}\n\n"
        f"====================================================\n"
        f"REPORTE VISUAL DETECTADO\n"
        f"====================================================\n"
        f"{visual_report}\n"
    )
    copys_path.write_text(copys_text, encoding="utf-8")

    if archive_input:
        processed_dir = INPUT_DIR / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(video_path), str(processed_dir / video_path.name))

    elapsed = time.perf_counter() - t0
    print(f"\n[LISTO en {elapsed:.1f}s]")
    print(f"  Video final : {final_video_path}")
    print(f"  Copys       : {copys_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Automatización de videos y copys para {STORE_NAME}"
    )
    parser.add_argument(
        "--context",
        type=str,
        default="",
        help="Dato extra opcional para los videos del lote (ej. 'Precio: 350 Bs, garantía 3 meses')",
    )
    parser.add_argument(
        "--mute-original",
        action="store_true",
        help="Silencia el audio original del video (útil si tiene locución en chino en vez de música)",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Mueve los videos originales procesados a media/input/processed/",
    )
    args = parser.parse_args()

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = sorted(
        p for p in INPUT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv"}
    )

    if not videos:
        print(f"No hay videos en '{INPUT_DIR}'. Coloca tus archivos .mp4 ahí y vuelve a ejecutar.")
        return

    print(f"Se encontraron {len(videos)} video(s) en cola para {STORE_NAME}.")
    for video in videos:
        try:
            process_single_video(
                video_path=video,
                extra_context=args.context,
                keep_original_audio=(not args.mute_original) and KEEP_ORIGINAL_AUDIO,
                archive_input=args.archive,
            )
        except Exception as err:
            print(f"\n[ERROR] Falló el procesamiento de '{video.name}': {err}")


if __name__ == "__main__":
    main()
