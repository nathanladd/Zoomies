"""GET /api/app/latest — serves the latest instructor-app release manifest.

The server admin places a latest.json manifest and the installer EXE in
USER_DATA_DIR/releases/ when publishing a new build. The instructor app polls
this endpoint at startup and shows an update dialog if a newer version exists.

Manifest format (latest.json):
{
  "version": "2.5",
  "notes": "What's new in this release",
  "download_url": "/releases/Rudi-Setup-2.5.exe",
  "sha256": "<hex digest of the EXE>"
}
"""
import json

from fastapi import APIRouter, HTTPException

from server.config import RELEASES_DIR

router = APIRouter()


@router.get("/api/app/latest")
async def app_latest():
    manifest_path = RELEASES_DIR / "latest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="No release published yet")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manifest read error: {e}")
