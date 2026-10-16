import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.main import app


@pytest.fixture
def mock_db(monkeypatch):
    db = AsyncMock(spec=AsyncSession)

    async def override_get_db():
        yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db)

    return db


def test_ready_success(mock_db) -> None:
    client = TestClient(app)
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    mock_db.execute.assert_awaited_once()

    assert str(mock_db.execute.await_args.args[0]) == "SELECT 1"


def test_ready_failure(mock_db) -> None:
    mock_db.execute.side_effect = SQLAlchemyError("Database connection error")

    client = TestClient(app)
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "数据库不可用"}


def test_ready_timeout(mock_db, monkeypatch) -> None:
    monkeypatch.setattr("app.main.READY_TIMEOUT_SECONDS", 0.01)

    async def slow_execute(*args, **kwargs):
        await asyncio.sleep(1)

    mock_db.execute.side_effect = slow_execute

    client = TestClient(app)
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "数据库不可用"}


def test_live_does_not_access_database(mock_db):
    mock_db.execute.side_effect = SQLAlchemyError("数据库不可用")

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_db.execute.assert_not_awaited()
