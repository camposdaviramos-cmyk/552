"""Regras de negócio locais compartilhadas pela API e pela importação validada."""
import hashlib
import io
import json
import re
import time
import threading
from collections import Counter
from datetime import date, datetime

from flask import Response, g, jsonify, request, send_file, stream_with_context

from .catalog import MODULES, can_access
from .db import audit, db, decrypt, encrypt, identity_hash, now, record_dict, snapshot

FINAL = {"encounters": "Finalizado", "exams": "Laudado", "fleet_events": "Registrado"}
TEETH = {str(q * 10 + n) for q in range(1, 9) for n in range(1, 9 if q <= 4 else 6)}
TOOTH_STATES = {"Hígido", "Cárie", "Restaurado", "Ausente", "Tratamento indicado", "Tratado"}


def records(key):
    return [record_dict(r) for r in db().execute("SELECT * FROM records WHERE module=? ORDER BY id", (key,))]


def odontogram(value, error):
    if not value:
        return {}
    try:
        value = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        raise error("Odontograma inválido.")
    if not isinstance(value, dict) or any(k not in TEETH or v not in TOOTH_STATES for k, v in value.items()):
        raise error("Informe dentes e condições válidas no odontograma.")
    return value


def validate(key, value, data, old, error):
    status = data.get("status", MODULES[key]["statuses"][0])
    others = lambda module: [r for r in records(module) if not old or r["id"] != old["id"]]
    if key == "encounters":
        care = value["care_type"]
        for f in MODULES[key]["fields"]:
            if f.get("care_types") and care not in f["care_types"]:
                value[f["key"]] = {} if f["type"] == "odontogram" else ""
        if value.get("oxygen", "") != "" and value["oxygen"] > 100:
            raise error("Saturação deve estar entre 0 e 100%.")
    if key == "exams" and status == "Laudado" and not value.get("result"):
        raise error("Informe o resultado antes de liberar o laudo.")
    if key == "shifts":
        start = value["date"] + "T" + value["time"]
        end = value["end_date"] + "T" + value["end_time"]
        if end <= start:
            raise error("O término do plantão deve ser posterior ao início.")
        if status != "Cancelado":
            for r in others(key):
                if r["status"] != "Cancelado" and r["professional_id"] == value["professional_id"] and start < r["end_date"] + "T" + r["end_time"] and end > r["date"] + "T" + r["time"]:
                    raise error("Profissional já escalado neste intervalo.")
    if key in ("prescriptions", "goals") and value["end_date"] < value["date"]:
        raise error("A data final não pode anteceder a inicial.")
    if key == "goals" and (value["target"] < 1 or value["target"] != int(value["target"])):
        raise error("A meta quantitativa deve ser inteira e positiva.")
    if key == "prescriptions":
        if value.get("hospital_id"):
            admission = record_dict(db().execute("SELECT * FROM records WHERE id=?", (value["hospital_id"],)).fetchone())
            if admission["patient_id"] != value["patient_id"] or admission["unit_id"] != value["unit_id"]:
                raise error("A internação deve corresponder ao paciente e à unidade da prescrição.")
            if not old and admission["status"] not in ("Internado", "Em observação"):
                raise error("A internação não está ativa.")
        if old and db().execute("SELECT 1 FROM workflow_events WHERE record_id=? AND kind='administration'", (old["id"],)).fetchone():
            if any(value.get(f["key"]) != old.get(f["key"], "") for f in MODULES[key]["fields"]):
                raise error("Prescrição com doses checadas não pode ser alterada. Suspenda e crie nova prescrição.")
    if key == "assets":
        if any(r["tag"].casefold() == value["tag"].casefold() for r in others(key)):
            raise error("Tombamento já cadastrado.")
        if (value.get("residual_value") or 0) > value["value"]:
            raise error("O valor residual não pode superar o valor de aquisição.")
        if value.get("useful_life") and (value["useful_life"] < 1 or value["useful_life"] != int(value["useful_life"])):
            raise error("Informe vida útil em meses inteiros positivos.")
        if old and (old["unit_id"] != value["unit_id"] or old["responsible"] != value["responsible"]):
            raise error("Use Transferência patrimonial para alterar unidade ou responsável.")
    if key == "transport":
        if value.get("return_time") and value["return_time"] <= value["time"]:
            raise error("O retorno deve ocorrer após a saída no mesmo dia.")
        value["total_cost"] = round(sum(value.get(k) or 0 for k in ("travel_cost", "lodging_cost", "meal_cost", "companion_cost")), 2)
        if status not in ("Cancelado", "Concluído"):
            end = value.get("return_time") or value["time"]
            for r in others(key):
                if r["status"] in ("Cancelado", "Concluído") or r["date"] != value["date"]:
                    continue
                if r["time"] == value["time"]:
                    if (r["vehicle_id"] == value["vehicle_id"]) != (r["driver"].casefold() == value["driver"].casefold()):
                        raise error("Motorista e veículo devem corresponder à mesma viagem neste horário.")
                    continue
                r_end = r.get("return_time") or r["time"]
                if value["time"] <= r_end and end >= r["time"] and (r["vehicle_id"] == value["vehicle_id"] or r["patient_id"] == value["patient_id"] or r["driver"].casefold() == value["driver"].casefold()):
                    raise error("Conflito de intervalo de viagem para veículo, motorista ou paciente.")
    if key == "fleet":
        value["plate"] = re.sub(r"[\s-]", "", value["plate"]).upper()
        if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", value["plate"]):
            raise error("Placa inválida.")
        if value["capacity"] < 1:
            raise error("A capacidade deve ser positiva.")
        if any(r["plate"] == value["plate"] for r in others(key)):
            raise error("Placa já cadastrada.")
        if old and value["mileage"] < old["mileage"]:
            raise error("Quilometragem não pode retroceder.")
        trips = [r for r in records("transport") if r["vehicle_id"] == (old or {}).get("id") and r["status"] not in ("Cancelado", "Concluído")]
        if trips and status in ("Inativo", "Em manutenção"):
            raise error("Reprograme ou cancele as viagens antes de indisponibilizar o veículo.")
        seats = Counter()
        for r in trips:
            seats[(r["date"], r["time"])] += 1 + bool(r.get("companion"))
        if any(n > value["capacity"] for n in seats.values()):
            raise error("Capacidade inferior à lotação já programada.")
    if key == "fleet_events":
        vehicle = record_dict(db().execute("SELECT * FROM records WHERE id=?", (value["vehicle_id"],)).fetchone())
        if value["mileage"] < vehicle["mileage"]:
            raise error("Quilometragem inferior à última registrada.")
        if value["kind"] == "Abastecimento" and not value.get("liters"):
            raise error("Informe os litros abastecidos.")
    if key == "billing":
        if status == "Rejeitado" and not value.get("review_notes"):
            raise error("Informe o motivo de rejeição da produção.")
        if value.get("source_id"):
            source = record_dict(db().execute("SELECT * FROM records WHERE id=?", (value["source_id"],)).fetchone())
            if source["patient_id"] != value["patient_id"] or source["unit_id"] != value["unit_id"]:
                raise error("Origem da produção incompatível com paciente/unidade.")
            if source["status"] not in ("Finalizado", "Laudado", "Concluído"):
                raise error("Conclua o atendimento de origem antes de faturar.")
            if any(r.get("source_id") == value["source_id"] and r["code"] == value["code"] and r["status"] != "Rejeitado" for r in others(key)):
                raise error("Procedimento já faturado para este atendimento.")
    if key == "territories":
        if value["population"] < 1 or value["population"] != int(value["population"]):
            raise error("A população deve ser inteira e positiva.")
        if any(r["territory"].casefold() == value["territory"].casefold() and r["date"] == value["date"] for r in others(key)):
            raise error("Já existe uma base populacional para este território e data.")
    if key == "support" and status == "Concluído" and not value.get("resolution"):
        raise error("Registre a solução antes de concluir o chamado.")
    if key == "training" and status == "Concluído" and not value.get("evidence"):
        raise error("Registre a evidência de execução antes de concluir a atividade.")
    if key == "regulation" and status in ("Autorizado", "Agendado") and not value.get("scheduled_date"):
        raise error("Informe a data autorizada para esta solicitação.")
    if key == "hospital" and status in ("Internado", "Em observação"):
        if any(r["patient_id"] == value["patient_id"] and r["status"] in ("Internado", "Em observação") for r in others(key)):
            raise error("Paciente já possui internação ativa.")


