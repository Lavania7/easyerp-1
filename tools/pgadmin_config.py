"""Project-specific pgAdmin desktop configuration; installation remains untouched."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_MODE = False
DATA_DIR = str(ROOT / "var" / "pgadmin")
DEFAULT_SERVER = "127.0.0.1"
DEFAULT_SERVER_PORT = 8093
SESSION_COOKIE_NAME = "easyerp_pgadmin_session"
CHECK_FOR_UPDATES = False
LLM_ENABLED = False
# Keep native master-password and operating-system secret-storage defaults.
