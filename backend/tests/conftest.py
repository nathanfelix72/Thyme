"""Shared pytest fixtures for Thyme API tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def tmp_data(tmp_path, monkeypatch):
    """Isolate recipe + chroma storage under a temp directory."""
    from app.modules.shared import config

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "CHROMA_DIR", data / "chroma")
    monkeypatch.setattr(config, "THYME_ENV", "local")
    monkeypatch.setattr(config, "ALLOW_ANON", True)
    monkeypatch.setattr(config, "TAVILY_API_KEY", "")
    return data


@pytest.fixture()
def client(tmp_data):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
