"""Admin endpoints for database backup and restore.

Uses SQLite's online backup API so the DB can be copied while the server is
running. The media/questions/ directory is zipped alongside the DB so that
question images stay in sync with the question rows that reference them.
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from server.config import (
    BACKUPS_DIR, BASE_DIR, DATA_DIR, DB_FILENAME, DB_PATH, MEDIA_DIR,
    USER_DATA_DIR,
)
from server.schemas import BackupResult, RestoreRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _online_sqlite_backup(src: Path, dst: Path) -> None:
    """Copy a SQLite DB using the online backup API (safe while in use)."""
    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


@router.post("/backup", response_model=BackupResult)
async def create_backup(path: str | None = None) -> BackupResult:
    """Create a zip backup of the DB and media/questions/ directory.

    If `path` is provided it is used as the output zip path (created /
    overwritten). Otherwise the zip is written under `<project>/backups/` with
    a timestamped name.
    """
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if path:
        out_zip = Path(path)
        out_zip.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_zip = BACKUPS_DIR / f"zundpunkt-{stamp}.zip"

    # Copy the DB via the online backup API into a temp file first so we zip
    # a consistent snapshot even if writes happen during the zip.
    with tempfile.TemporaryDirectory() as td:
        tmp_db = Path(td) / DB_FILENAME
        try:
            _online_sqlite_backup(DB_PATH, tmp_db)
        except sqlite3.Error as e:
            raise HTTPException(500, f"SQLite backup failed: {e}")

        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_db, arcname=f"data/{DB_FILENAME}")
            # Instructor-editable settings (scoring curve, etc.)
            scoring_json = DATA_DIR / "scoring.json"
            if scoring_json.is_file():
                zf.write(scoring_json, arcname="data/scoring.json")
            if MEDIA_DIR.exists():
                for p in MEDIA_DIR.rglob("*"):
                    if p.is_file():
                        arc = Path("media/questions") / p.relative_to(MEDIA_DIR)
                        zf.write(p, arcname=str(arc).replace("\\", "/"))

    return BackupResult(
        path=str(out_zip),
        size_bytes=out_zip.stat().st_size,
        created_at=datetime.now(timezone.utc),
    )


@router.post("/restore")
async def restore_backup(body: RestoreRequest) -> dict[str, str]:
    """Restore the DB and media/questions/ from a zip created by /backup.

    Current DB and media directory are moved aside to
    `data/pre-restore-<stamp>/` before being overwritten, so the previous
    state is recoverable if something goes wrong.

    The caller must restart the server process afterwards — the open
    SQLAlchemy engine will not pick up the replaced file automatically.
    """
    zip_path = Path(body.path)
    if not zip_path.is_file():
        raise HTTPException(404, f"Backup zip not found: {zip_path}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safety_dir = DATA_DIR / f"pre-restore-{stamp}"
    safety_dir.mkdir(parents=True, exist_ok=True)

    # Move current DB and media aside
    if DB_PATH.exists():
        shutil.move(str(DB_PATH), str(safety_dir / DB_FILENAME))
    if MEDIA_DIR.exists():
        shutil.move(str(MEDIA_DIR), str(safety_dir / "questions"))
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    # Extract into the user-writable data root (holds data/ and media/questions/).
    # Validate every entry resolves under USER_DATA_DIR before extracting so a
    # maliciously crafted zip can't escape with "..\..\foo" paths (Zip-Slip).
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            root = USER_DATA_DIR.resolve()
            for info in zf.infolist():
                # Reject absolute paths and drive letters outright.
                name = info.filename
                if name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
                    raise HTTPException(400, f"Unsafe path in backup: {name}")
                target = (root / name).resolve()
                try:
                    target.relative_to(root)
                except ValueError:
                    raise HTTPException(400, f"Unsafe path in backup: {name}")
            zf.extractall(USER_DATA_DIR)
    except zipfile.BadZipFile as e:
        # Roll back the safety move
        if (safety_dir / DB_FILENAME).exists():
            shutil.move(str(safety_dir / DB_FILENAME), str(DB_PATH))
        if (safety_dir / "questions").exists():
            if MEDIA_DIR.exists():
                shutil.rmtree(MEDIA_DIR)
            shutil.move(str(safety_dir / "questions"), str(MEDIA_DIR))
        raise HTTPException(400, f"Invalid backup archive: {e}")

    return {
        "status": "ok",
        "restored_from": str(zip_path),
        "previous_state": str(safety_dir),
        "notice": "Restart the server for the restored database to take effect.",
    }
