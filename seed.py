"""Carga demonstrativa explícita. Não contém pacientes ou profissionais reais."""
import argparse
import random
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from saude.app import create_app
from saude.db import db, encrypt, identity_hash, now

def cpf_for(number):
    s=f"{number:09d}"
    for n in (9,10):
        s+=str(sum(int(s[j])*(n+1-j) for j in range(n))*10%11%10)
    return s

def seed(app):
    with app.app_context():
        if db().execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            print("Base já inicializada. Nenhum dado foi alterado.")
            return
        today=date.today(); rng=random.Random(42)
        units=[(f"UBS {i:02d}","Atenção básica") for i in range(1,12)]+[("Hospital Municipal Ana Moreira","Hospital"),("CAPS","Saúde mental"),("Central de Controle e Avaliação","Regulação"),("Farmácia Municipal","Farmácia"),("Almoxarifado Central","Estoque"),("Transporte Sanitário","Transporte"),("Vigilância em Saúde","Vigilância"),("Secretaria Municipal de Saúde","Administração")]
        db().executemany("INSERT INTO units(name,kind) VALUES(?,?)",units)
        first=["Maria","João","Ana","Carlos","Fernanda","Pedro","Juliana","José","Camila","Antônio","Mariana","Paulo","Beatriz","Lucas","Helena","Rafael","Lúcia","Gabriel","Sônia","Marcos"]
        last=["Silva","Santos","Oliveira","Souza","Pereira","Costa","Almeida","Lima","Rodrigues","Ferreira"]
        for i in range(80):
            cpf=cpf_for(800000000+i)
            payload=dict(name=f"{first[i%20]} {last[(i//20)%10]} {last[(i+3)%10]}",birth_date=f"{1948+i%60}-{1+i%12:02d}-{1+i%27:02d}",cpf=cpf,cns="",phone="",address=f"Território demonstrativo {1+i%11}",sex="Feminino" if i%2==0 else "Masculino",mother="Cadastro demonstrativo",allergies="Não informadas")
            db().execute("INSERT INTO patients(payload,identity_hash,created_at) VALUES(?,?,?)",(encrypt(payload),identity_hash(cpf),now()))
        users=[("Gestão Municipal","admin","admin",None),("Dra. Laura Mendes · Demo","laura","clinico",None),("Dr. André Costa · Demo","andre","clinico",None),("Equipe de Recepção","recepcao","recepcao",None),("Equipe de Farmácia","farmacia","farmacia",None),("Maria · acesso demonstrativo","cidadao","cidadao",1),("Gestor da Rede","gestor","gestor",None)]
        password=generate_password_hash("Demo@Saude2026!")
        db().executemany("INSERT INTO users(name,username,role,patient_id,password) VALUES(?,?,?,?,?)",[(*u,password) for u in users])
        def record(key,payload,status):
            cur=db().execute("INSERT INTO records(module,patient_id,unit_id,payload,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,2,?,?)",(key,payload.get("patient_id"),payload.get("unit_id"),encrypt(payload),status,now(),now()))
            return cur.lastrowid
        specialties=["Clínica geral","Enfermagem","Odontologia","Cardiologia","Pediatria","Saúde mental","Ginecologia"]
        for offset in range(30):
            day=(today-timedelta(days=offset)).isoformat()
            for j in range(8+offset%9):
                patient=1+(offset*7+j)%80
                status=("Confirmado" if j%3 else "Agendado") if offset==0 else ("Concluído" if j%7 else "Faltou")
                record("appointments",dict(patient_id=patient,unit_id=1+j%11,date=day,time=f"{8+j//2:02d}:{'00' if j%2==0 else '30'}",specialty=specialties[j%7],professional_id=2+j%2,notes="Dado fictício para demonstração."),status)
        for i in range(24):
            record("encounters",dict(patient_id=1+i%12,unit_id=1+i%11,date=(today-timedelta(days=i)).isoformat(),care_type=["Atenção básica","Atendimento médico","Enfermagem","Odontologia","CAPS","Hospitalar"][i%6],subjective="Registro fictício de acompanhamento de rotina.",objective="Dados de avaliação demonstrativos.",assessment="Evolução de demonstração, sem validade clínica.",plan="Retorno para acompanhamento na unidade de referência.",diagnosis="",prescription="",allergies="Não informadas"),"Finalizado")
        for i in range(17):
            record("regulation",dict(patient_id=1+i,unit_id=1+i%11,date=(today-timedelta(days=i*3)).isoformat(),specialty=["Cardiologia","Ultrassonografia","Oftalmologia","Ortopedia"][i%4],priority=["Eletiva","Prioritária","Urgente"][i%3],justification="Solicitação fictícia para demonstração do fluxo.",scheduled_date=""),["Aguardando","Em análise","Autorizado"][i%3])
        medicines=[("Losartana potássica 50 mg",420,100),("Metformina 850 mg",85,100),("Amoxicilina 500 mg",240,60),("Dipirona 500 mg",580,150),("Omeprazol 20 mg",45,80),("Paracetamol 500 mg",320,100)]
        for i,(name,qty,minimum) in enumerate(medicines):
            record("pharmacy",dict(unit_id=15,name=name,batch=f"DEMO-26{i:03d}",expiry=(today+timedelta(days=90+i*30)).isoformat(),minimum=minimum,quantity=qty,measure="Comprimido",notes="Lote fictício."),"Ativo")
        for i,name in enumerate(["Luva de procedimento · caixa","Seringa descartável 5 ml","Máscara cirúrgica · caixa","Gaze estéril · pacote"]):
            record("warehouse",dict(unit_id=16,name=name,batch=f"MAT-{i+1:03d}",expiry=(today+timedelta(days=365)).isoformat(),minimum=50,quantity=30+i*80,measure="Unidade",notes="Material demonstrativo."),"Ativo")
        vehicles=[]
        for i,name in enumerate(["Van sanitária 01","Micro-ônibus 02","Ambulância 03"]):
            vehicles.append(record("fleet",dict(name=name,plate=f"DEM{i}A0{i}",capacity=[15,24,2][i],mileage=12000+i*4000,maintenance_date=(today+timedelta(days=30)).isoformat(),notes="Veículo fictício."),"Disponível"))
        for i in range(4):
            record("transport",dict(patient_id=1+i,unit_id=17,date=(today+timedelta(days=i)).isoformat(),time="06:30",destination=["Campos dos Goytacazes","Macaé"][i%2],vehicle_id=vehicles[i%3],driver="Motorista demonstrativo",companion="",notes="Viagem TFD de demonstração."),"Programado")
        for i in range(3):
            record("hospital",dict(patient_id=30+i,unit_id=12,date=(today-timedelta(days=i+1)).isoformat(),bed=f"Clínica · {i+1:02d}",reason="Admissão fictícia para demonstração.",discharge_date="",notes=""),"Internado")
        for i in range(7):
            record("exams",dict(patient_id=1+i,unit_id=1+i,date=today.isoformat(),procedure=["Hemograma completo","Ultrassonografia abdominal","Eletrocardiograma"][i%3],code="",result="Laudo demonstrativo." if i%3==0 else "",notes=""),"Laudado" if i%3==0 else "Solicitado")
            record("surveillance",dict(patient_id=10+i,unit_id=18,date=(today-timedelta(days=i)).isoformat(),condition=["Dengue","Síndrome gripal"][i%2],territory=f"Território {1+i%3}",classification=["Suspeito","Confirmado","Descartado"][i%3],notes="Notificação fictícia."),"Em andamento")
        for i in range(12):
            record("billing",dict(patient_id=1+i,unit_id=1+i%11,date=today.isoformat(),competence=today.strftime("%Y-%m"),procedure="Consulta de demonstração",code="0301010072",professional_id=2+i%2,quantity=1,value=10,notes="Valor fictício; não representa a tabela SIGTAP vigente."),"Conferido" if i%3 else "Pendente")
        for i in range(3):
            record("judicial",dict(patient_id=3+i,case_number=f"DEMO-{2026}-{i+1:04d}",demand="Fornecimento de insumo · caso fictício.",date=today.isoformat(),deadline=(today+timedelta(days=2+i*5)).isoformat(),responsible="Equipe jurídica",cost=500+i*200,notes=""),"Em andamento")
            record("assets",dict(unit_id=1+i,name=["Computador de atendimento","Cadeira odontológica","Impressora de etiquetas"][i],tag=f"PAT-DEMO-{i+1:03d}",responsible="Coordenação da unidade",acquisition_date=today.isoformat(),value=2000+i*1000,notes=""),"Em uso")
        record("messages",dict(patient_id=1,subject="Sua consulta está agendada",body="Você tem um agendamento disponível. Consulte os detalhes na sua agenda e confirme sua presença."),"Disponível no portal")
        record("support",dict(subject="Orientação sobre cadastro de pacientes",category="Suporte",priority="Normal",description="Chamado demonstrativo de orientação à equipe.",resolution=""),"Aberto")
        for i,category in enumerate(["Implantação","Migração","Treinamento","Aceite"]):
            record("training",dict(subject=f"{category} da rede municipal",category=category,date=(today+timedelta(days=i*7)).isoformat(),responsible="Coordenação do projeto",audience="Equipe assistencial, administrativa e gestores",evidence="Atividade planejada; execução e evidências pendentes."),"Aberto")
        db().commit()
        print("Demonstração criada: 80 pacientes fictícios, 19 unidades e módulos integrados.")
        print("Acesso: admin / Demo@Saude2026! | Cidadão: cidadao / Demo@Saude2026!")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--demo",action="store_true",required=True)
    parser.parse_args()
    seed(create_app())
