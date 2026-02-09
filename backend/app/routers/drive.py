"""Google Drive: OAuth and list (stub: returns placeholder until OAuth wired)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/drive/status")
async def drive_status():
    """Whether Drive is connected and summary."""
    # TODO: read stored token, list recent files
    return {"connected": False, "summary": "Connect Google Drive in Settings."}


@router.get("/drive/list")
async def drive_list():
    """List recent Drive files (when connected)."""
    return {"files": [], "connected": False}
