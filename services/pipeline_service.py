import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agents.copy_agent import generate_marketing_copy
from agents.vision_agent import analyze_video_content
from config.settings import (
    INPUT_DIR,
    KEEP_ORIGINAL_AUDIO,
    OUTPUT_DIR,
    TTS_PROVIDER,
)
from services.tts_service import generate_voiceover
from services.video_service import get_media_duration, merge_video_with_voiceover

ProgressCallback = Callable[[str, str], None]


def slugify(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip())
    return clean.strip("_")[:60] or "video_producto"


def _resolve_output_dir(base_slug: str, ensure_unique: bool) -> tuple[str, Path]:
    candidate_slug = base_slug
    candidate_dir = OUTPUT_DIR / candidate_slug

    if ensure_unique and candidate_dir.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate_slug = f"{base_slug[:44]}_{stamp}"
        candidate_dir = OUTPUT_DIR / candidate_slug
        counter = 1
        while candidate_dir.exists():
            candidate_slug = f"{base_slug[:40]}_{stamp}_{counter}"
            candidate_dir = OUTPUT_DIR / candidate_slug
            counter += 1

    return candidate_slug, candidate_dir


def process_single_video(
    video_path: Path,
    extra_context: str = "",
    keep_original_audio: bool = KEEP_ORIGINAL_AUDIO,
    archive_input: bool = False,
    ensure_unique_slug: bool = False,
    progress_cb: ProgressCallback | None = None,
) -> dict[str, Any]:
    """
    Orquesta el flujo completo para un video:
    duración -> visión Gemini -> copywriting CrewAI -> voz TTS -> ensamblado FFmpeg -> archivos de salida.
    """
    def notify(stage: str, detail: str) -> None:
        if progress_cb is not None:
            progress_cb(stage, detail)

    t0 = time.perf_counter()
    path = Path(video_path)
    slug, product_out_dir = _resolve_output_dir(
        slugify(path.stem),
        ensure_unique=ensure_unique_slug,
    )
    product_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 65}")
    print(f"PROCESANDO: {path.name}")
    print(f"{'=' * 65}")

    # 1. Medir duración exacta del video original
    notify("duration", "Midiendo duración del video...")
    video_duration = get_media_duration(path)
    print(f"-> Duración detectada: {video_duration:.2f} segundos")

    # 2. Agente de Visión (Gemini File API con proxy 480p)
    notify("vision", "Analizando video con Gemini Vision...")
    visual_report = analyze_video_content(path)
    if extra_context.strip():
        visual_report += f"\n\n5. DATOS ADICIONALES DE TIENDA:\n{extra_context.strip()}"

    # 3. Agente Copywriter (CrewAI + validación Pydantic)
    notify("copy", "Redactando guion y copys para TikTok / Reels...")
    print("-> Redactando guion de audio y copys para TikTok / Reels...")
    marketing = generate_marketing_copy(visual_report, video_duration)

    # 4. Síntesis de voz (TTS Provider configurado)
    notify("tts", f"Generando voz en off ({TTS_PROVIDER})...")
    audio_path = product_out_dir / "voiceover.mp3"
    audio_duration = generate_voiceover(marketing.guion_audio, audio_path)
    print(f"-> Locución generada: {audio_duration:.2f} segundos ({audio_path.name})")

    # 5. Ensamblado final con FFmpeg
    notify("ffmpeg", "Ensamblando video final con FFmpeg...")
    final_video_path = product_out_dir / "video_final.mp4"
    merge_video_with_voiceover(
        video_path=path,
        audio_path=audio_path,
        output_video_path=final_video_path,
        keep_original_audio=keep_original_audio,
    )

    # 6. Guardar copys listos para copiar y pegar + result.json estructurado
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

    elapsed = time.perf_counter() - t0
    result_data: dict[str, Any] = {
        "slug": slug,
        "source_filename": path.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_duration": round(video_duration, 2),
        "audio_duration": round(audio_duration, 2),
        "elapsed_seconds": round(elapsed, 2),
        "extra_context": extra_context.strip(),
        "keep_original_audio": keep_original_audio,
        "tts_provider": TTS_PROVIDER,
        "guion_audio": marketing.guion_audio,
        "descripcion_tiktok": marketing.descripcion_tiktok,
        "descripcion_reels": marketing.descripcion_reels,
        "visual_report": visual_report,
        "video_file": final_video_path.name,
        "audio_file": audio_path.name,
        "copys_file": copys_path.name,
    }

    result_json_path = product_out_dir / "result.json"
    result_json_path.write_text(
        json.dumps(result_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if archive_input:
        processed_dir = INPUT_DIR / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(processed_dir / path.name))

    notify("done", f"Completado en {elapsed:.1f}s")
    print(f"\n[LISTO en {elapsed:.1f}s]")
    print(f"  Video final : {final_video_path}")
    print(f"  Copys       : {copys_path}")
    print(f"  Metadata    : {result_json_path}")

    return result_data
