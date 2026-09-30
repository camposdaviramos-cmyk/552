import csv
import io
import json
import sqlite3
from datetime import date,timedelta

import pytest
from werkzeug.security import generate_password_hash
from saude.app import create_app
from saude.db import db,encrypt,identity_hash,now
from seed import cpf_for
from backup import create_backup,restore_backup

@pytest.fixture
def app(tmp_path):
    app=create_app({"INSTANCE":str(tmp_path),"TESTING":True})
    with app.app_context():
        db().execute("INSERT INTO units(name,kind) VALUES('UBS Teste','Atenção básica')")
        for i in (1,2):
            p=dict(name=f"Paciente Teste {i}",birth_date="1985-01-01",cpf=cpf_for(800000000+i),cns="",phone="",address="",mother="",sex="",allergies="")
            db().execute("INSERT INTO patients(payload,identity_hash,created_at) VALUES(?,?,?)",(encrypt(p),identity_hash(p["cpf"]),now()))
        pwd=generate_password_hash("Test@Password2026")
        for name,role,pid in [("admin","admin",None),("clinical","clinico",None),("reception","recepcao",None),("citizen","cidadao",1)]:
            db().execute("INSERT INTO users(name,username,password,role,patient_id) VALUES(?,?,?,?,?)",(name,name,pwd,role,pid))
        db().commit()
    return app

def login(client,username="admin"):
    csrf=client.get('/api/session').json['csrf']
    response=client.post('/api/login',json=dict(username=username,password="Test@Password2026"),headers={'X-CSRF-Token':csrf})
    assert response.status_code==200
    return {'X-CSRF-Token':response.json['csrf']}

def patient(number=99):
    return dict(name="Novo Paciente",birth_date="1990-03-15",cpf=cpf_for(700000000+number),cns="")

def encounter():
    return dict(patient_id=1,unit_id=1,date=date.today().isoformat(),care_type="Atenção básica",subjective="Queixa de teste",objective="Observação de teste",assessment="Avaliação",plan="Plano",status="Finalizado")

def stock(quantity=10,expiry=None):
    return dict(unit_id=1,name="Medicamento Teste",batch="T1",expiry=expiry or (date.today()+timedelta(days=30)).isoformat(),quantity=quantity,minimum=5,measure="Comprimido")

def test_login_csrf_and_role_boundaries(app):
    client=app.test_client()
    assert client.get('/api/patients').status_code==401
    assert client.post('/api/login',json={}).status_code==403
    headers=login(client,"reception")
    assert client.get('/api/records/encounters').status_code==403
    assert client.get('/api/patients/1/timeline').status_code==403
    assert client.get('/api/audit').status_code==403
    assert client.get('/api/users').status_code==403
    assert client.post('/api/users',json={},headers=headers).status_code==403
    assert client.post('/api/patients',json=patient()).status_code==403
    assert client.post('/api/patients',json=patient(),headers=headers).status_code==201

def test_patient_identity_and_encryption(app):
    client=app.test_client();headers=login(client)
    response=client.post('/api/patients',json=patient(),headers=headers)
    assert response.status_code==201
    assert client.post('/api/patients',json=patient(),headers=headers).status_code==400
    assert client.post('/api/patients',json={**patient(12),'cpf':'11111111111'},headers=headers).status_code==400
    assert client.post('/api/patients',json={**patient(13),'birth_date':'2090-01-01'},headers=headers).status_code==400
    with app.app_context():
        payload=db().execute("SELECT payload FROM patients WHERE id=?",(response.json['id'],)).fetchone()[0]
        assert 'Novo Paciente' not in payload and patient()['cpf'] not in payload

def test_finalized_clinical_record_is_immutable(app):
    client=app.test_client();headers=login(client,"clinical")
    response=client.post('/api/records/encounters',json=encounter(),headers=headers)
    assert response.status_code==201
    rid=response.json['id']
    assert client.patch(f'/api/records/encounters/{rid}',json={'version':1,'plan':'Alterado'},headers=headers).status_code==409
    timeline=client.get('/api/patients/1/timeline').json
    assert timeline['items'][0]['plan']=='Plano'

