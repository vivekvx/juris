"""Shared pytest fixtures for Juris backend tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.utils.logging import configure_logging


@pytest.fixture(autouse=True)
def _configure_logging() -> None:
    configure_logging()


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client. Firebase not initialised — health must not need it."""
    return TestClient(create_app())
