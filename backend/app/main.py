import asyncio

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import DbSession

app = FastAPI(title="Harness Agent")

READY_TIMEOUT_SECONDS = 2.0


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def db_ready(db: DbSession) -> dict[str, str]:
    try:
        async with asyncio.timeout(READY_TIMEOUT_SECONDS):
            await db.execute(text("SELECT 1"))
    except (TimeoutError, SQLAlchemyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库不可用",
        ) from exc

    return {"status": "ok"}
