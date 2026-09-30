"""Importação local de registros com simulação transacional e recibo de reconciliação."""
import hashlib
import json

from flask import g, jsonify, request

from .catalog import MODULES
from .db import audit, db, decrypt, encrypt, now
from . import workflows


def register(app, error, roles, validate_record):
    @app.get("/api/migration/records/template")
    @roles("gestor")
    def template():
        return jsonify(source="Identificação da base de origem", items=[dict(source_id="id-estavel-na-origem", module="encounters", data=dict(patient_id=1, unit_id=1, date="2026-09-01", care_type="Atendimento médico", subjective="Relato", objective="Exame", assessment="Avaliação", plan="Plano", status="Rascunho"))])

    @app.get("/api/migration/runs")
    @roles("gestor")
    def runs():
        audit("read", "migration_runs"); db().commit()
        return jsonify(items=[dict(id=r["id"], created_at=r["created_at"], **decrypt(r["payload"])) for r in db().execute("SELECT * FROM migration_runs ORDER BY id DESC")])

    @app.post("/api/migration/records/<action>")
    @roles("gestor")
    def import_records(action):
        if action not in ("validate", "import"):
            return jsonify(error="Operação desconhecida."), 404
        file = request.files.get("file")
        if not file:
            raise error("Selecione o arquivo JSON de registros.")
        try:
            batch = json.loads(file.read().decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            raise error("JSON inválido.")
        if not isinstance(batch, dict) or not isinstance(batch.get("source"), str) or not batch["source"].strip() or len(batch["source"]) > 200 or not isinstance(batch.get("items"), list) or not 1 <= len(batch["items"]) <= 1000:
            raise error("Informe origem e de 1 a 1.000 registros em items.")
        fingerprint = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest()
        db().execute("BEGIN IMMEDIATE")
        existing = db().execute("SELECT id FROM migration_runs WHERE fingerprint=?", (fingerprint,)).fetchone()
        if existing:
            return jsonify(error="Arquivo já importado.", receipt_id=existing["id"]), 409
        previous = set()
        for row in db().execute("SELECT payload FROM migration_runs"):
            report = decrypt(row[0])
            if report["source"] == batch["source"]:
                previous.update((r["module"], r["source_id"]) for r in report["records"])
        errors, inserted, seen = [], [], set()
        db().execute("SAVEPOINT batch_validation")
        for index, entry in enumerate(batch["items"], 1):
            db().execute("SAVEPOINT entry_validation")
            try:
                if not isinstance(entry, dict) or entry.get("module") not in MODULES or not isinstance(entry.get("data"), dict) or not isinstance(entry.get("source_id"), str) or not 1 <= len(entry["source_id"]) <= 150:
                    raise error("Informe module, source_id textual e data.")
                key, data, source_id = entry["module"], entry["data"], entry["source_id"]
                identity = (key, source_id)
                if identity in seen or identity in previous:
                    raise error("Identificador de origem já importado ou repetido no arquivo.")
                seen.add(identity)
                value = validate_record(key, data)
                status = data.get("status", MODULES[key]["statuses"][0])
                if status not in MODULES[key]["statuses"]:
                    raise error("Situação inválida.")
                value.update(import_source=batch["source"], import_source_id=source_id, imported_at=now())
                value = workflows.seal(key, value, status)
                cur = db().execute("INSERT INTO records(module,patient_id,unit_id,payload,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (key, value.get("patient_id") or None, value.get("unit_id") or None, encrypt(value), status, g.user["id"], now(), now()))
                workflows.after_save(key, cur.lastrowid, value)
                inserted.append(dict(module=key, source_id=source_id, id=cur.lastrowid))
                db().execute("RELEASE entry_validation")
            except error as exc:
                db().execute("ROLLBACK TO entry_validation"); db().execute("RELEASE entry_validation")
                errors.append(dict(line=index, error=str(exc)))
        if errors or action == "validate":
            db().execute("ROLLBACK TO batch_validation"); db().execute("RELEASE batch_validation")
            db().rollback()
            return jsonify(total=len(batch["items"]), valid=len(inserted), errors=errors, imported=0), 400 if errors and action == "import" else 200
        db().execute("RELEASE batch_validation")
        report = dict(source=batch["source"], total=len(inserted), imported=len(inserted), records=inserted, sha256=fingerprint)
        cur = db().execute("INSERT INTO migration_runs(fingerprint,payload,created_by,created_at) VALUES(?,?,?,?)", (fingerprint, encrypt(report), g.user["id"], now()))
        audit("import", "records", cur.lastrowid); db().commit()
        return jsonify(receipt_id=cur.lastrowid, **report), 201
