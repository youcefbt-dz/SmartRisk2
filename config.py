"""إعدادات التطبيق. تُضبط بمتغيرات البيئة (انظر .env.example) دون تعديل الكود."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = Path(os.environ.get("SMARTRISK_INSTANCE", BASE_DIR / "instance"))


def _secret_key() -> str:
    env = os.environ.get("SMARTRISK_SECRET_KEY")
    if env:
        return env
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    f = INSTANCE_DIR / "secret.key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text().strip()


def _flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = _secret_key()
    DATABASE = os.environ.get("SMARTRISK_DB", str(INSTANCE_DIR / "smartrisk.db"))
    # false = وضع مستخدم واحد محلي بلا تسجيل دخول (مناسب للعرض الأكاديمي على جهاز واحد)
    AUTH_REQUIRED = _flag("SMARTRISK_AUTH", True)
    ALLOW_REGISTRATION = _flag("SMARTRISK_ALLOW_REGISTRATION", True)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    MAX_PROJECTS_PER_USER = int(os.environ.get("SMARTRISK_MAX_PROJECTS", 50))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _flag("SMARTRISK_HTTPS", False)
    JSON_AS_ASCII = False
    TESTING = False
