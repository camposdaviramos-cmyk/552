import io
import json
from datetime import date, timedelta

import pytest

from test_app import app, login, encounter, stock
from saude.db import db, decrypt, record_dict


def create(client, headers, module, data):
    response = client.post('/api/records/' + module, json=data, headers=headers)
    assert response.status_code == 201, response.json
    return response.json['id']


def test_specialized_clinical_forms_and_odontogram(app):
    c = app.test_client(); h = login(c, 'clinical')
    for care, field in [('Atenção básica','family_context'), ('Atendimento médico','history'), ('Enfermagem','nursing_interventions'), ('Odontologia','dental_plan'), ('CAPS','therapeutic_project'), ('Hospitalar','history')]:
        data = {**encounter(), 'care_type':care, field:'Registro especializado', 'odontogram':{'11':'Cárie'}}
        rid = create(c,h,'encounters',data)
        item = next(r for r in c.get('/api/records/encounters').json['items'] if r['id']==rid)
        assert item[field]=='Registro especializado'
        assert item['odontogram']==({'11':'Cárie'} if care=='Odontologia' else {})
        assert c.get(f'/api/records/{rid}/history').json['seal_valid'] is True
    assert c.post('/api/records/encounters',json={**encounter(),'odontogram':{'99':'Cárie'}},headers=h).status_code==400


def test_shifts_overlap_across_units(app):
    c=app.test_client();h=login(c)
    shift=dict(unit_id=1,professional_id=2,date='2026-09-01',time='20:00',end_date='2026-09-02',end_time='08:00')
    rid=create(c,h,'shifts',shift)
    assert c.post('/api/records/shifts',json={**shift,'time':'21:00'},headers=h).status_code==400
    assert c.post('/api/records/shifts',json={**shift,'date':'2026-09-02','time':'08:00','end_time':'12:00'},headers=h).status_code==201
    assert c.patch(f'/api/records/shifts/{rid}',json={'version':1,'status':'Cancelado'},headers=h).status_code==200
    assert c.post('/api/records/shifts',json=shift,headers=h).status_code==201


def prescription():
    return dict(patient_id=1,unit_id=1,date='2026-09-01',end_date='2026-09-03',medication='Item demonstrativo',dose='Conforme registro',route='Via registrada',frequency='Horário registrado')


def test_prescription_dose_duplicate_and_immutability(app):
    c=app.test_client();h=login(c,'clinical');rid=create(c,h,'prescriptions',prescription())
    dose=dict(scheduled_at='2026-09-01T08:00',outcome='Administrada',notes='Checagem de teste')
    assert c.post(f'/api/prescriptions/{rid}/administrations',json=dose,headers=h).status_code==201
    assert c.post(f'/api/prescriptions/{rid}/administrations',json=dose,headers=h).status_code==400
    assert c.patch(f'/api/records/prescriptions/{rid}',json={'version':1,'dose':'Alterada'},headers=h).status_code==400
    assert c.post(f'/api/prescriptions/{rid}/administrations',json={**dose,'scheduled_at':'2026-09-05T08:00'},headers=h).status_code==400
    assert c.patch(f'/api/records/prescriptions/{rid}',json={'version':1,'status':'Suspensa'},headers=h).status_code==200
    assert c.post(f'/api/prescriptions/{rid}/administrations',json={**dose,'scheduled_at':'2026-09-02T08:00'},headers=h).status_code==400
    assert c.get(f'/api/records/{rid}/history').json['events'][0]['payload']['dose']=='Conforme registro'


def test_prescription_hospital_patient_link(app):
    c=app.test_client();h=login(c)
    hid=create(c,h,'hospital',dict(patient_id=2,unit_id=1,date='2026-09-01',bed='A',reason='Teste'))
    assert c.post('/api/records/prescriptions',json={**prescription(),'hospital_id':hid},headers=h).status_code==400


def test_encrypted_attachments_release_permissions_and_backup(app,tmp_path):
    from backup import create_backup,restore_backup
    import sqlite3
    c=app.test_client();h=login(c,'clinical')
    rid=create(c,h,'exams',dict(patient_id=1,unit_id=1,date='2026-09-01',procedure='Exame demonstrativo',result='Resultado'))
    content=b'%PDF-1.4\nDocumento privado de teste'
    upload=lambda: {'file':(io.BytesIO(content),'laudo.pdf')}
    response=c.post(f'/api/records/{rid}/attachments',data=upload(),headers=h)
    assert response.status_code==201
    aid=response.json['id']
    with app.app_context():
        raw=db().execute('SELECT content,metadata FROM attachments WHERE id=?',(aid,)).fetchone()
        assert content not in raw['content'] and 'laudo.pdf' not in raw['metadata']
    citizen=app.test_client();login(citizen,'citizen')
    assert citizen.get(f'/api/citizen/attachments/{aid}').status_code==404
    reception=app.test_client();login(reception,'reception')
    assert reception.get(f'/api/attachments/{aid}').status_code==404
    assert c.patch(f'/api/records/exams/{rid}',json={'version':1,'status':'Laudado'},headers=h).status_code==200
    assert citizen.get(f'/api/citizen/attachments/{aid}').data==content
    assert c.post(f'/api/records/{rid}/attachments',data=upload(),headers=h).status_code==400
    assert c.patch(f'/api/records/exams/{rid}',json={'version':2,'result':'Outro'},headers=h).status_code==409
    backup=create_backup(app);restored=tmp_path/'attachments-restore.db';restore_backup(app,backup,restored)
    with sqlite3.connect(restored) as conn:
        assert conn.execute('SELECT COUNT(*) FROM attachments').fetchone()[0]==1