def test_stock_transactions_and_expiration(app):
    client=app.test_client();headers=login(client)
    rid=client.post('/api/records/pharmacy',json=stock(),headers=headers).json['id']
    def move(q,**kwargs):return client.post(f'/api/stock/{rid}/move',json=dict(kind='Dispensação',quantity=q,reason='Prescrição de teste',patient_id=1,**kwargs),headers=headers)
    assert move(11).status_code==400
    assert move(3).json['quantity']==7
    assert move(8).status_code==400
    assert client.get(f'/api/stock/{rid}/movements').json['items'][0]['quantity']==3
    assert client.get('/api/patients/1/timeline').json['movements'][0]['quantity']==3
    old=client.get('/api/records/pharmacy').json['items'][0]
    assert client.patch(f'/api/records/pharmacy/{rid}',json={'version':old['version'],'quantity':999},headers=headers).status_code==200
    assert client.get('/api/records/pharmacy').json['items'][0]['quantity']==7
    expired=client.post('/api/records/pharmacy',json=stock(expiry='2020-01-01'),headers=headers).json['id']
    assert client.post(f'/api/stock/{expired}/move',json={'kind':'Saída','quantity':1,'reason':'Teste'},headers=headers).status_code==400

def test_optimistic_lock_and_appointment_conflict(app):
    client=app.test_client();headers=login(client)
    body=dict(patient_id=1,unit_id=1,date=date.today().isoformat(),time='09:00',specialty='Clínica geral',professional_id=2)
    response=client.post('/api/records/appointments',json=body,headers=headers)
    assert response.status_code==201
    rid=response.json['id']
    assert client.post('/api/records/appointments',json={**body,'patient_id':2},headers=headers).status_code==400
    assert client.patch(f'/api/records/appointments/{rid}',json={'version':1,'status':'Confirmado'},headers=headers).status_code==200
    assert client.patch(f'/api/records/appointments/{rid}',json={'version':1,'status':'Cancelado'},headers=headers).status_code==409

def test_citizen_cannot_read_or_modify_another_patient(app):
    client=app.test_client();headers=login(client)
    ids=[]
    for pid in (1,2):
        ids.append(client.post('/api/records/messages',json={'patient_id':pid,'subject':'Privado','body':f'Mensagem paciente {pid}'},headers=headers).json['id'])
    client.post('/api/logout',headers=headers)
    headers=login(client,'citizen')
    data=client.get('/api/citizen').json
    assert len(data['items'])==1
    assert data['items'][0]['body']=='Mensagem paciente 1'
    assert client.get('/api/patients').status_code==403
    assert client.get('/api/export/encounters').status_code==403
    assert client.post(f'/api/citizen/{ids[1]}/action',json={'action':'read'},headers=headers).status_code==404
    assert client.post(f'/api/citizen/{ids[0]}/action',json={'action':'read'},headers=headers).status_code==200

def test_migration_atomic_and_csv_injection(app):
    client=app.test_client();headers=login(client)
    before=len(client.get('/api/patients').json['items'])
    def upload(rows):
        output=io.StringIO();writer=csv.DictWriter(output,fieldnames=['name','birth_date','cpf','cns'],delimiter=';');writer.writeheader();writer.writerows(rows)
        return {'file':(io.BytesIO(output.getvalue().encode()),'data.csv')}
    rows=[patient(30),{**patient(31),'cpf':'123'}]
    assert client.post('/api/migration/import',data=upload(rows),headers=headers).status_code==400
    assert len(client.get('/api/patients').json['items'])==before
    assert client.post('/api/migration/import',data=upload([patient(30)]),headers=headers).json['imported']==1
    client.post('/api/records/messages',json={'patient_id':1,'subject':'=1+1','body':'Teste'},headers=headers)
    assert "'=1+1" in client.get('/api/export/messages').text

def test_audit_chain_detects_tampering(app):
    client=app.test_client();headers=login(client)
    client.get('/api/patients')
    client.post('/api/patients',json=patient(),headers=headers)
    assert client.get('/api/audit').json['chain_valid'] is True
    with app.app_context():
        db().execute("UPDATE audit SET action='tampered' WHERE id=1");db().commit()
    assert client.get('/api/audit').json['chain_valid'] is False

def test_deactivation_revokes_existing_session(app):
    user=app.test_client();login(user,'clinical')
    admin=app.test_client();headers=login(admin)
    assert user.get('/api/patients').status_code==200
    admin.patch('/api/users/2',json={'active':False},headers=headers)
    assert user.get('/api/patients').status_code==401

def test_backup_restore_is_encrypted_and_non_destructive(app,tmp_path):
    filename=create_backup(app)
    assert not filename.read_bytes().startswith(b'SQLite')
    output=tmp_path/'recovered.db'
    restore_backup(app,filename,output)
    with sqlite3.connect(output) as conn:
        assert conn.execute('SELECT COUNT(*) FROM patients').fetchone()[0]==2
    with pytest.raises(ValueError):restore_backup(app,filename,output)

