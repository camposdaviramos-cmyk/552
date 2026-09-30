"""Revocable browser sessions shared by cookie and Bearer authentication."""
import hashlib
import secrets
import time

from flask import current_app, g, request, session
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.exceptions import Unauthorized

from .db import db


def lifetime():
    return current_app.permanent_session_lifetime.total_seconds()


def login_challenge():
    return URLSafeTimedSerializer(current_app.secret_key, salt="login-csrf-v1")


def new_csrf():
    return login_challenge().dumps(secrets.token_urlsafe(32))


def valid_csrf(login=False):
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf", "")
    if expected and secrets.compare_digest(supplied, expected):
        return True
    # A signed, short-lived bootstrap challenge permits login without cookies.
    # Protected cookie mutations still require the session-bound CSRF value.
    if login:
        try:
            login_challenge().loads(supplied, max_age=600)
            return True
        except BadSignature:
            pass
    return False


def resolve_user():
    g.bearer_auth = "Authorization" in request.headers
    session_id = session.get("sid")
    if g.bearer_auth:
        parts = request.headers["Authorization"].split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or len(parts[1]) != 43:
            raise Unauthorized()
        session_id = hashlib.sha256(parts[1].encode()).hexdigest()
    g.auth_session = None
    uid = session.get("uid")
    if session_id:
        row = db().execute("SELECT * FROM auth_sessions WHERE token_hash=? AND expires_at>?", (session_id, time.time())).fetchone()
        if not row:
            if g.bearer_auth:
                raise Unauthorized()
            session.clear()
            return None
        g.auth_session = dict(row)
        uid = row["user_id"]
    user = db().execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone() if uid else None
    if not user and g.bearer_auth:
        raise Unauthorized()
    if user and g.auth_session:
        db().execute("UPDATE auth_sessions SET expires_at=? WHERE token_hash=?", (time.time() + lifetime(), session_id))
        db().commit()
    return dict(user) if user else None


def issue_session(user):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    csrf = secrets.token_urlsafe(32)
    # Rotate the current browser session on successful authentication.
    if session.get("sid"):
        db().execute("DELETE FROM auth_sessions WHERE token_hash=?", (session["sid"],))
    db().execute("DELETE FROM auth_sessions WHERE expires_at<=?", (time.time(),))
    db().execute("INSERT INTO auth_sessions(token_hash,user_id,csrf,expires_at) VALUES(?,?,?,?)", (token_hash, user["id"], csrf, time.time() + lifetime()))
    session.clear()
    session.update(uid=user["id"], sid=token_hash, csrf=csrf)
    session.permanent = True
    g.user = dict(user)
    return token


def revoke_session():
    if g.auth_session:
        db().execute("DELETE FROM auth_sessions WHERE token_hash=?", (g.auth_session["token_hash"],))
    session.clear()
