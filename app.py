import json
import re
import secrets
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from config.settings import (
    BASE_DIR,
    INPUT_DIR,
    KEEP_ORIGINAL_AUDIO,
    OUTPUT_DIR,
    STORE_NAME,
    STORE_URL,
    STUDIO_PIN,
    TTS_PROVIDER,
    WHATSAPP_NUMBER,
)
from services.pipeline_service import process_single_video

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}
ALLOWED_MEDIA_FILES = {"video_final.mp4", "voiceover.mp3", "copys.txt"}
MAX_FILES_PER_JOB = 3

app = FastAPI(
    title=f"{STORE_NAME} — Video Studio API",
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def verify_studio_pin(
    x_studio_pin: str | None = Header(default=None),
    pin: str | None = Query(default=None),
) -> None:
    expected = STUDIO_PIN.strip()
    if not expected:
        return

    provided = (x_studio_pin or pin or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="PIN inválido o faltante.")


def _parse_legacy_copys(copys_path: Path) -> dict[str, str]:
    text = copys_path.read_text(encoding="utf-8")

    def _extract(section_prefix: str) -> str:
        pattern = (
            rf"={10,}\n{re.escape(section_prefix)}[^\n]*\n={10,}\n"
            r"(.*?)(?=\n={10,}\n|\Z)"
        )
        match = re.search(pattern, text, flags=re.DOTALL)
        return match.group(1).strip() if match else ""

    return {
        "descripcion_tiktok": _extract("TIKTOK"),
        "descripcion_reels": _extract("META BUSINESS SUITE"),
        "guion_audio": _extract("GUION DE AUDIO LOCUTADO"),
        "visual_report": _extract("REPORTE VISUAL DETECTADO"),
    }


def _update_job_file(
    job_id: str,
    index: int,
    **fields: Any,
) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["files"][index].update(fields)


def _run_job(
    job_id: str,
    file_entries: list[dict[str, Any]],
    extra_context: str,
    keep_original_audio: bool,
    upload_dir: Path,
) -> None:
    with _JOBS_LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["status"] = "processing"

    has_failures = False

    try:
        for idx, entry in enumerate(file_entries):
            video_path = Path(entry["temp_path"])
            _update_job_file(
                job_id,
                idx,
                status="processing",
                stage="starting",
                detail="Iniciando procesamiento...",
            )

            def on_progress(stage: str, detail: str, file_idx: int = idx) -> None:
                _update_job_file(job_id, file_idx, stage=stage, detail=detail)

            try:
                result = process_single_video(
                    video_path=video_path,
                    extra_context=extra_context,
                    keep_original_audio=keep_original_audio,
                    archive_input=False,
                    ensure_unique_slug=True,
                    progress_cb=on_progress,
                )
                _update_job_file(
                    job_id,
                    idx,
                    status="completed",
                    stage="done",
                    detail=f"Listo en {result['elapsed_seconds']}s",
                    result=result,
                )
            except Exception as exc:
                has_failures = True
                _update_job_file(
                    job_id,
                    idx,
                    status="failed",
                    stage="error",
                    detail=str(exc),
                    error=str(exc),
                )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)
        with _JOBS_LOCK:
            if job_id in _JOBS:
                all_failed = all(
                    f["status"] == "failed" for f in _JOBS[job_id]["files"]
                )
                _JOBS[job_id]["status"] = (
                    "failed"
                    if all_failed
                    else ("completed_with_errors" if has_failures else "completed")
                )
                _JOBS[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "store_name": STORE_NAME,
            "store_url": STORE_URL,
            "whatsapp_number": WHATSAPP_NUMBER,
            "tts_provider": TTS_PROVIDER,
            "pin_required": bool(STUDIO_PIN.strip()),
        },
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "tts_provider": TTS_PROVIDER}


@app.post("/api/auth", dependencies=[Depends(verify_studio_pin)])
def check_auth() -> dict[str, bool]:
    return {"authenticated": True}


