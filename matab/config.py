"""Configuration management for ZAYVORA MATAB OS."""

import os
from pathlib import Path
from dataclasses import dataclass

BASE_DIR = Path(__file__).resolve().parent.parent

@dataclass
class AppConfig:
    env: str = os.getenv("MATAB_ENV", "development")
    profile: str = os.getenv("MATAB_PROFILE", "MATAB")  # MATAB, CLINIC, HOSPITAL
    host: str = os.getenv("MATAB_HOST", "127.0.0.1")
    port: int = int(os.getenv("MATAB_PORT", "8000"))
    db_path: str = os.getenv("MATAB_DB_PATH", str(BASE_DIR / "matab.db"))
    secret_key: str = os.getenv("MATAB_SECRET_KEY", "matab-os-standalone-secure-dev-key-2026")
    fail_closed_on_safety_unknown: bool = os.getenv("MATAB_FAIL_CLOSED", "true").lower() == "true"
    allow_synthetic_data: bool = env != "production"

    def is_production(self) -> bool:
        return self.env == "production"

config = AppConfig()