def test_attachment_invalid_format_and_size(app):
    c=app.test_client();h=login(c);rid=create(c,h,'encounters',{**encounter(),'status':'Rascunho'})
    for content in (b'<script>bad</script>',b'%PDF-'+b'x'*(1024*1024)):
        assert c.post(f'/api/records/{rid}/attachments',data={'file':(io.BytesIO(content),'file.pdf')},headers=h).status_code==400


def asset():
    return dict(unit_id=1,name='Equipamento',tag='PAT-001',responsible='Equipe A',acquisition_date='2025-01-01',value=1200,residual_value=0,useful_life=12)


def test_asset_transfer_inventory_valuation_and_duplicate(app):
    c=app.test_client();h=login(c);rid=create(c,h,'assets',asset())
    assert c.post('/api/records/assets',json=asset(),headers=h).status_code==400
    unit=c.post('/api/units',json={'name':'Unidade B','kind':'UBS'},headers=h).json['id']
    assert c.patch(f'/api/records/assets/{rid}',json={'version':1,'unit_id':unit},headers=h).status_code==400
    event=dict(kind='Transferência',version=1,unit_id=unit,responsible='Equipe B',notes='Termo 1')
    assert c.post(f'/api/assets/{rid}/events',json=event,headers=h).status_code==200
    assert c.post(f'/api/assets/{rid}/events',json=event,headers=h).status_code==409
    assert c.post(f'/api/assets/{rid}/events',json={'kind':'Inventário','version':2,'condition':'Localizado','notes':'Conferido'},headers=h).status_code==200
    value=c.get('/api/assets/valuation?date=2025-07-01').json['items'][0]
    assert value['depreciation']==600 and value['book_value']==600
    assert c.get('/api/assets/valuation?date=2028-01-01').json['items'][0]['book_value']==0
    history=c.get(f'/api/records/{rid}/history').json
    assert len(history['events'])==2 and len(history['versions'])==3


def fleet():
    return dict(name='Van',plate='TST1A01',capacity=4,mileage=100,maintenance_date='2027-01-01')


def test_transport_intervals_cost_and_vehicle_constraints(app):
    c=app.test_client();h=login(c);vid=create(c,h,'fleet',fleet())
    trip=dict(patient_id=1,unit_id=1,date='2026-09-01',time='08:00',return_time='12:00',destination='Destino',vehicle_id=vid,driver='Motorista',travel_cost=25.5,lodging_cost=100,meal_cost=10,route_stops='UBS;Hospital')
    create(c,h,'transport',trip)
    assert c.get('/api/records/transport').json['items'][0]['total_cost']==135.5
    assert c.post('/api/records/transport',json={**trip,'patient_id':2,'time':'10:00','return_time':'14:00'},headers=h).status_code==400
    assert c.patch(f'/api/records/fleet/{vid}',json={'version':1,'status':'Em manutenção'},headers=h).status_code==400
    assert c.post('/api/records/fleet',json=fleet(),headers=h).status_code==400


def test_fleet_expense_updates_odometer_and_history(app):
    c=app.test_client();h=login(c);vid=create(c,h,'fleet',fleet())
    event=dict(vehicle_id=vid,date='2026-09-01',kind='Abastecimento',mileage=150,liters=10,cost=60,description='Comprovante')
    rid=create(c,h,'fleet_events',event)
    assert c.get('/api/records/fleet').json['items'][0]['mileage']==150
    assert c.post('/api/records/fleet_events',json={**event,'mileage':120},headers=h).status_code==400
    assert c.patch(f'/api/records/fleet_events/{rid}',json={'version':1,'cost':10},headers=h).status_code==409


