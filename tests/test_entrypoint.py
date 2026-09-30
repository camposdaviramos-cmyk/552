"""Check import-time startup without opening a listening server."""

import json
import runpy
import tempfile
import tomllib
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


def test_vercel_preserves_flask_routes():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["framework"] == "flask"
    assert not config.get("rewrites")
    assert not config.get("builds")
    assert not config.get("routes")


def test_vercel_project_declares_runtime_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = {
        line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert project["project"]["name"]
    assert project["project"]["version"]
    assert project["project"]["requires-python"] == ">=3.12"
    assert set(project["project"]["dependencies"]) == requirements
    assert project["tool"]["vercel"]["entrypoint"] == "run:app"
