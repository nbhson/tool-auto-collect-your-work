"""Shared test fixtures and configuration."""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Test database engine (in-memory SQLite) ───────────


@pytest.fixture(scope="session")
def test_engine():
    """Create a shared in-memory SQLite engine for the test session."""
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture(scope="session")
def testing_db_url(tmp_path_factory) -> str:
    """Create a temp file database URL for session scope."""
    db_dir = tmp_path_factory.mktemp("test_db")
    return f"sqlite:///{db_dir}/test_worklog.db"


@pytest.fixture(scope="function")
def test_engine_per_func(testing_db_url):
    """Create a fresh engine per test function using a temp file."""
    from sqlalchemy import create_engine

    return create_engine(
        testing_db_url,
        connect_args={"check_same_thread": False},
    )


# ─── Patch database before importing app ──────────────


@pytest.fixture(scope="function", autouse=True)
def patch_database(test_engine_per_func, monkeypatch):
    """Patch database module with test engine before app is imported."""
    from database import db as db_module

    # Patch the engine and SessionLocal
    monkeypatch.setattr(db_module, "engine", test_engine_per_func)
    monkeypatch.setattr(
        db_module,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=test_engine_per_func),
    )

    # Create tables using test engine
    db_module.Base.metadata.create_all(bind=test_engine_per_func)

    yield

    # Cleanup: drop all tables
    db_module.Base.metadata.drop_all(bind=test_engine_per_func)


# ─── Scheduler mock ────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_scheduler(monkeypatch):
    """Prevent actual scheduler from starting during tests."""
    from unittest.mock import MagicMock

    mock_scheduler_instance = MagicMock()

    def mock_start():
        pass

    def mock_stop():
        pass

    mock_scheduler_instance.start = mock_start
    mock_scheduler_instance.stop = mock_stop

    from pollers import scheduler as sched_module

    monkeypatch.setattr(sched_module, "scheduler", mock_scheduler_instance)
    monkeypatch.setattr(sched_module, "start_scheduler", mock_start)
    monkeypatch.setattr(sched_module, "stop_scheduler", mock_stop)


# ─── Test client ───────────────────────────────────────


@pytest.fixture(scope="function")
def client(patch_database) -> Generator[TestClient, None, None]:
    """Create a FastAPI test client with test database."""
    # Import app after database is patched
    from app import app

    with TestClient(app) as test_client:
        yield test_client


# ─── Test database session ────────────────────────────


@pytest.fixture(scope="function")
def db_session(test_engine_per_func) -> Generator[Session, None, None]:
    """Provide a test database session for direct DB operations."""
    from sqlalchemy.orm import sessionmaker

    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine_per_func)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
