import os
import secrets
from typing import Optional
from pydantic_settings import BaseSettings
from pathlib import Path
from dotenv import load_dotenv

backend_dir = Path(__file__).resolve().parent.parent.parent
root_dir = backend_dir.parent
load_dotenv(root_dir / ".env")
load_dotenv(backend_dir / ".env", override=True)
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI7 Finance API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/ai7_finance"
    )
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN", "")
    ALLOWED_USER_ID: int = int(os.getenv("ALLOWED_USER_ID", "0"))
    
    # Web App URL
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8080")

    # Timezone
    TIMEZONE: str = "Asia/Jakarta"

    # Google Sheets Integration
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials_google.json")
    GOOGLE_SHEETS_SPREADSHEET_ID: Optional[str] = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") or None

    # AI Media Extraction (OCR & Voice Notes via 9router)
    AI_ROUTER_URL: str = os.getenv("AI_ROUTER_URL", "http://127.0.0.1:20128/v1")
    AI_ROUTER_KEY: str = os.getenv("AI_ROUTER_KEY", "")
    AI_ROUTER_MODEL: str = os.getenv("AI_ROUTER_MODEL", "ag/gemini-3.8-flash")

    # JWT Authentication - Loaded securely from environment or auto-generated cryptographically
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "") or secrets.token_hex(32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days (10080 minutes)

    # Bot Token Symmetric Encryption Key (Fernet) - Falls back to JWT_SECRET_KEY
    BOT_TOKEN_ENCRYPTION_KEY: Optional[str] = os.getenv("BOT_TOKEN_ENCRYPTION_KEY", None)

    # Google OAuth Sign-In (Web)
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID", None)

    class Config:
        case_sensitive = True

settings = Settings()
