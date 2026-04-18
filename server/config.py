import os
import sys
from pathlib import Path

# When running as a PyInstaller-built executable, bundled read-only resources
# (static/, media/questions/ seeded, etc.) live under sys._MEIPASS while
# user-writable data is kept under %LOCALAPPDATA%\Zundpunkt so the install dir
# (typically Program Files) stays read-only as Windows expects.
IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    USER_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Zundpunkt"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    USER_DATA_DIR = BASE_DIR

DATA_DIR = USER_DATA_DIR / "data"
MEDIA_DIR = USER_DATA_DIR / "media" / "questions"
BACKUPS_DIR = USER_DATA_DIR / "backups"

DB_FILENAME = "zundpunkt.db"
DB_PATH = DATA_DIR / DB_FILENAME
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Ensure the user-writable dirs exist regardless of entry point.
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

SERVER_HOST = "0.0.0.0"
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