@app.post("/api/process", dependencies=[Depends(verify_studio_pin)])
async def process_videos(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    extra_context: str = Form(default=""),
    keep_original_audio: bool = Form(default=KEEP_ORIGINAL_AUDIO),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos 1 video.")
    if len(files) > MAX_FILES_PER_JOB:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_FILES_PER_JOB} videos por lote.",
        )

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex[:12]
    upload_dir = INPUT_DIR / "uploads" / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_entries: list[dict[str, Any]] = []
    try:
        for idx, upload in enumerate(files):
            original_name = Path(upload.filename or f"video_{idx + 1}.mp4").name
            ext = Path(original_name).suffix.lower()
            if ext not in ALLOWED_VIDEO_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Formato no permitido en '{original_name}'. "
                        "Usa .mp4, .mov o .mkv."
                    ),
                )

            safe_target = upload_dir / f"{idx + 1}_{original_name}"
            with safe_target.open("wb") as out_f:
                while chunk := await upload.read(1024 * 1024):
                    out_f.write(chunk)

            file_entries.append(
                {
                    "filename": original_name,
                    "temp_path": str(safe_target),
                    "status": "queued",
                    "stage": "queued",
                    "detail": "En cola...",
                    "result": None,
                    "error": None,
                }
            )
    except Exception:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise

    job_record = {
        "job_id": job_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "extra_context": extra_context.strip(),
        "keep_original_audio": keep_original_audio,
        "files": [
            {k: v for k, v in entry.items() if k != "temp_path"}
            for entry in file_entries
        ],
    }

    with _JOBS_LOCK:
        _JOBS[job_id] = job_record

    background_tasks.add_task(
        _run_job,
        job_id,
        file_entries,
        extra_context,
        keep_original_audio,
        upload_dir,
    )

    return job_record


@app.get("/api/jobs/{job_id}", dependencies=[Depends(verify_studio_pin)])
def get_job_status(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        return json.loads(json.dumps(job))


@app.get("/api/history", dependencies=[Depends(verify_studio_pin)])
def get_history() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []

    for entry in OUTPUT_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        result_json = entry / "result.json"
        final_video = entry / "video_final.mp4"
        copys_file = entry / "copys.txt"

        if result_json.exists():
            try:
                data = json.loads(result_json.read_text(encoding="utf-8"))
                data.setdefault("slug", entry.name)
                data["has_video"] = final_video.exists()
                items.append(data)
                continue
            except Exception:
                pass

        if final_video.exists():
            parsed = _parse_legacy_copys(copys_file) if copys_file.exists() else {}
            mtime = datetime.fromtimestamp(
                final_video.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            items.append(
                {
                    "slug": entry.name,
                    "source_filename": f"{entry.name}.mp4",
                    "created_at": mtime,
                    "video_duration": None,
                    "audio_duration": None,
                    "elapsed_seconds": None,
                    "extra_context": "",
                    "keep_original_audio": KEEP_ORIGINAL_AUDIO,
                    "tts_provider": TTS_PROVIDER,
                    "guion_audio": parsed.get("guion_audio", ""),
                    "descripcion_tiktok": parsed.get("descripcion_tiktok", ""),
                    "descripcion_reels": parsed.get("descripcion_reels", ""),
                    "visual_report": parsed.get("visual_report", ""),
                    "video_file": "video_final.mp4",
                    "audio_file": "voiceover.mp3",
                    "copys_file": "copys.txt",
                    "has_video": True,
                }
            )

    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return {"items": items}


@app.get("/api/media/{slug}/{filename}", dependencies=[Depends(verify_studio_pin)])
def serve_media(
    slug: str,
    filename: str,
    download: bool = Query(default=False),
) -> FileResponse:
    if "/" in slug or "\\" in slug or ".." in slug:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    if filename not in ALLOWED_MEDIA_FILES:
        raise HTTPException(status_code=404, detail="Archivo no permitido.")

    target = (OUTPUT_DIR / slug / filename).resolve()
    if not target.is_relative_to(OUTPUT_DIR.resolve()) or not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    media_type = (
        "video/mp4"
        if filename.endswith(".mp4")
        else ("audio/mpeg" if filename.endswith(".mp3") else "text/plain; charset=utf-8")
    )
    headers = {}
    if download:
        download_name = f"{slug}_{filename}"
        headers["Content-Disposition"] = f'attachment; filename="{download_name}"'

    return FileResponse(path=target, media_type=media_type, headers=headers)


@app.delete("/api/cleanup", dependencies=[Depends(verify_studio_pin)])
def cleanup_outputs(slug: str | None = Query(default=None)) -> dict[str, Any]:
    deleted: list[str] = []

    if slug:
        if "/" in slug or "\\" in slug or ".." in slug:
            raise HTTPException(status_code=400, detail="Slug inválido.")
        target = (OUTPUT_DIR / slug).resolve()
        if target.is_relative_to(OUTPUT_DIR.resolve()) and target.is_dir():
            shutil.rmtree(target)
            deleted.append(slug)
        return {"deleted": deleted, "count": len(deleted)}

    if OUTPUT_DIR.exists():
        for entry in OUTPUT_DIR.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if (entry / "result.json").exists() or (entry / "video_final.mp4").exists():
                shutil.rmtree(entry, ignore_errors=True)
                deleted.append(entry.name)

    uploads_dir = INPUT_DIR / "uploads"
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir, ignore_errors=True)

    return {"deleted": deleted, "count": len(deleted)}
