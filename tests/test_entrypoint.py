"""Check import-time startup without opening a listening server."""

import json
import runpy
import tempfile
from pathlib import Path
from unittest.mock import Mock

import saude.app
import waitress


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_import_uses_writable_instance_and_serves_requests(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    serve = Mock(side_effect=AssertionError("Import must not start a server"))
    monkeypatch.setattr(waitress, "serve", serve)

    namespace = runpy.run_path(str(ROOT / "run.py"), run_name="vercel_entrypoint")
    app = namespace["app"]
    assert Path(app.config["DATABASE"]).parent == tmp_path / "integra-saude"
    with app.test_client() as client:
        assert client.get("/api/health").json == {"status": "ok"}
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/api/session").json["user"] is None
    serve.assert_not_called()


def test_local_import_preserves_factory_defaults(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    app = object()
    factory = Mock(return_value=app)
    monkeypatch.setattr(saude.app, "create_app", factory)
    namespace = runpy.run_path(str(ROOT / "run.py"), run_name="local_entrypoint")
    assert namespace["app"] is app
    factory.assert_called_once_with({})


def test_vercel_rewrites():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config == {
        "rewrites": [{"source": "/(.*)", "destination": "/run.py"}]
    }