def seal(key, value, status):
    if key in ("encounters", "exams") and status == FINAL[key]:
        value["signed_by"] = g.user["id"]
        value["signed_at"] = now()
        value["seal"] = identity_hash(json.dumps(value, sort_keys=True, ensure_ascii=False))
    return value


def after_save(key, rid, value):
    snapshot(rid)
    if key == "fleet_events":
        vehicle = record_dict(db().execute("SELECT * FROM records WHERE id=?", (value["vehicle_id"],)).fetchone())
        snapshot(vehicle["id"])
        payload = decrypt(db().execute("SELECT payload FROM records WHERE id=?", (vehicle["id"],)).fetchone()[0])
        payload["mileage"] = value["mileage"]
        db().execute("UPDATE records SET payload=?,version=version+1,updated_at=? WHERE id=?", (encrypt(payload), now(), vehicle["id"]))
        snapshot(vehicle["id"])


def register(app, error, roles):
    # Reserva threads para as demais rotas mesmo com vários portais conectados.
    stream_slots = threading.BoundedSemaphore(app.config.get("MAX_EVENT_STREAMS", 4))
    @app.get("/api/references/<key>/<field_key>")
    def references(key, field_key):
        if key not in MODULES or not can_access(g.user["role"], key):
            return jsonify(error="Acesso não permitido."), 403
        field = next((f for f in MODULES[key]["fields"] if f["key"] == field_key and f["type"] == "record"), None)
        if not field:
            raise error("Campo de referência inválido.")
        targets = ("appointments", "encounters", "exams") if field["module"] == "clinical_source" else (field["module"],)
        items = []
        for target in targets:
            for r in records(target):
                items.append(dict(id=r["id"], label=f'{MODULES[target]["singular"]} #{r["id"]} · paciente #{r.get("patient_id")} · {r.get("date", "")} · {r["status"]}'))
        return jsonify(items=items)

    @app.get("/api/citizen/events")
    @roles("cidadao")
    def citizen_events():
        if not stream_slots.acquire(blocking=False):
            return jsonify(error="Canal ocupado; o portal utilizará atualização periódica."), 503
        uid, pid = g.user["id"], g.user["patient_id"]
        auth_session = g.auth_session
        released = False
        def release_slot():
            nonlocal released
            if not released:
                released = True
                stream_slots.release()
        # O evento só transporta uma revisão opaca; o conteúdo continua na API autenticada.
        @stream_with_context
        def stream():
            try:
                previous = request.headers.get("Last-Event-ID", "")
                for _ in range(app.config.get("EVENT_STREAM_TICKS", 20)):
                    with app.app_context():
                        user = db().execute("SELECT active,patient_id,role FROM users WHERE id=?", (uid,)).fetchone()
                        session_active = not auth_session or db().execute("SELECT 1 FROM auth_sessions WHERE token_hash=? AND expires_at>?", (auth_session["token_hash"], time.time())).fetchone()
                        if not session_active or not user or not user["active"] or user["role"] != "cidadao" or user["patient_id"] != pid:
                            yield "event: revoked\ndata: {}\n\n"
                            return
                        versions = [tuple(r) for r in db().execute("SELECT id,version FROM records WHERE patient_id=? AND module IN ('appointments','messages','regulation','exams') ORDER BY id", (pid,))]
                        revision = hashlib.sha256(json.dumps(versions).encode()).hexdigest()
                    if revision != previous:
                        yield f"id: {revision}\nevent: refresh\ndata: {{}}\n\n"
                        previous = revision
                    else:
                        yield ": heartbeat\n\n"
                    if not app.config.get("TESTING"):
                        time.sleep(1)
            finally:
                release_slot()
        response = Response(stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
        response.call_on_close(release_slot)
        return response

    @app.get("/sw.js")
    def service_worker():
        response = app.send_static_file("sw.js")
        response.headers["Cache-Control"] = "no-cache"
        return response

    def authorized_record(rid, citizen=False):
        row = db().execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        if not row:
            return None
        r = record_dict(row)
        if g.user["role"] == "cidadao":
            if not citizen or r.get("patient_id") != g.user["patient_id"] or r["module"] != "exams" or r["status"] != "Laudado":
                return None
        elif not can_access(g.user["role"], r["module"]):
            return None
        return r

    def event(rid, kind, payload):
        db().execute("INSERT INTO workflow_events(record_id,kind,payload,created_by,created_at) VALUES(?,?,?,?,?)", (rid, kind, encrypt(payload), g.user["id"], now()))
        audit(kind, "records", rid)

    @app.get("/api/records/<int:rid>/history")
    def history(rid):
        r = authorized_record(rid)
        if not r:
            return jsonify(error="Registro não disponível."), 404
        versions = [decrypt(row[0]) for row in db().execute("SELECT payload FROM record_history WHERE record_id=? ORDER BY version DESC", (rid,))]
        events = [{**dict(row), "payload": decrypt(row["payload"])} for row in db().execute("SELECT * FROM workflow_events WHERE record_id=? ORDER BY id DESC", (rid,))]
        seal_valid = None
        if r.get("seal"):
            payload = decrypt(db().execute("SELECT payload FROM records WHERE id=?", (rid,)).fetchone()[0])
            signature = payload.pop("seal")
            seal_valid = signature == identity_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        audit("read", "record_history", rid); db().commit()
        return jsonify(versions=versions, events=events, seal_valid=seal_valid)

    @app.get("/api/records/<int:rid>/attachments")
    def attachments(rid):
        if not authorized_record(rid):
            return jsonify(error="Registro não disponível."), 404
        result = [dict(id=r["id"], created_at=r["created_at"], **decrypt(r["metadata"])) for r in db().execute("SELECT id,metadata,created_at FROM attachments WHERE record_id=?", (rid,))]
        audit("read", "attachments", rid); db().commit()
        return jsonify(items=result)

    @app.post("/api/records/<int:rid>/attachments")
    def upload_attachment(rid):
        db().execute("BEGIN IMMEDIATE")
        record = authorized_record(rid)
        if not record:
            return jsonify(error="Registro não disponível."), 404
        if FINAL.get(record["module"]) == record["status"]:
            raise error("Inclua anexos antes da finalização; documentos finalizados são imutáveis.")
        file = request.files.get("file")
        if not file:
            raise error("Selecione um PDF, PNG ou JPEG.")
        content = file.read(1024 * 1024 + 1)
        if not content or len(content) > 1024 * 1024:
            raise error("O anexo deve ter no máximo 1 MB.")
        mime = "application/pdf" if content.startswith(b"%PDF-") else "image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if content.startswith(b"\xff\xd8\xff") else None
        if not mime:
            raise error("Formato não permitido. Use PDF, PNG ou JPEG.")
        name = re.sub(r"[\x00-\x1f\\/]", "_", file.filename or "anexo")[:150]
        meta = dict(name=name, mime=mime, size=len(content), sha256=hashlib.sha256(content).hexdigest())
        cur = db().execute("INSERT INTO attachments(record_id,metadata,content,created_by,created_at) VALUES(?,?,?,?,?)", (rid, encrypt(meta), app.extensions["cipher"].encrypt(content), g.user["id"], now()))
        audit("upload", record["module"], rid); db().commit()
        return jsonify(id=cur.lastrowid, **meta), 201

    @app.get("/api/attachments/<int:aid>")
    @app.get("/api/citizen/attachments/<int:aid>")
    def download_attachment(aid):
        row = db().execute("SELECT * FROM attachments WHERE id=?", (aid,)).fetchone()
        if not row or not authorized_record(row["record_id"], citizen=True):
            return jsonify(error="Anexo não disponível."), 404
        meta = decrypt(row["metadata"])
        content = app.extensions["cipher"].decrypt(row["content"])
        if hashlib.sha256(content).hexdigest() != meta["sha256"]:
            raise error("Integridade do anexo não confirmada.")
        audit("download", "attachments", aid); db().commit()
        response = send_file(io.BytesIO(content), mimetype=meta["mime"], as_attachment=True, download_name=meta["name"])
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/prescriptions/<int:rid>/administrations")
    @roles("clinico", "gestor")
    def administer(rid):
        db().execute("BEGIN IMMEDIATE")
        r = authorized_record(rid)
        if not r or r["module"] != "prescriptions":
            return jsonify(error="Prescrição não disponível."), 404
        data = request.get_json(silent=True) or {}
        if r["status"] != "Ativa":
            raise error("Prescrição não está ativa.")
        try:
            stamp = datetime.fromisoformat(data.get("scheduled_at", ""))
            if not r["date"] <= stamp.date().isoformat() <= r["end_date"]:
                raise ValueError()
        except (ValueError, TypeError):
            raise error("Horário da dose fora da vigência da prescrição.")
        if data.get("outcome") not in ("Administrada", "Não administrada") or not str(data.get("notes", "")).strip():
            raise error("Informe a checagem e observação da dose.")
        scheduled = stamp.isoformat(timespec="minutes")
        for row in db().execute("SELECT payload FROM workflow_events WHERE record_id=? AND kind='administration'", (rid,)):
            if decrypt(row[0])["scheduled_at"] == scheduled:
                raise error("Dose já checada neste horário.")
        event(rid, "administration", dict(scheduled_at=scheduled, outcome=data["outcome"], notes=str(data["notes"])[:3000], medication=r["medication"], dose=r["dose"]))
        db().commit()
        return jsonify(ok=True), 201

    @app.post("/api/assets/<int:rid>/events")
    @roles("estoque", "gestor")
    def asset_event(rid):
        db().execute("BEGIN IMMEDIATE")
        r = authorized_record(rid)
        if not r or r["module"] != "assets":
            return jsonify(error="Bem não disponível."), 404
        data = request.get_json(silent=True) or {}
        if data.get("version") != r["version"]:
            return jsonify(error="Bem alterado. Recarregue antes de continuar."), 409
        kind = data.get("kind")
        if kind not in ("Transferência", "Inventário") or not str(data.get("notes", "")).strip():
            raise error("Informe tipo e observações do evento patrimonial.")
        payload = decrypt(db().execute("SELECT payload FROM records WHERE id=?", (rid,)).fetchone()[0])
        details = dict(notes=str(data["notes"])[:3000], previous_unit=r["unit_id"], previous_responsible=r["responsible"])
        if kind == "Transferência":
            if r["status"] == "Baixado":
                raise error("Bem baixado não pode ser transferido.")
            unit = db().execute("SELECT id FROM units WHERE id=?", (data.get("unit_id"),)).fetchone()
            if not unit or not str(data.get("responsible", "")).strip():
                raise error("Informe unidade e responsável de destino.")
            payload.update(unit_id=unit["id"], responsible=str(data["responsible"]).strip()[:200])
            details.update(unit_id=unit["id"], responsible=payload["responsible"])
        else:
            if data.get("condition") not in ("Localizado", "Divergência", "Não localizado"):
                raise error("Informe o resultado do inventário.")
            details["condition"] = data["condition"]
        snapshot(rid)
        db().execute("UPDATE records SET payload=?,unit_id=?,version=version+1,updated_at=? WHERE id=?", (encrypt(payload), payload["unit_id"], now(), rid))
        snapshot(rid); event(rid, kind, details); db().commit()
        return jsonify(ok=True)

    @app.get("/api/assets/valuation")
    @roles("estoque", "gestor")
    def valuation():
        try:
            on = date.fromisoformat(request.args.get("date", date.today().isoformat()))
        except ValueError:
            raise error("Data de avaliação inválida.")
        result = []
        for r in records("assets"):
            acquired = date.fromisoformat(r["acquisition_date"])
            if acquired > on:
                continue
            months = max(0, (on.year - acquired.year) * 12 + on.month - acquired.month - (on.day < acquired.day))
            residual = r.get("residual_value") or 0
            life = r.get("useful_life") or 0
            depreciation = round((r["value"] - residual) * min(months, life) / life, 2) if life else None
            result.append(dict(id=r["id"], tag=r["tag"], name=r["name"], value=r["value"], depreciation=depreciation, book_value=round(r["value"] - depreciation, 2) if depreciation is not None else None))
        audit("read", "asset_valuation"); db().commit()
        return jsonify(date=on.isoformat(), method="Linear mensal, parâmetros informados no cadastro", items=result)

    @app.post("/api/records/<int:rid>/comments")
    def comment(rid):
        db().execute("BEGIN IMMEDIATE")
        r = authorized_record(rid)
        if not r or r["module"] not in ("support", "training", "judicial", "regulation"):
            return jsonify(error="Registro não disponível."), 404
        text = str((request.get_json(silent=True) or {}).get("text", "")).strip()
        if not text or len(text) > 3000:
            raise error("Informe comentário de até 3.000 caracteres.")
        event(rid, "comment", dict(text=text)); db().commit()
        return jsonify(ok=True), 201

    @app.post("/api/stock/<int:rid>/transfer")
    def transfer_stock(rid):
        db().execute("BEGIN IMMEDIATE")
        r = authorized_record(rid)
        if not r or r["module"] not in ("pharmacy", "warehouse"):
            return jsonify(error="Lote não disponível."), 404
        data = request.get_json(silent=True) or {}
        try:
            amount = int(data.get("quantity", 0))
            if amount < 1 or str(amount) != str(data["quantity"]):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise error("Quantidade deve ser inteira e positiva.")
        unit = db().execute("SELECT id FROM units WHERE id=?", (data.get("unit_id"),)).fetchone()
        reason = str(data.get("reason", "")).strip()
        if not unit or unit["id"] == r["unit_id"] or not reason:
            raise error("Informe unidade de destino diferente e motivo da transferência.")
        if r["status"] != "Ativo" or (r.get("expiry") and r["expiry"] < date.today().isoformat()) or amount > r["quantity"]:
            raise error("Lote bloqueado, vencido ou com saldo insuficiente.")
        dest = next((v for v in records(r["module"]) if v["unit_id"] == unit["id"] and all(v.get(k) == r.get(k) for k in ("name", "batch", "expiry", "measure")) and v["status"] == "Ativo"), None)
        if not dest:
            payload = decrypt(db().execute("SELECT payload FROM records WHERE id=?", (rid,)).fetchone()[0])
            payload.update(quantity=0, unit_id=unit["id"])
            cur = db().execute("INSERT INTO records(module,unit_id,payload,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (r["module"], unit["id"], encrypt(payload), "Ativo", g.user["id"], now(), now()))
            dest = record_dict(db().execute("SELECT * FROM records WHERE id=?", (cur.lastrowid,)).fetchone())
        for item, delta, kind in ((r, -amount, "Transferência saída"), (dest, amount, "Transferência entrada")):
            snapshot(item["id"])
            payload = decrypt(db().execute("SELECT payload FROM records WHERE id=?", (item["id"],)).fetchone()[0])
            payload["quantity"] += delta
            db().execute("UPDATE records SET payload=?,version=version+1,updated_at=? WHERE id=?", (encrypt(payload), now(), item["id"]))
            db().execute("INSERT INTO movements(record_id,quantity,kind,reason,created_by,created_at) VALUES(?,?,?,?,?,?)", (item["id"], amount, kind, encrypt(f'{reason} · lotes #{rid} → #{dest["id"]}'), g.user["id"], now()))
            snapshot(item["id"])
        audit("stock_transfer", r["module"], rid); db().commit()
        return jsonify(source_id=rid, destination_id=dest["id"], quantity=amount)