def test_login_throttle(app):
    client=app.test_client();csrf=client.get('/api/session').json['csrf']
    for _ in range(5):
        assert client.post('/api/login',json={'username':'admin','password':'incorrect'},headers={'X-CSRF-Token':csrf}).status_code==401
    assert client.post('/api/login',json={'username':'admin','password':'incorrect'},headers={'X-CSRF-Token':csrf}).status_code==429

def test_patient_edit_conflicts_and_unit_permissions(app):
    client=app.test_client();headers=login(client)
    assert client.patch('/api/patients/1',json={'version':1,'phone':'22999999999'},headers=headers).status_code==200
    assert client.patch('/api/patients/1',json={'version':1,'phone':'0'},headers=headers).status_code==409
    assert client.patch('/api/patients/1',json={'version':2,'cpf':cpf_for(800000002)},headers=headers).status_code==400
    unit=client.post('/api/units',json={'name':'Hospital Teste','kind':'Hospital','cnes':'1234567'},headers=headers)
    assert unit.status_code==201
    assert client.patch('/api/units/'+str(unit.json['id']),json={'name':'Hospital Atualizado','kind':'Hospital','cnes':'1234567'},headers=headers).status_code==200
    other=app.test_client();other_headers=login(other,'reception')
    assert other.post('/api/units',json={'name':'Sem permissão','kind':'UBS'},headers=other_headers).status_code==403

def test_hospital_bed_and_discharge(app):
    client=app.test_client();headers=login(client)
    data={'patient_id':1,'unit_id':1,'date':date.today().isoformat(),'bed':'Leito 01','reason':'Teste'}
    response=client.post('/api/records/hospital',json=data,headers=headers)
    assert response.status_code==201
    assert client.post('/api/records/hospital',json={**data,'patient_id':2},headers=headers).status_code==400
    rid=response.json['id']
    assert client.patch(f'/api/records/hospital/{rid}',json={'version':1,'status':'Alta'},headers=headers).status_code==400
    assert client.patch(f'/api/records/hospital/{rid}',json={'version':1,'status':'Alta','discharge_date':date.today().isoformat()},headers=headers).status_code==200
    assert client.post('/api/records/hospital',json={**data,'patient_id':2},headers=headers).status_code==201

def test_transport_capacity_counts_companion(app):
    client=app.test_client();headers=login(client)
    fleet={'name':'Van Teste','plate':'TST1A01','capacity':2,'mileage':10,'maintenance_date':'2030-01-01'}
    vid=client.post('/api/records/fleet',json=fleet,headers=headers).json['id']
    trip={'patient_id':1,'unit_id':1,'date':date.today().isoformat(),'time':'08:00','destination':'Macaé','vehicle_id':vid,'driver':'Motorista','companion':'Acompanhante'}
    assert client.post('/api/records/transport',json=trip,headers=headers).status_code==201
    assert client.post('/api/records/transport',json={**trip,'patient_id':2,'companion':''},headers=headers).status_code==400

def test_parallel_stock_outflow_cannot_overdraw(app):
    from concurrent.futures import ThreadPoolExecutor
    admin=app.test_client();headers=login(admin)
    rid=admin.post('/api/records/pharmacy',json=stock(quantity=5),headers=headers).json['id']
    clients=[app.test_client(),app.test_client()]
    tokens=[login(client) for client in clients]
    def withdraw(i):
        return clients[i].post(f'/api/stock/{rid}/move',json={'kind':'Saída','quantity':4,'reason':'Concorrência'},headers=tokens[i]).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses=list(executor.map(withdraw,[0,1]))
    assert sorted(statuses)==[200,400]
    assert admin.get('/api/records/pharmacy').json['items'][0]['quantity']==1
    assert admin.get('/api/audit').json['chain_valid'] is True

def test_unreleased_exam_results_are_not_exposed_to_citizen(app):
    admin=app.test_client();headers=login(admin)
    admin.post('/api/records/exams',json={'patient_id':1,'unit_id':1,'date':date.today().isoformat(),'procedure':'Exame','result':'Laudo ainda não liberado','status':'Realizado'},headers=headers)
    citizen=app.test_client();login(citizen,'citizen')
    exam=citizen.get('/api/citizen').json['items'][0]
    assert 'result' not in exam
