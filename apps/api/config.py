"""Configuration and environment validation for ZAYVORA MATAB OS."""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Automatically load .env if present without overwriting existing environment variables
env_file = BASE_DIR / ".env"
if env_file.exists():
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                k = k.strip()
                v = v.strip()
                if v and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

DEFAULT_INSECURE_KEYS = [
    "change-this-insecure-dev-key-before-production-use-2026",
    "matab-os-standalone-secure-dev-key-2026",
    "secret",
    "dev_key",
    "password"
]

@dataclass
class AppConfig:
    env: str = os.getenv("MATAB_ENV", "development").lower()
    profile: str = os.getenv("MATAB_PROFILE", "MATAB").upper()
    host: str = os.getenv("MATAB_HOST", "0.0.0.0")
    port: int = int(os.getenv("MATAB_PORT", "8080"))
    db_path: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "matab.db"))
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'matab.db'}")
    secret_key: str = os.getenv("MATAB_SECRET_KEY", "matab-os-standalone-secure-dev-key-2026")
    session_hours: int = int(os.getenv("MATAB_SESSION_HOURS", "12"))
    auth_rate_limit_per_min: int = int(os.getenv("MATAB_AUTH_RATE_LIMIT", "10"))
    fail_closed: bool = os.getenv("MATAB_FAIL_CLOSED", "true").lower() == "true"
    allowed_origins: str = os.getenv("MATAB_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8080,http://localhost:8080")
    books_dir: str = os.getenv("MATAB_BOOKS_DIR", str(BASE_DIR / "data" / "medical_books"))

    def is_production(self) -> bool:
        return self.env == "production"

    def validate_production_readiness(self) -> List[str]:
        """Validate safety requirements for production deployment."""
        errors = []
        if self.is_production():
            if self.secret_key in DEFAULT_INSECURE_KEYS or len(self.secret_key) < 32:
                errors.append("MATAB_SECRET_KEY must be a secure, non-default string of at least 32 characters in production.")
            if "localhost" in self.database_url and "sqlite" not in self.database_url:
                errors.append("DATABASE_URL should not point to localhost in production cluster deployments.")
            if self.host == "127.0.0.1" and os.environ.get("MATAB_PROFILE") == "ENTERPRISE_CLUSTER":
                errors.append("MATAB_HOST should be configured explicitly (e.g. 0.0.0.0 in container) for cluster production.")
        return errors

config = AppConfig()

# Fail fast on startup if production configuration is explicitly unsafe
_prod_errors = config.validate_production_readiness()
if _prod_errors and config.is_production():
    raise RuntimeError(f"FATAL: Unsafe production configuration:\n" + "\n".join(_prod_errors))
