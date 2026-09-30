import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timezone
from flask import current_app, g, session, has_request_context

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS units(id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, cnes TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY, payload TEXT NOT NULL, identity_hash TEXT UNIQUE, created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL, role TEXT NOT NULL, patient_id INTEGER REFERENCES patients(id), active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, module TEXT NOT NULL, patient_id INTEGER REFERENCES patients(id), unit_id INTEGER REFERENCES units(id), payload TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_records_module ON records(module,unit_id);
CREATE INDEX IF NOT EXISTS ix_records_patient ON records(patient_id);
CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL REFERENCES records(id), patient_id INTEGER REFERENCES patients(id), quantity INTEGER NOT NULL, kind TEXT NOT NULL, reason TEXT NOT NULL, created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor INTEGER, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT, created_at TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts(key TEXT PRIMARY KEY, failures INTEGER NOT NULL, last_at REAL NOT NULL);
"""

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=20)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

def encrypt(value):
    return current_app.extensions["cipher"].encrypt(json.dumps(value,ensure_ascii=False).encode()).decode()

def decrypt(value):
    return json.loads(current_app.extensions["cipher"].decrypt(value.encode()))

def identity_hash(value):
    return hmac.new(current_app.config["HASH_KEY"],value.encode(),hashlib.sha256).hexdigest()

def audit(action, entity, entity_id=""):
    conn = db()
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    prev = conn.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    previous = prev[0] if prev else "0"*64
    actor = session.get("uid") if has_request_context() else None
    stamp = now()
    content = json.dumps([actor,action,entity,str(entity_id),stamp,previous],ensure_ascii=False)
    digest = identity_hash(content)
    conn.execute("INSERT INTO audit(actor,action,entity,entity_id,created_at,previous_hash,hash) VALUES(?,?,?,?,?,?,?)",(actor,action,entity,str(entity_id),stamp,previous,digest))

def patient_dict(row):
    return dict(id=row["id"],created_at=row["created_at"],version=row["version"],**decrypt(row["payload"]))

def record_dict(row):
    return dict(id=row["id"],module=row["module"],status=row["status"],version=row["version"],created_at=row["created_at"],updated_at=row["updated_at"],created_by=row["created_by"],**decrypt(row["payload"]))
