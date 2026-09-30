"""Authentication with cookies completely disabled, plus cookie compatibility."""
import hashlib
import io
import time

import pytest

from saude.db import db
from test_app import app, encounter

ORIGIN = "https://552-blue.vercel.app"
CREDENTIALS = {"username": "admin", "password": "Test@Password2026"}


def token_login(client, username="admin"):
    csrf = client.get("/api/session", headers={"Origin": ORIGIN}).json["csrf"]
    response = client.post("/api/login", json={**CREDENTIALS, "username": username}, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert response.json["token_type"] == "Bearer"
    assert response.json["expires_in"] == 1800
    assert "password" not in response.json["user"]
    return response.json, {"Authorization": "Bearer " + response.json["token"], "Origin": ORIGIN}


def test_cookieless_login_navigation_writes_downloads_logout(app):
    client = app.test_client(use_cookies=False)
    data, headers = token_login(client)
    assert client.get("/api/session", headers=headers).json["user"] == data["user"]
    for path in ("/api/meta", "/api/patients", "/api/patients/1/timeline", "/api/records/encounters", "/api/export/encounters"):
        assert client.get(path, headers=headers).status_code == 200, path
    response = client.post("/api/records/encounters", json={**encounter(), "status": "Rascunho"}, headers=headers)
    assert response.status_code == 201
    rid = response.json["id"]
    response = client.post(f"/api/records/{rid}/attachments", headers=headers, data={"file": (io.BytesIO(b"%PDF-1.4\nTest"), "teste.pdf")})
    assert response.status_code == 201
    assert client.get(f'/api/attachments/{response.json["id"]}', headers=headers).status_code == 200
    with app.app_context():
        row = db().execute("SELECT * FROM auth_sessions").fetchone()
        assert row["token_hash"] == hashlib.sha256(data["token"].encode()).hexdigest()
        assert data["token"] not in dict(row).values()
        assert db().execute("SELECT actor FROM audit WHERE action='create' ORDER BY id DESC").fetchone()[0] == data["user"]["id"]
    assert client.post("/api/logout", headers=headers).status_code == 200
    assert client.get("/api/session", headers=headers).status_code == 401
    assert client.get("/api/meta", headers=headers).status_code == 401


@pytest.mark.parametrize("authorization", ["Bearer invalid", "Bearer", "Basic abc", "", "Bearer " + "a" * 43])
def test_invalid_header_never_falls_back_to_valid_cookie(app, authorization):
    client = app.test_client()
    token_login(client)
    assert client.get("/api/meta").status_code == 200
    assert client.get("/api/meta", headers={"Authorization": authorization}).status_code == 401
    assert client.get("/api/meta").status_code == 200


@pytest.mark.parametrize("logout_with_token", [True, False])
def test_logout_revokes_both_cookie_and_token(app, logout_with_token):
    client = app.test_client()
    data, headers = token_login(client)
    cookie = client.get_cookie("session").value
    logout_headers = headers if logout_with_token else {"X-CSRF-Token": data["csrf"]}
    assert client.post("/api/logout", headers=logout_headers).status_code == 200
    assert client.get("/api/meta", headers=headers).status_code == 401
    client.set_cookie("session", cookie)
    assert client.get("/api/meta").status_code == 401


def test_expiration_and_activity_extension(app):
    client = app.test_client(use_cookies=False)
    _, headers = token_login(client)
    with app.app_context():
        db().execute("UPDATE auth_sessions SET expires_at=?", (time.time() + 30,))
        db().commit()
    assert client.get("/api/meta", headers=headers).status_code == 200
    with app.app_context():
        assert db().execute("SELECT expires_at FROM auth_sessions").fetchone()[0] > time.time() + 1700
        db().execute("UPDATE auth_sessions SET expires_at=0")
        db().commit()
    assert client.get("/api/meta", headers=headers).status_code == 401


def test_bearer_roles_deactivation_and_user_id_rejected(app):
    client = app.test_client(use_cookies=False)
    data, headers = token_login(client, "reception")
    assert client.get("/api/records/encounters", headers=headers).status_code == 403
    assert client.get("/api/patients", headers=headers).status_code == 200
    assert client.get("/api/patients", headers={"X-User-ID": "1"}).status_code == 401
    with app.app_context():
        db().execute("UPDATE users SET active=0 WHERE id=?", (data["user"]["id"],))
        db().commit()
    assert client.get("/api/session", headers=headers).status_code == 401


def test_citizen_stream_and_boundaries_without_cookie(app):
    client = app.test_client(use_cookies=False)
    _, headers = token_login(client, "citizen")
    assert client.get("/api/citizen", headers=headers).status_code == 200
    assert client.get("/api/patients", headers=headers).status_code == 403
    app.config.update(EVENT_STREAM_TICKS=1)
    response = client.get("/api/citizen/events", headers=headers)
    assert response.status_code == 200
    assert b"event: refresh" in response.data


def test_login_challenge_required_valid_and_unexpired(app, monkeypatch):
    client = app.test_client(use_cookies=False)
    csrf = client.get("/api/session").json["csrf"]
    for supplied in ("", csrf + "tampered"):
        assert client.post("/api/login", json=CREDENTIALS, headers={"X-CSRF-Token": supplied}).status_code == 403
    future = time.time() + 601
    monkeypatch.setattr("itsdangerous.timed.time.time", lambda: future)
    assert client.post("/api/login", json=CREDENTIALS, headers={"X-CSRF-Token": csrf}).status_code == 403


def test_bearer_cors_preflight(app):
    response = app.test_client(use_cookies=False).options("/api/records/encounters", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type, X-CSRF-Token, Last-Event-ID",
    })
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ORIGIN
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]
    assert "Last-Event-ID" in response.headers["Access-Control-Allow-Headers"]
