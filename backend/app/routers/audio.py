"""Audio upload: transcribe and format as meeting notes or conversation summary."""
import asyncio
import logging
import time
import uuid
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.audio_notes import process_audio_to_notes

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job status for async progress (job_id -> { stage, transcript?, formatted?, error?, created_at })
_audio_jobs: dict[str, dict] = {}
_JOB_EXPIRE_SEC = 3600  # 1 hour


def _cleanup_old_jobs() -> None:
    now = time.time()
    to_del = [jid for jid, j in _audio_jobs.items() if (now - j.get("created_at", 0)) > _JOB_EXPIRE_SEC]
    for jid in to_del:
        del _audio_jobs[jid]


@router.post("/audio/process")
async def process_audio(
    file: UploadFile = File(...),
    instruction: str = Form(""),
    user_id: str = Form("default"),
    whisper_model: str = Form("base"),
    async_mode: str = Form("0"),
):
    """Upload an audio file; transcribe and format. If async_mode=1, returns 202 with job_id; poll GET /audio/status/{job_id} for progress."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file.")
    if async_mode.strip() == "1":
        job_id = str(uuid.uuid4())
        _audio_jobs[job_id] = {"stage": "transcribing", "created_at": time.time()}

        async def on_progress(stage: str) -> None:
            _audio_jobs[job_id]["stage"] = stage

        async def run_job() -> None:
            try:
                result = await process_audio_to_notes(
                    data, file.filename, instruction, user_id,
                    whisper_model=whisper_model,
                    progress_callback=on_progress,
                )
                _audio_jobs[job_id]["stage"] = "done"
                _audio_jobs[job_id]["transcript"] = result.get("transcript", "")
                _audio_jobs[job_id]["formatted"] = result.get("formatted", "")
            except Exception as e:
                logger.exception("Audio job %s failed: %s", job_id, e)
                _audio_jobs[job_id]["stage"] = "error"
                _audio_jobs[job_id]["error"] = str(e)[:500]

        asyncio.create_task(run_job())
        _cleanup_old_jobs()
        return JSONResponse(content={"job_id": job_id}, status_code=202)
    try:
        return await process_audio_to_notes(data, file.filename, instruction, user_id, whisper_model=whisper_model)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/audio/status/{job_id}")
async def audio_status(job_id: str):
    """Poll for async audio job progress. Returns { stage: 'transcribing'|'formatting'|'done'|'error', transcript?, formatted?, error? }."""
    _cleanup_old_jobs()
    if job_id not in _audio_jobs:
        raise HTTPException(404, "Job not found or expired.")
    j = _audio_jobs[job_id]
    out = {"stage": j.get("stage", "transcribing")}
    if "transcript" in j:
        out["transcript"] = j["transcript"]
    if "formatted" in j:
        out["formatted"] = j["formatted"]
    if "error" in j:
        out["error"] = j["error"]
    return out
