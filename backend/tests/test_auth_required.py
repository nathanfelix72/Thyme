"""Auth gate: anonymous callers are rejected unless ALLOW_ANON is on."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_recipes_list_requires_sign_in(tmp_path, monkeypatch):
    from app.modules.shared import config
    from app.main import app

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "CHROMA_DIR", data / "chroma")
    monkeypatch.setattr(config, "THYME_ENV", "local")
    monkeypatch.setattr(config, "ALLOW_ANON", False)

    with TestClient(app) as client:
        res = client.get("/api/recipes/list")
        assert res.status_code == 401
        assert "Sign in" in res.json()["detail"]
