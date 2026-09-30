import csv
import io
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from cryptography.fernet import Fernet
from flask import Flask, Response, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from .catalog import MODULES, ROLE_LABELS, can_access
from .db import SCHEMA, audit, db, decrypt, encrypt, identity_hash, now, patient_dict, record_dict

ROOT = Path(__file__).resolve().parent.parent

class ValidationError(Exception):
    pass

def create_app(config=None):
    app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="/static")
    app.json.sort_keys=False
    instance = Path((config or {}).get("INSTANCE", ROOT / "instance"))
    instance.mkdir(parents=True, exist_ok=True)
    secret_file = instance / "keys.json"
    if not secret_file.exists():
        secret_file.write_text(json.dumps({"session":secrets.token_hex(32),"encryption":Fernet.generate_key().decode(),"hash":secrets.token_hex(32)}))
    keys = json.loads(secret_file.read_text())
    app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY",keys["session"]), DATABASE=str(instance / "saude.db"), INSTANCE=str(instance), HASH_KEY=bytes.fromhex(keys["hash"]), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.environ.get("HTTPS_ONLY")=="1", PERMANENT_SESSION_LIFETIME=timedelta(minutes=30), MAX_CONTENT_LENGTH=2*1024*1024, DEMO=os.environ.get("APP_DEMO","1")=="1")
    if config:
        app.config.update(config)
    app.extensions["cipher"] = Fernet(os.environ.get("DATA_KEY",keys["encryption"]).encode())

    @app.teardown_appcontext
    def close_db(error):
        conn = g.pop("db",None)
        if conn:
            conn.close()

    @app.errorhandler(ValidationError)
    def validation_error(error):
        return jsonify(error=str(error)),400

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity_error(error):
        db().rollback()
        return jsonify(error="Já existe um registro com esta identificação, ou a referência informada é inválida."),409

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(error="O arquivo excede o limite de 2 MB."),413

    @app.before_request
    def protect():
        if not request.path.startswith("/api/"):
            return
        if request.path in ("/api/session","/api/login","/api/health"):
            if request.path=="/api/login" and request.method=="POST" and not valid_csrf():
                return jsonify(error="Sessão expirada. Recarregue a página."),403
            return
        uid = session.get("uid")
        user = db().execute("SELECT * FROM users WHERE id=? AND active=1",(uid,)).fetchone() if uid else None
        if not user:
            return jsonify(error="Entre na sua conta para continuar."),401
        g.user = dict(user)
        if request.method in ("POST","PATCH","DELETE","PUT") and not valid_csrf():
            return jsonify(error="Token de segurança inválido. Recarregue a página."),403
        if user["role"]=="cidadao" and not request.path.startswith(("/api/citizen","/api/logout")):
            return jsonify(error="Este recurso é restrito à equipe de saúde."),403

    def valid_csrf():
        return bool(session.get("csrf")) and secrets.compare_digest(request.headers.get("X-CSRF-Token",""),session["csrf"])

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["X-Frame-Options"]="DENY"
        response.headers["Referrer-Policy"]="same-origin"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"]="no-store"
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
        return response

    def roles(*allowed):
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args,**kwargs):
                if g.user["role"]!="admin" and g.user["role"] not in allowed:
                    return jsonify(error="Seu perfil não tem acesso a esta funcionalidade."),403
                return fn(*args,**kwargs)
            return wrapper
        return decorator

    def module_access(key):
        if key not in MODULES:
            raise ValidationError("Módulo desconhecido.")
        return can_access(g.user["role"],key)

    @app.get("/")
    @app.get("/cidadao")
    def index():
        return send_from_directory(ROOT / "static","index.html")

    @app.get("/api/health")
    def health():
        db().execute("SELECT 1")
        return jsonify(status="ok")

    @app.get("/api/session")
    def get_session():
        session.setdefault("csrf",secrets.token_urlsafe(32))
        user = db().execute("SELECT id,name,username,role,patient_id FROM users WHERE id=? AND active=1",(session.get("uid"),)).fetchone()
        return jsonify(csrf=session["csrf"],user=dict(user) if user else None,demo=app.config["DEMO"],roles=ROLE_LABELS)

    @app.post("/api/login")
    def login():
        data=request.get_json(silent=True) or {}
        username=str(data.get("username","")).strip().lower()[:120]
        key=identity_hash(username+"|"+(request.remote_addr or ""))
        attempt=db().execute("SELECT * FROM login_attempts WHERE key=?",(key,)).fetchone()
        if attempt and attempt["failures"]>=5 and time.time()-attempt["last_at"]<300:
            return jsonify(error="Muitas tentativas. Aguarde 5 minutos."),429
        user=db().execute("SELECT * FROM users WHERE username=? AND active=1",(username,)).fetchone()
        if not user or not check_password_hash(user["password"],str(data.get("password",""))):
            failures=(attempt["failures"]+1) if attempt and time.time()-attempt["last_at"]<300 else 1
            db().execute("INSERT INTO login_attempts VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET failures=excluded.failures,last_at=excluded.last_at",(key,failures,time.time()))
            db().commit()
            return jsonify(error="Usuário ou senha inválidos."),401
        session.clear()
        session.update(uid=user["id"],csrf=secrets.token_urlsafe(32))
        session.permanent=True
        db().execute("DELETE FROM login_attempts WHERE key=?",(key,))
        audit("login","users",user["id"])
        db().commit()
        return jsonify(csrf=session["csrf"],user={k:user[k] for k in ("id","name","username","role","patient_id")})

    @app.post("/api/logout")
    def logout():
        audit("logout","users",session.get("uid"))
        db().commit()
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/meta")
    def meta():
        modules={k:v for k,v in MODULES.items() if can_access(g.user["role"],k)}
        units=[dict(r) for r in db().execute("SELECT * FROM units ORDER BY id")]
        professionals=[dict(r) for r in db().execute("SELECT id,name,role FROM users WHERE role IN ('clinico','admin') AND active=1")]
        return jsonify(modules=modules,units=units,professionals=professionals,roles=ROLE_LABELS)

    @app.post("/api/units")
    @roles("gestor")
    def add_unit():
        data=request.get_json(silent=True) or {}
        name=str(data.get("name","")).strip()
        kind=str(data.get("kind","")).strip()
        cnes=str(data.get("cnes","")).strip() or None
        if len(name)<3 or not kind or (cnes and not re.fullmatch(r"\d{7}",cnes)):
            raise ValidationError("Informe nome, tipo e CNES válido com 7 dígitos, quando disponível.")
        cur=db().execute("INSERT INTO units(name,kind,cnes) VALUES(?,?,?)",(name,kind,cnes))
        audit("create","units",cur.lastrowid);db().commit()
        return jsonify(id=cur.lastrowid),201

    @app.patch("/api/units/<int:uid>")
    @roles("gestor")
    def edit_unit(uid):
        data=request.get_json(silent=True) or {}
        name=str(data.get("name","")).strip();kind=str(data.get("kind","")).strip()
        cnes=str(data.get("cnes","")).strip() or None
        if len(name)<3 or not kind or (cnes and not re.fullmatch(r"\d{7}",cnes)):
            raise ValidationError("Informe nome, tipo e CNES válido com 7 dígitos, quando disponível.")
        cur=db().execute("UPDATE units SET name=?,kind=?,cnes=? WHERE id=?",(name,kind,cnes,uid))
        if cur.rowcount!=1:return jsonify(error="Unidade não encontrada."),404
        audit("update","units",uid);db().commit()
        return jsonify(ok=True)

    def validate_patient(data):
        result={k:str(data.get(k,"")).strip() for k in ("name","birth_date","cpf","cns","phone","address","sex","mother","allergies")}
        if len(result["name"])<3:
            raise ValidationError("Informe o nome completo do paciente.")
        try:
            birthday=date.fromisoformat(result["birth_date"])
            if birthday>date.today() or birthday.year<1900:
                raise ValueError()
        except ValueError:
            raise ValidationError("Data de nascimento inválida.")
        result["cpf"]=re.sub(r"\D","",result["cpf"])
        result["cns"]=re.sub(r"\D","",result["cns"])
        if not result["cpf"] and not result["cns"]:
            raise ValidationError("Informe CPF ou CNS para identificação única.")
        if result["cpf"]:
            cpf=result["cpf"]
            if len(cpf)!=11 or len(set(cpf))==1 or any((sum(int(cpf[j])*(n+1-j) for j in range(n))*10%11%10)!=int(cpf[n]) for n in (9,10)):
                raise ValidationError("CPF inválido. Verifique os dígitos.")
        if result["cns"] and (len(result["cns"])!=15 or len(set(result["cns"]))==1 or sum(int(v)*(15-i) for i,v in enumerate(result["cns"]))%11!=0):
            raise ValidationError("CNS inválido. Verifique os 15 dígitos.")
        if any(len(v)>3000 for v in result.values()):
            raise ValidationError("Um dos campos excede o tamanho permitido.")
        return result

    def insert_patient(data):
        value=validate_patient(data)
        for row in db().execute("SELECT payload FROM patients"):
            existing=decrypt(row[0])
            if any(value[k] and value[k]==existing.get(k) for k in ("cpf","cns")):
                raise ValidationError("Paciente já cadastrado com este CPF ou CNS.")
        cur=db().execute("INSERT INTO patients(payload,identity_hash,created_at) VALUES(?,?,?)",(encrypt(value),identity_hash(value["cpf"] or value["cns"]),now()))
        return cur.lastrowid

    @app.get("/api/patients")
    def patients():
        # Cadastros mínimos são compartilhados; dados clínicos exigem perfil assistencial.
        query=request.args.get("q","").casefold()
        result=[]
        for row in db().execute("SELECT * FROM patients ORDER BY id DESC"):
            p=patient_dict(row)
            if query and query not in " ".join(str(v) for v in p.values()).casefold():
                continue
            if g.user["role"] not in ("admin","clinico","gestor"):
                p.pop("allergies",None)
            result.append(p)
        audit("read","patients")
        db().commit()
        return jsonify(items=result)

    @app.post("/api/patients")
    @roles("recepcao","clinico","gestor")
    def add_patient():
        db().execute("BEGIN IMMEDIATE")
        pid=insert_patient(request.get_json(silent=True) or {})
        audit("create","patients",pid)
        db().commit()
        return jsonify(id=pid),201

    @app.get("/api/patients/<int:pid>/timeline")
    @roles("clinico","gestor")
    def timeline(pid):
        row=db().execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone()
        if not row:
            return jsonify(error="Paciente não encontrado."),404
        entries=[record_dict(r) for r in db().execute("SELECT * FROM records WHERE patient_id=? ORDER BY created_at DESC,id DESC",(pid,)) if can_access(g.user["role"],r["module"])]
        movements=[dict(r) for r in db().execute("SELECT id,record_id,quantity,kind,created_at FROM movements WHERE patient_id=? ORDER BY id DESC",(pid,))]
        audit("read_clinical","patients",pid)
        db().commit()
        return jsonify(patient=patient_dict(row),items=entries,movements=movements)

    @app.patch("/api/patients/<int:pid>")
    @roles("recepcao","clinico","gestor")
    def edit_patient(pid):
        db().execute("BEGIN IMMEDIATE")
        row=db().execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone()
        if not row:return jsonify(error="Paciente não encontrado."),404
        data=request.get_json(silent=True) or {}
        if data.get("version")!=row["version"]:return jsonify(error="Cadastro alterado por outra pessoa. Recarregue antes de editar."),409
        old=decrypt(row["payload"])
        if g.user["role"]=="recepcao":data.pop("allergies",None)
        value=validate_patient({**old,**data})
        for other in db().execute("SELECT payload FROM patients WHERE id<>?",(pid,)):
            existing=decrypt(other[0])
            if any(value[k] and value[k]==existing.get(k) for k in ("cpf","cns")):
                raise ValidationError("Já existe outro paciente com este CPF ou CNS.")
        db().execute("UPDATE patients SET payload=?,identity_hash=?,version=version+1 WHERE id=?",(encrypt(value),identity_hash(value["cpf"] or value["cns"]),pid))
        audit("update","patients",pid);db().commit()
        return jsonify(ok=True)

    def validate_record(key,data,old=None):
        spec=MODULES[key]
        result={}
        for f in spec["fields"]:
            value=data.get(f["key"], "")
            if f["required"] and (value is None or str(value).strip()==""):
                raise ValidationError(f'Preencha o campo {f["label"]}.')
            if value is None or str(value).strip()=="":
                result[f["key"]]=""
                continue
            if f["type"] in ("patient","unit","professional","vehicle"):
                try: value=int(value)
                except (ValueError,TypeError): raise ValidationError(f'Referência inválida: {f["label"]}.')
                table={"patient":"patients","unit":"units","professional":"users","vehicle":"records"}[f["type"]]
                row=db().execute(f"SELECT * FROM {table} WHERE id=?",(value,)).fetchone()
                if not row or (f["type"]=="vehicle" and row["module"]!="fleet") or (f["type"]=="professional" and (not row["active"] or row["role"] not in ("admin","clinico"))):
                    raise ValidationError(f'Referência inexistente: {f["label"]}.')
            elif f["type"]=="number":
                try:
                    value=float(value)
                    if not 0<=value<=1e9: raise ValueError()
                    if f["key"] in ("quantity","minimum","capacity","mileage") and value!=int(value): raise ValueError()
                    if value==int(value): value=int(value)
                except (TypeError,ValueError,OverflowError): raise ValidationError(f'Valor numérico inválido: {f["label"]}.')
            elif f["type"] in ("date","month","time"):
                try: datetime.strptime(str(value),{"date":"%Y-%m-%d","month":"%Y-%m","time":"%H:%M"}[f["type"]])
                except ValueError: raise ValidationError(f'Data ou horário inválido: {f["label"]}.')
            elif f["type"]=="select" and value not in f["options"]:
                raise ValidationError(f'Opção inválida: {f["label"]}.')
            else:
                value=str(value).strip()
                if len(value)>10000: raise ValidationError("Texto excede o limite de 10.000 caracteres.")
            result[f["key"]]=value
        if key in ("pharmacy","warehouse") and old:
            result["quantity"]=old["quantity"]
        if key=="billing" and (not re.fullmatch(r"\d{10}",result["code"]) or result["quantity"]<1):
            raise ValidationError("Informe código de procedimento com 10 dígitos e quantidade positiva.")
        if key=="hospital":
            if data.get("status")=="Alta" and not result.get("discharge_date"):
                raise ValidationError("Informe a data da alta.")
            if result.get("discharge_date") and result["discharge_date"]<result["date"]:
                raise ValidationError("A alta não pode anteceder a admissão.")
            active=db().execute("SELECT * FROM records WHERE module='hospital' AND status IN ('Internado','Em observação')")
            if data.get("status",spec["statuses"][0]) in ("Internado","Em observação"):
                for row in active:
                    r=record_dict(row)
                    if old and r["id"]==old["id"]: continue
                    if r.get("unit_id")==result["unit_id"] and r["bed"].casefold()==result["bed"].casefold():
                        raise ValidationError("Este leito já está ocupado.")
        if key=="transport" and data.get("status","Solicitado") not in ("Cancelado","Concluído"):
            vehicle=record_dict(db().execute("SELECT * FROM records WHERE id=?",(result["vehicle_id"],)).fetchone())
            if vehicle["status"] in ("Em manutenção","Inativo"):
                raise ValidationError("Veículo indisponível para transporte.")
            occupied=1+bool(result.get("companion"))
            for row in db().execute("SELECT * FROM records WHERE module='transport' AND status NOT IN ('Cancelado','Concluído')"):
                other=record_dict(row)
                if old and other["id"]==old["id"]:continue
                if other["date"]==result["date"] and other["time"]==result["time"]:
                    if other["patient_id"]==result["patient_id"]:
                        raise ValidationError("Este paciente já tem transporte no mesmo horário.")
                    if other["vehicle_id"]==result["vehicle_id"]:
                        if other["destination"].casefold()!=result["destination"].casefold():
                            raise ValidationError("Veículo já programado para outro destino neste horário.")
                        occupied+=1+bool(other.get("companion"))
            if occupied>vehicle["capacity"]:
                raise ValidationError("Capacidade do veículo excedida, incluindo acompanhantes.")
        if key=="appointments" and data.get("status","Agendado") not in ("Cancelado","Faltou"):
            for row in db().execute("SELECT * FROM records WHERE module='appointments' AND status NOT IN ('Cancelado','Faltou')"):
                r=record_dict(row)
                if old and r["id"]==old["id"]: continue
                if r["date"]==result["date"] and r["time"]==result["time"] and (r["professional_id"]==result["professional_id"] or r["patient_id"]==result["patient_id"]):
                    raise ValidationError("Já existe um agendamento para este paciente ou profissional neste horário.")
        return result

    @app.get("/api/records/<key>")
    def records(key):
        if not module_access(key): return jsonify(error="Acesso não permitido."),403
        result=[record_dict(r) for r in db().execute("SELECT * FROM records WHERE module=? ORDER BY id DESC",(key,))]
        audit("read",key)
        db().commit()
        return jsonify(items=result)

    @app.post("/api/records/<key>")
    def create_record(key):
        if not module_access(key): return jsonify(error="Acesso não permitido."),403
        data=request.get_json(silent=True) or {}
        db().execute("BEGIN IMMEDIATE")
        value=validate_record(key,data)
        status=data.get("status",MODULES[key]["statuses"][0])
        if status not in MODULES[key]["statuses"]: raise ValidationError("Situação inválida.")
        cur=db().execute("INSERT INTO records(module,patient_id,unit_id,payload,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(key,value.get("patient_id") or None,value.get("unit_id") or None,encrypt(value),status,g.user["id"],now(),now()))
        rid=cur.lastrowid
        audit("create",key,rid)
        db().commit()
        return jsonify(id=rid),201

    @app.patch("/api/records/<key>/<int:rid>")
    def edit_record(key,rid):
        if not module_access(key): return jsonify(error="Acesso não permitido."),403
        db().execute("BEGIN IMMEDIATE")
        row=db().execute("SELECT * FROM records WHERE module=? AND id=?",(key,rid)).fetchone()
        if not row: return jsonify(error="Registro não encontrado."),404
        old=record_dict(row)
        data=request.get_json(silent=True) or {}
        if data.get("version")!=old["version"]:
            return jsonify(error="Este registro foi atualizado por outra pessoa. Recarregue antes de salvar."),409
        if key=="encounters" and old["status"]=="Finalizado":
            return jsonify(error="Um registro clínico finalizado é imutável. Crie uma nova evolução para complementá-lo."),409
        merged={**old,**data}
        value=validate_record(key,merged,old)
        status=merged["status"]
        if status not in MODULES[key]["statuses"]: raise ValidationError("Situação inválida.")
        db().execute("UPDATE records SET payload=?,patient_id=?,unit_id=?,status=?,version=version+1,updated_at=? WHERE id=?",(encrypt(value),value.get("patient_id") or None,value.get("unit_id") or None,status,now(),rid))
        audit("update",key,rid)
        db().commit()
        return jsonify(ok=True)

    @app.post("/api/stock/<int:rid>/move")
    def stock_move(rid):
        db().execute("BEGIN IMMEDIATE")
        row=db().execute("SELECT * FROM records WHERE id=? AND module IN ('pharmacy','warehouse')",(rid,)).fetchone()
        if not row: return jsonify(error="Lote não encontrado."),404
        if not module_access(row["module"]): return jsonify(error="Acesso não permitido."),403
        item=record_dict(row)
        data=request.get_json(silent=True) or {}
        try:
            amount=int(data.get("quantity",0))
            if amount<=0 or str(amount)!=str(data.get("quantity")): raise ValueError()
        except (ValueError,TypeError): raise ValidationError("Informe uma quantidade inteira positiva.")
        kind=data.get("kind")
        if kind not in ("Entrada","Saída","Dispensação"): raise ValidationError("Tipo de movimentação inválido.")
        if item["status"]=="Bloqueado": raise ValidationError("Este lote está bloqueado.")
        if kind!="Entrada" and item.get("expiry") and item["expiry"]<date.today().isoformat(): raise ValidationError("Não é permitida saída de lote vencido.")
        if kind!="Entrada" and amount>item["quantity"]: raise ValidationError("Saldo insuficiente no lote.")
        pid=data.get("patient_id") or None
        if kind=="Dispensação" and not pid: raise ValidationError("Vincule a dispensação a um paciente.")
        if pid and not db().execute("SELECT 1 FROM patients WHERE id=?",(pid,)).fetchone(): raise ValidationError("Paciente inexistente.")
        reason=str(data.get("reason","")).strip()
        if not reason: raise ValidationError("Informe o motivo / documento da movimentação.")
        payload=decrypt(row["payload"])
        payload["quantity"]+=amount if kind=="Entrada" else -amount
        db().execute("UPDATE records SET payload=?,version=version+1,updated_at=? WHERE id=?",(encrypt(payload),now(),rid))
        db().execute("INSERT INTO movements(record_id,patient_id,quantity,kind,reason,created_by,created_at) VALUES(?,?,?,?,?,?,?)",(rid,pid,amount,kind,encrypt(reason),g.user["id"],now()))
        audit("stock_move",row["module"],rid)
        db().commit()
        return jsonify(quantity=payload["quantity"])

    @app.get("/api/stock/<int:rid>/movements")
    def movements(rid):
        row=db().execute("SELECT module FROM records WHERE id=?",(rid,)).fetchone()
        if not row or row["module"] not in ("pharmacy","warehouse"): return jsonify(error="Lote não encontrado."),404
        if not module_access(row["module"]): return jsonify(error="Acesso não permitido."),403
        result=[]
        for row in db().execute("SELECT * FROM movements WHERE record_id=? ORDER BY id DESC",(rid,)):
            value=dict(row); value["reason"]=decrypt(value["reason"]); result.append(value)
        audit("read","movements",rid); db().commit()
        return jsonify(items=result)

    @app.get("/api/dashboard")
    def dashboard():
        unit=request.args.get("unit","")
        try:days=max(1,min(365,int(request.args.get("days","30"))))
        except ValueError:raise ValidationError("Período inválido.")
        today=date.today()
        since=(today-timedelta(days=days-1)).isoformat()
        rows=[record_dict(r) for r in db().execute("SELECT * FROM records") if can_access(g.user["role"],r["module"])]
        if unit: rows=[r for r in rows if str(r.get("unit_id",""))==unit]
        appointments=[r for r in rows if r["module"]=="appointments" and since<=r["date"]<=today.isoformat()]
        waiting=[r for r in rows if r["module"]=="regulation" and r["status"] in ("Aguardando","Em análise")]
        low=[r for r in rows if r["module"] in ("pharmacy","warehouse") and r["quantity"]<=r["minimum"]]
        judicial=[r for r in rows if r["module"]=="judicial" and r["status"] not in ("Concluído","Cancelado")]
        totals=[]
        for i in range(min(days,14)-1,-1,-1):
            day=(today-timedelta(days=i)).isoformat()
            totals.append(dict(date=day,total=sum(r["date"]==day for r in appointments),completed=sum(r["date"]==day and r["status"]=="Concluído" for r in appointments)))
        distribution={}
        for r in appointments: distribution[r["specialty"]]=distribution.get(r["specialty"],0)+1
        today_agenda=[r for r in rows if r["module"]=="appointments" and r["date"]==today.isoformat()]
        alerts=[dict(kind="warning",title="Estoque abaixo do mínimo",text=f'{r["name"]} · {r["quantity"]} em estoque',module=r["module"]) for r in low]
        alerts += [dict(kind="danger",title="Prazo judicial",text=f'{r["case_number"]} · prazo {r["deadline"]}',module="judicial") for r in judicial if r["deadline"]<=(today+timedelta(days=7)).isoformat()]
        patients_count=db().execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        audit("read","dashboard"); db().commit()
        return jsonify(patients=patients_count,appointments=len(appointments),waiting=len(waiting),low_stock=len(low),series=totals,distribution=distribution,agenda=sorted(today_agenda,key=lambda x:x["time"]),alerts=alerts,units=db().execute("SELECT COUNT(*) FROM units").fetchone()[0],completed=sum(r["status"]=="Concluído" for r in appointments),period_days=days)

    @app.get("/api/export/<key>")
    def export_records(key):
        if not module_access(key): return jsonify(error="Acesso não permitido."),403
        rows=[record_dict(r) for r in db().execute("SELECT * FROM records WHERE module=? ORDER BY id",(key,))]
        columns=["id"]+[f["key"] for f in MODULES[key]["fields"]]+["status","created_at"]
        output=io.StringIO(); writer=csv.writer(output,delimiter=";"); writer.writerow(columns)
        for row in rows:
            values=[]
            for key_ in columns:
                value=str(row.get(key_,""))
                if value.startswith(("=","+","-","@","\t","\r")): value="'"+value
                values.append(value)
            writer.writerow(values)
        audit("export",key); db().commit()
        return Response("\ufeff"+output.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="integra-{key}.csv"'})

    @app.post("/api/migration/validate")
    @roles("gestor")
    def migration_validate():
        rows=read_import()
        return jsonify(**inspect_import(rows))

    def read_import():
        file=request.files.get("file")
        if not file: raise ValidationError("Selecione um arquivo CSV UTF-8.")
        try: rows=list(csv.DictReader(io.StringIO(file.read().decode("utf-8-sig")),delimiter=";"))
        except (UnicodeError,csv.Error): raise ValidationError("Arquivo inválido. Use CSV UTF-8 separado por ponto e vírgula.")
        if not rows or len(rows)>1000: raise ValidationError("O arquivo deve conter entre 1 e 1.000 pacientes.")
        return rows

    def inspect_import(rows):
        errors=[]; seen=set()
        existing=[decrypt(r[0]) for r in db().execute("SELECT payload FROM patients")]
        for i,row in enumerate(rows,2):
            try:
                value=validate_patient(row)
                identifiers=[(k,value[k]) for k in ("cpf","cns") if value[k]]
                if any(pair in seen for pair in identifiers) or any(any(v.get(k)==val for k,val in identifiers) for v in existing): raise ValidationError("CPF/CNS duplicado.")
                seen.update(identifiers)
            except ValidationError as exc: errors.append(dict(line=i,error=str(exc)))
        return dict(total=len(rows),valid=len(rows)-len(errors),errors=errors)

    @app.post("/api/migration/import")
    @roles("gestor")
    def migration_import():
        rows=read_import()
        db().execute("BEGIN IMMEDIATE")
        report=inspect_import(rows)
        if report["errors"]: return jsonify(error="Corrija os erros antes de importar.",**report),400
        for row in rows: insert_patient(row)
        audit("import","patients",len(rows)); db().commit()
        return jsonify(imported=len(rows))

    @app.get("/api/audit")
    @roles("gestor")
    def audit_log():
        entries=[dict(r) for r in db().execute("SELECT a.*,u.name AS actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 250")]
        previous="0"*64; valid=True
        for row in db().execute("SELECT * FROM audit ORDER BY id"):
            content=json.dumps([row["actor"],row["action"],row["entity"],row["entity_id"],row["created_at"],row["previous_hash"]],ensure_ascii=False)
            if row["previous_hash"]!=previous or identity_hash(content)!=row["hash"]: valid=False
            previous=row["hash"]
        audit("read","audit"); db().commit()
        return jsonify(items=entries,chain_valid=valid)

    @app.get("/api/users")
    @roles()
    def users():
        return jsonify(items=[dict(r) for r in db().execute("SELECT id,name,username,role,active,patient_id FROM users ORDER BY id")])

    @app.post("/api/users")
    @roles()
    def add_user():
        data=request.get_json(silent=True) or {}
        if data.get("role") not in ROLE_LABELS: raise ValidationError("Perfil inválido.")
        if len(str(data.get("password","")))<12: raise ValidationError("A senha deve ter pelo menos 12 caracteres.")
        if len(str(data.get("name","")))<3 or not re.fullmatch(r"[a-z0-9_.@-]{3,120}",str(data.get("username",""))): raise ValidationError("Informe nome e usuário válidos.")
        pid=data.get("patient_id") or None
        if data["role"]=="cidadao" and not pid: raise ValidationError("Vincule o cidadão ao seu cadastro de paciente.")
        cur=db().execute("INSERT INTO users(name,username,password,role,patient_id) VALUES(?,?,?,?,?)",(data["name"],data["username"],generate_password_hash(data["password"]),data["role"],pid))
        audit("create","users",cur.lastrowid); db().commit()
        return jsonify(id=cur.lastrowid),201

    @app.patch("/api/users/<int:uid>")
    @roles()
    def disable_user(uid):
        if uid==g.user["id"]: raise ValidationError("Você não pode desativar a própria conta.")
        data=request.get_json(silent=True) or {}
        db().execute("UPDATE users SET active=? WHERE id=?",(1 if data.get("active") else 0,uid))
        audit("access_change","users",uid); db().commit()
        return jsonify(ok=True)

    @app.get("/api/citizen")
    @roles("cidadao")
    def citizen():
        pid=g.user["patient_id"]
        row=db().execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone()
        if not row: return jsonify(error="Conta sem paciente vinculado."),409
        rows=[record_dict(r) for r in db().execute("SELECT * FROM records WHERE patient_id=? AND module IN ('appointments','messages','regulation','exams') ORDER BY id DESC",(pid,))]
        # O portal expõe apenas os campos necessários a cada serviço.
        allowed={"appointments":["date","time","specialty","unit_id"],"messages":["subject","body"],"regulation":["specialty","date","scheduled_date"],"exams":["procedure","date","result"]}
        items=[{k:r[k] for k in ["id","module","status"]+allowed[r["module"]] if k in r} for r in rows]
        for item in items:
            if item["module"]=="exams" and item["status"]!="Laudado":item.pop("result",None)
        audit("read_own","citizen",pid); db().commit()
        return jsonify(patient={k:patient_dict(row)[k] for k in ("id","name")},items=items,units=[dict(r) for r in db().execute("SELECT * FROM units")])

    @app.post("/api/citizen/<int:rid>/action")
    @roles("cidadao")
    def citizen_action(rid):
        db().execute("BEGIN IMMEDIATE")
        row=db().execute("SELECT * FROM records WHERE id=? AND patient_id=?",(rid,g.user["patient_id"])).fetchone()
        if not row: return jsonify(error="Registro não encontrado."),404
        data=request.get_json(silent=True) or {}
        valid=(row["module"]=="messages" and data.get("action")=="read") or (row["module"]=="appointments" and data.get("action") in ("confirm","cancel") and row["status"] in ("Agendado","Confirmado"))
        if not valid: raise ValidationError("Esta ação não está disponível para o registro.")
        status={"read":"Lida","confirm":"Confirmado","cancel":"Cancelado"}[data["action"]]
        db().execute("UPDATE records SET status=?,version=version+1,updated_at=? WHERE id=?",(status,now(),rid))
        audit("citizen_action",row["module"],rid); db().commit()
        return jsonify(ok=True)

    @app.get("/api/compliance")
    @roles("gestor")
    def compliance():
        return jsonify(json.loads((ROOT / "docs" / "aderencia.json").read_text(encoding="utf-8")))

    @app.get("/api/integrations")
    @roles("gestor","faturamento")
    def integrations():
        return jsonify(items=[dict(name=n,status="Não homologada",description=d) for n,d in [("e-SUS APS","Requer implementação e validação do leiaute oficial de intercâmbio."),("SISAB","Requer validação do fluxo oficial de envio e retorno da produção."),("CNES","Requer carga oficial dos estabelecimentos e profissionais."),("BPA","Requer geração e homologação dos arquivos no aplicativo oficial."),("SIA/SUS","Requer validação da produção e retorno de processamento."),("Ministério da Saúde","Demais sistemas devem ser definidos com a equipe municipal.")]])

    with app.app_context():
        db().executescript(SCHEMA)
        if "version" not in [r[1] for r in db().execute("PRAGMA table_info(patients)")]:
            db().execute("ALTER TABLE patients ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        db().commit()
    return app