def test_atomic_stock_transfer_and_history(app):
    c=app.test_client();h=login(c);rid=create(c,h,'pharmacy',stock(10))
    unit=c.post('/api/units',json={'name':'Unidade B','kind':'UBS'},headers=h).json['id']
    body=dict(unit_id=unit,quantity=4,reason='Transferência teste')
    response=c.post(f'/api/stock/{rid}/transfer',json=body,headers=h)
    assert response.status_code==200
    items=c.get('/api/records/pharmacy').json['items']
    assert sum(r['quantity'] for r in items)==10
    assert next(r for r in items if r['id']==rid)['quantity']==6
    assert c.post(f'/api/stock/{rid}/transfer',json={**body,'quantity':7},headers=h).status_code==400
    assert c.get(f'/api/stock/{rid}/movements').json['items'][0]['kind']=='Transferência saída'
    assert c.get('/api/audit').json['chain_valid']


def test_billing_origin_validation_and_rejection(app):
    c=app.test_client();h=login(c);source=create(c,h,'encounters',encounter())
    data=dict(patient_id=1,unit_id=1,date=date.today().isoformat(),competence=date.today().isoformat()[:7],procedure='Procedimento',code='0301010072',professional_id=2,quantity=1,value=10,source_id=source)
    rid=create(c,h,'billing',data)
    assert c.post('/api/records/billing',json=data,headers=h).status_code==400
    assert c.patch(f'/api/records/billing/{rid}',json={'version':1,'status':'Rejeitado'},headers=h).status_code==400
    assert c.patch(f'/api/records/billing/{rid}',json={'version':1,'status':'Rejeitado','review_notes':'Inconsistência'},headers=h).status_code==200
    assert c.post('/api/records/billing',json=data,headers=h).status_code==201


def test_analytics_population_filters_and_goals(app):
    c=app.test_client();h=login(c)
    create(c,h,'territories',dict(territory='Centro',population=1000,date='2026-01-01',source='Base de teste'))
    for pid in (1,1,2):
        create(c,h,'surveillance',dict(patient_id=pid,unit_id=1,date='2026-09-01',condition='Agravo teste',territory='Centro',classification='Confirmado'))
    goal=create(c,h,'goals',dict(indicator='Exames laudados',date='2026-09-01',end_date='2026-09-30',target=2))
    create(c,h,'exams',dict(patient_id=1,unit_id=1,date='2026-09-01',procedure='Teste',result='Resultado',status='Laudado'))
    data=c.get('/api/analytics?start=2026-09-01&end=2026-09-30').json
    epi=data['epidemiology'][0]
    assert epi['confirmed_patients']==2 and epi['rate_per_100k']==200
    assert data['goals'][0]['percent']==50
    assert c.get('/api/analytics?start=2026-09-01&end=2026-09-30&unit=1').json['epidemiology'][0]['rate_per_100k'] is None
    assert not c.get('/api/analytics?start=2025-01-01&end=2025-01-31').json['epidemiology']
    assert 'Centro' in c.get('/api/analytics?start=2026-09-01&end=2026-09-30&format=csv').text
    assert c.get('/api/analytics?start=2026-10-01&end=2026-01-01').status_code==400


def test_support_training_resolution_and_comments(app):
    c=app.test_client();h=login(c)
    rid=create(c,h,'support',dict(subject='Chamado',category='Suporte',priority='Normal',description='Teste'))
    assert c.post(f'/api/records/{rid}/comments',json={'text':'Em análise'},headers=h).status_code==201
    assert c.patch(f'/api/records/support/{rid}',json={'version':1,'status':'Concluído'},headers=h).status_code==400
    assert c.patch(f'/api/records/support/{rid}',json={'version':1,'status':'Concluído','resolution':'Resolvido'},headers=h).status_code==200
    training=dict(subject='Capacitação',category='Treinamento',date='2026-09-01',responsible='Instrutor',audience='Equipe',status='Concluído')
    assert c.post('/api/records/training',json=training,headers=h).status_code==400
    assert c.post('/api/records/training',json={**training,'evidence':'Relatório','attendance':'2 presentes','duration':2},headers=h).status_code==201


def test_record_migration_simulation_atomicity_and_receipts(app):
    c=app.test_client();h=login(c)
    entry=dict(source_id='e1',module='encounters',data=encounter())
    def upload(items,source='Legado teste'):
        return {'file':(io.BytesIO(json.dumps(dict(source=source,items=items)).encode()),'registros.json')}
    before=len(c.get('/api/records/encounters').json['items'])
    assert c.post('/api/migration/records/validate',data=upload([entry]),headers=h).json['valid']==1
    assert len(c.get('/api/records/encounters').json['items'])==before
    invalid={**entry,'source_id':'e2','data':{**encounter(),'patient_id':999}}
    assert c.post('/api/migration/records/import',data=upload([entry,invalid]),headers=h).status_code==400
    assert len(c.get('/api/records/encounters').json['items'])==before
    result=c.post('/api/migration/records/import',data=upload([entry]),headers=h)
    assert result.status_code==201 and result.json['imported']==1
    assert c.post('/api/migration/records/import',data=upload([entry]),headers=h).status_code==409
    assert c.post('/api/migration/records/import',data=upload([entry,{**entry,'source_id':'e3'}]),headers=h).status_code==400
    assert len(c.get('/api/migration/runs').json['items'])==1


