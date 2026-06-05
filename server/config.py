import os
import sys
from pathlib import Path

# When running as a PyInstaller-built executable, bundled read-only resources
# (static/, media/questions/ seeded, etc.) live under sys._MEIPASS while
# user-writable data is kept under %LOCALAPPDATA%\Rudi so the install dir
# (typically Program Files) stays read-only as Windows expects.
IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    _LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    USER_DATA_DIR = _LOCALAPPDATA / "Rudi"
    # One-time migration: if this is an upgrade from a pre-rename install,
    # the user's data is still under LOCALAPPDATA\Zundpunkt. Move the whole
    # tree over so their question bank, uploaded media, and backups follow.
    _legacy_user_dir = _LOCALAPPDATA / "Zundpunkt"
    if _legacy_user_dir.exists() and not USER_DATA_DIR.exists():
        try:
            _legacy_user_dir.rename(USER_DATA_DIR)
        except OSError:
            pass
elif sys.platform != "win32":
    # Linux / macOS server deployment: honour RUDI_DATA_DIR env var or
    # default to ~/.local/share/rudi for user-writable data.
    BASE_DIR = Path(__file__).resolve().parent.parent
    _env_data = os.environ.get("RUDI_DATA_DIR")
    USER_DATA_DIR = Path(_env_data) if _env_data else Path.home() / ".local" / "share" / "rudi"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    USER_DATA_DIR = BASE_DIR

DATA_DIR = USER_DATA_DIR / "database"
MEDIA_DIR = USER_DATA_DIR / "media" / "questions"
BACKUPS_DIR = USER_DATA_DIR / "backups"
RELEASES_DIR = USER_DATA_DIR / "releases"

DB_FILENAME = "rudi.db"
DB_PATH = DATA_DIR / DB_FILENAME

# One-time migration: rename the legacy zundpunkt.db file in place so existing
# installs keep their question bank after the rebrand. Runs in both dev and
# frozen modes since either could carry over an old DB.
_legacy_db = DATA_DIR / "zundpunkt.db"
if _legacy_db.exists() and not DB_PATH.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _legacy_db.rename(DB_PATH)
    except OSError:
        pass

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Ensure the user-writable dirs exist regardless of entry point.
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
RELEASES_DIR.mkdir(parents=True, exist_ok=True)

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_WIDTH = 1920
MAX_IMAGE_HEIGHT = 1080
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

POINTS_MAX = 1000
POINTS_MIN = 100
ELIMINATION_MARKS = (0.33, 0.66)

TIME_DEFAULT = 10
TIME_MIN = 5
TIME_MAX = 30
