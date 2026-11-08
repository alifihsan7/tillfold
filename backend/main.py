import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import engine, Base
from app.db.pocket_schema import ensure_pocket_subscription_schema
from app.db.account_schema import ensure_account_archive_schema
import app.models.transaction
import app.models.subscription
import app.models.account
import app.models.goal
import app.models.paycheck
import app.models.user
import app.models.category
import app.models.jago_pocket

# Create database tables automatically
Base.metadata.create_all(bind=engine)
ensure_account_archive_schema(engine)

def ensure_pocket_schema_compatibility():
    """Idempotently adds account_id and role columns to jago_pockets if table predates schema update."""
    from sqlalchemy import inspect, text
    try:
        inspector = inspect(engine)
        if "jago_pockets" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("jago_pockets")}
            with engine.begin() as conn:
                if "account_id" not in cols:
                    conn.execute(text("ALTER TABLE jago_pockets ADD COLUMN account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE"))
                if "role" not in cols:
                    conn.execute(text("ALTER TABLE jago_pockets ADD COLUMN role VARCHAR(30) DEFAULT 'operasional' NOT NULL"))
    except Exception:
        pass

ensure_pocket_schema_compatibility()
ensure_pocket_subscription_schema(engine)

IS_PROD = os.getenv("ENVIRONMENT", "production").lower() == "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=None if IS_PROD else f"{settings.API_V1_STR}/openapi.json",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
)

# Enable CORS with strict origin allowlist
ALLOWED_ORIGINS = [
    "https://ai7finance.alifihsan.my.id",
    "https://tillfold.alifihsan.my.id",
]
if not IS_PROD:
    ALLOWED_ORIGINS.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://telegram.org https://accounts.google.com; "
        "frame-src 'self' https://accounts.google.com; "
        "style-src 'self' 'unsafe-inline' https://accounts.google.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://accounts.google.com https://ai7finance.alifihsan.my.id https://tillfold.alifihsan.my.id;"
    )
    return response

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Serve Frontend static files if present
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
INDEX_PATH = os.path.join(STATIC_DIR, "index.html")
NEXT_DIR = os.path.join(STATIC_DIR, "_next")

if os.path.exists(NEXT_DIR):
    app.mount("/_next", StaticFiles(directory=NEXT_DIR), name="next_static")

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME, "version": settings.VERSION}

if os.path.exists(INDEX_PATH):
    @app.get("/")
    def root():
        return FileResponse(INDEX_PATH)

if os.path.exists(STATIC_DIR):
    real_static_dir = os.path.realpath(STATIC_DIR)

    @app.get("/{file_name:path}")
    def serve_static(file_name: str):
        clean_name = file_name.strip("/")
        # Block soft-404 fallthrough on unhandled API routes and prod docs
        if clean_name.startswith("api") or (IS_PROD and clean_name in ("docs", "redoc", "openapi.json")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        target_path = os.path.realpath(os.path.join(STATIC_DIR, file_name))
        # Prevent directory traversal attacks
        try:
            if os.path.commonpath([real_static_dir, target_path]) != real_static_dir:
                return JSONResponse({"detail": "Forbidden"}, status_code=403)
        except ValueError:
            return JSONResponse({"detail": "Forbidden"}, status_code=403)

        if os.path.isfile(target_path):
            return FileResponse(target_path)
        if os.path.exists(INDEX_PATH):
            return FileResponse(INDEX_PATH)
        return JSONResponse({"detail": "Not Found"}, status_code=404)
