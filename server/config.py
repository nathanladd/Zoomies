from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media" / "questions"

DB_FILENAME = "zundpunkt.db"
DB_PATH = DATA_DIR / DB_FILENAME
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

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