def test_citizen_event_stream_is_scoped_and_revocation(app):
    app.config['EVENT_STREAM_TICKS']=1
    admin=app.test_client();h=login(admin)
    citizen=app.test_client();login(citizen,'citizen')
    first=citizen.get('/api/citizen/events').text
    assert 'event: refresh' in first and 'Paciente' not in first
    create(admin,h,'messages',dict(patient_id=2,subject='Privada',body='Outro paciente'))
    assert citizen.get('/api/citizen/events').text==first
    create(admin,h,'messages',dict(patient_id=1,subject='Nova',body='Mensagem ao titular'))
    assert citizen.get('/api/citizen/events').text!=first
    admin.patch('/api/users/4',json={'active':False},headers=h)
    assert citizen.get('/api/citizen/events').status_code==401


def test_workflow_permissions_and_static_pwa(app):
    c=app.test_client();h=login(c,'reception')
    for url in ('/api/analytics','/api/assets/valuation','/api/migration/runs'):
        assert c.get(url).status_code==403
    assert c.post('/api/records/prescriptions',json=prescription(),headers=h).status_code==403
    assert c.post('/api/prescriptions/1/administrations',json={},headers=h).status_code==403
    assert c.get('/sw.js').status_code==200
    assert '/api/' in c.get('/sw.js').text
    assert c.get('/static/offline.html').status_code==200


def test_professional_unique_identity_and_legacy_identification(app):
    from seed import cpf_for
    c=app.test_client();h=login(c)
    data=dict(name='Profissional Teste',username='new-clinical',password='Password@2026!',role='clinico',professional_cpf=cpf_for(900000001))
    assert c.post('/api/users',json={**data,'professional_cpf':''},headers=h).status_code==400
    response=c.post('/api/users',json=data,headers=h)
    assert response.status_code==201
    assert c.post('/api/users',json={**data,'username':'duplicate'},headers=h).status_code==400
    assert c.patch('/api/users/2',json={'professional_cpf':data['professional_cpf']},headers=h).status_code==400
    assert c.patch('/api/users/2',json={'professional_cpf':cpf_for(900000002)},headers=h).status_code==200
    with app.app_context():
        row=db().execute('SELECT * FROM users WHERE id=?',(response.json['id'],)).fetchone()
        assert data['professional_cpf'] not in row['professional_payload']
        assert decrypt(row['professional_payload'])['cpf']==data['professional_cpf']
    assert next(u for u in c.get('/api/users').json['items'] if u['id']==2)['identified']==1


def test_regulation_date_and_hospital_double_admission(app):
    c=app.test_client();h=login(c)
    data=dict(patient_id=1,unit_id=1,date='2026-09-01',specialty='Clínica',priority='Eletiva',justification='Teste',status='Autorizado')
    assert c.post('/api/records/regulation',json=data,headers=h).status_code==400
    assert c.post('/api/records/regulation',json={**data,'scheduled_date':'2026-09-02'},headers=h).status_code==201
    admission=dict(patient_id=1,unit_id=1,date='2026-09-01',bed='A',reason='Teste')
    create(c,h,'hospital',admission)
    assert c.post('/api/records/hospital',json={**admission,'bed':'B'},headers=h).status_code==400


def test_compliance_external_dependencies_and_evidence(app):
    c=app.test_client();login(c)
    matrix=c.get('/api/compliance').json
    assert len(matrix['items'])==70
    assert len({i['id'] for i in matrix['items']})==70
    for item in matrix['items']:
        if item['external_dependency']:
            assert item['status']=='Dependência externa' and item['dependency'] and item['owner'] and item['next_step']
        else:
            assert item['criterion'] and item['validation'] and item['evidence']
    assert c.get('/api/compliance/document').data.startswith(b'%PDF')


def test_invalid_json_and_vigilance_analytics_permissions(app):
    c=app.test_client();h=login(c)
    assert c.post('/api/records/assets',json=[],headers=h).status_code==400
    create(c,h,'billing',dict(patient_id=1,unit_id=1,date='2026-09-01',competence='2026-09',procedure='Teste',code='0301010072',professional_id=2,quantity=1,value=999,status='Conferido'))
    response=c.post('/api/users',json=dict(name='Vigilância Teste',username='vigilance',password='Test@Password2026',role='vigilancia'),headers=h)
    assert response.status_code==201
    v=app.test_client();login(v,'vigilance')
    report=v.get('/api/analytics?start=2026-09-01&end=2026-09-30').json
    assert report['summary']['billing_approved']==0
    assert not any(r['label']=='billing' for r in report['dimensions']['module'])
