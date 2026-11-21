import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_strict_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.backup import MAX_BYTES, export_backup, restore_backup, summary, validate_backup

router = APIRouter()


async def read_backup(request: Request):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_BYTES:
            raise HTTPException(413, "Ukuran backup maksimal 25 MB.")
    try:
        payload = json.loads(content)
        return validate_backup(payload), payload["version"]
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise HTTPException(400, "File JSON backup tidak dapat dibaca.")


@router.get("/export")
def download_backup(user: User = Depends(get_strict_current_user), db: Session = Depends(get_db)):
    engine = db.get_bind()
    isolation = "REPEATABLE READ" if engine.dialect.name == "postgresql" else "SERIALIZABLE"
    with engine.connect().execution_options(isolation_level=isolation) as connection:
        with Session(bind=connection) as snapshot:
            payload = export_backup(snapshot, user.id)
            validate_backup(payload)
    content = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise HTTPException(413, "Backup melebihi batas restore 25 MB.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(content, media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="tillfold-backup-{stamp}.json"',
        "Cache-Control": "no-store",
    })


@router.post("/preview")
async def preview_backup(request: Request, user: User = Depends(get_strict_current_user)):
    data, version = await read_backup(request)
    result = summary(data)
    if version < 5:
        result["legacy_missing_loan_history"] = True
    return result


@router.post("/restore")
async def restore(request: Request, user: User = Depends(get_strict_current_user), db: Session = Depends(get_db)):
    data, _ = await read_backup(request)
    try:
        return restore_backup(db, user, data)
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Backup memiliki data duplikat atau relasi yang tidak valid.")
    except Exception:
        db.rollback()
        raise
