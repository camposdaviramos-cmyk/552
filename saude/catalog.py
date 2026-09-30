"""Catálogo de formulários e permissões. Referência: TR, páginas 1 e 7–9."""

def field(key, label, kind="text", required=True, options=None):
    return dict(key=key, label=label, type=kind, required=required, options=options or [])

P = field("patient_id", "Paciente", "patient")
U = field("unit_id", "Unidade de saúde", "unit")
D = field("date", "Data", "date")
NOTE = field("notes", "Observações", "textarea", False)

def module(title, singular, group, icon, description, fields, columns, roles, statuses=None):
    return dict(title=title, singular=singular, group=group, icon=icon,
                description=description, fields=fields, columns=columns, roles=roles,
                statuses=statuses or ["Aberto", "Em andamento", "Concluído", "Cancelado"])

CLINICAL = ["clinico", "gestor"]
MODULES = {
    "appointments": module("Agenda e atendimentos", "Agendamento", "Assistência", "calendar", "Organize a jornada do paciente, da marcação ao atendimento.",
        [P,U,D,field("time","Horário","time"),field("specialty","Especialidade","select",options=["Clínica geral","Enfermagem","Odontologia","Cardiologia","Pediatria","Saúde mental","Ginecologia"]),field("professional_id","Profissional","professional"),NOTE], ["patient_id","date","time","specialty","unit_id","status"], ["recepcao","clinico","gestor"], ["Agendado","Confirmado","Em atendimento","Concluído","Faltou","Cancelado"]),
    "encounters": module("Prontuário eletrônico", "Registro clínico", "Assistência", "clipboard", "Histórico municipal unificado e evoluções vinculadas ao profissional.",
        [P,U,D,field("care_type","Linha de cuidado","select",options=["Atenção básica","Atendimento médico","Enfermagem","Odontologia","CAPS","Hospitalar"]),field("subjective","Subjetivo · relato do paciente","textarea"),field("objective","Objetivo · avaliação","textarea"),field("assessment","Avaliação clínica","textarea"),field("plan","Plano de cuidado","textarea"),field("diagnosis","Código de diagnóstico",required=False),field("prescription","Prescrição / orientações","textarea",False),field("allergies","Alergias registradas",required=False)], ["patient_id","date","care_type","unit_id","status"], CLINICAL, ["Rascunho","Finalizado"]),
    "hospital": module("Atenção hospitalar", "Internação", "Assistência", "hospital", "Admissões, leitos e altas do Hospital Municipal Ana Moreira.",
        [P,U,field("date","Data de admissão","date"),field("bed","Leito"),field("reason","Motivo da internação","textarea"),field("discharge_date","Data de alta","date",False),NOTE], ["patient_id","date","bed","unit_id","status"], CLINICAL, ["Internado","Em observação","Alta","Transferido"]),
    "regulation": module("Regulação", "Solicitação", "Assistência", "arrows", "Priorize solicitações e acompanhe a demanda reprimida da rede.",
        [P,U,D,field("specialty","Especialidade / procedimento"),field("priority","Prioridade","select",options=["Eletiva","Prioritária","Urgente"]),field("justification","Justificativa","textarea"),field("scheduled_date","Data autorizada","date",False)], ["patient_id","specialty","priority","date","unit_id","status"], ["regulador","clinico","gestor"], ["Aguardando","Em análise","Autorizado","Agendado","Concluído","Indeferido"]),
    "exams": module("Exames e procedimentos", "Solicitação de exame", "Assistência", "flask", "Acompanhe solicitações, execução e resultados em um único lugar.",
        [P,U,D,field("procedure","Exame / procedimento"),field("code","Código do procedimento",required=False),field("result","Resultado / laudo","textarea",False),NOTE], ["patient_id","procedure","date","unit_id","status"], CLINICAL, ["Solicitado","Agendado","Realizado","Laudado","Cancelado"]),
    "surveillance": module("Vigilância em saúde", "Notificação", "Assistência", "shield", "Monitore notificações e acompanhe a investigação epidemiológica.",
        [P,U,D,field("condition","Agravo / evento"),field("territory","Território"),field("classification","Classificação","select",options=["Suspeito","Confirmado","Descartado"]),NOTE], ["condition","territory","classification","date","status"], ["vigilancia","clinico","gestor"]),
    "pharmacy": module("Assistência farmacêutica", "Medicamento / lote", "Administração", "pill", "Estoque por lote, validade e dispensação vinculada ao cidadão.",
        [U,field("name","Medicamento e apresentação"),field("batch","Lote"),field("expiry","Validade","date"),field("minimum","Estoque mínimo","number"),field("quantity","Quantidade inicial","number"),field("measure","Unidade de medida","select",options=["Comprimido","Cápsula","Frasco","Ampola","Unidade"]),NOTE], ["name","batch","expiry","quantity","unit_id","status"], ["farmacia","gestor"], ["Ativo","Bloqueado"]),
    "warehouse": module("Almoxarifado", "Material / lote", "Administração", "box", "Controle de insumos e movimentações entre as unidades da rede.",
        [U,field("name","Material"),field("batch","Lote / referência"),field("expiry","Validade","date",False),field("minimum","Estoque mínimo","number"),field("quantity","Quantidade inicial","number"),field("measure","Unidade de medida"),NOTE], ["name","batch","quantity","minimum","unit_id","status"], ["estoque","gestor"], ["Ativo","Bloqueado"]),
    "assets": module("Controle patrimonial", "Bem patrimonial", "Administração", "monitor", "Localização, responsabilidade e conservação do patrimônio.",
        [U,field("name","Descrição do bem"),field("tag","Tombamento"),field("responsible","Responsável"),field("acquisition_date","Data de aquisição","date"),field("value","Valor de aquisição (R$)","number"),NOTE], ["tag","name","responsible","unit_id","status"], ["estoque","gestor"], ["Em uso","Em manutenção","Baixado"]),
    "transport": module("Transporte e TFD", "Viagem", "Administração", "bus", "Planeje o transporte sanitário e o tratamento fora do domicílio.",
        [P,U,D,field("time","Horário de saída","time"),field("destination","Destino"),field("vehicle_id","Veículo","vehicle"),field("driver","Motorista"),field("companion","Acompanhante",required=False),NOTE], ["patient_id","date","time","destination","vehicle_id","status"], ["transporte","gestor"], ["Solicitado","Programado","Em viagem","Concluído","Cancelado"]),
    "fleet": module("Controle da frota", "Veículo", "Administração", "truck", "Disponibilidade, quilometragem e manutenção da frota sanitária.",
        [field("name","Modelo / identificação"),field("plate","Placa"),field("capacity","Capacidade de passageiros","number"),field("mileage","Quilometragem","number"),field("maintenance_date","Próxima manutenção","date"),NOTE], ["name","plate","capacity","mileage","maintenance_date","status"], ["transporte","gestor"], ["Disponível","Em viagem","Em manutenção","Inativo"]),
    "billing": module("Faturamento SUS", "Produção", "Gestão", "receipt", "Organize a produção e a conferência por competência.",
        [P,U,field("date","Data do procedimento","date"),field("competence","Competência","month"),field("procedure","Descrição do procedimento"),field("code","Código SIGTAP"),field("professional_id","Profissional","professional"),field("quantity","Quantidade","number"),field("value","Valor unitário (R$)","number"),NOTE], ["competence","procedure","code","quantity","value","status"], ["faturamento","gestor"], ["Pendente","Conferido","Rejeitado"]),
    "judicial": module("Demandas judiciais", "Demanda judicial", "Gestão", "scale", "Acompanhe determinações, responsáveis e prazos de cumprimento.",
        [P,field("case_number","Número do processo"),field("demand","Objeto da demanda","textarea"),field("date","Data de recebimento","date"),field("deadline","Prazo de cumprimento","date"),field("responsible","Responsável"),field("cost","Custo estimado (R$)","number"),NOTE], ["case_number","patient_id","deadline","responsible","status"], ["juridico","gestor"]),
    "messages": module("Comunicação com o cidadão", "Mensagem", "Gestão", "message", "Disponibilize avisos individuais na caixa de entrada do portal do cidadão.",
        [P,field("subject","Assunto"),field("body","Mensagem","textarea")], ["patient_id","subject","created_at","status"], ["recepcao","gestor"], ["Disponível no portal","Lida"]),
    "support": module("Suporte e manutenção", "Chamado", "Operação", "headphones", "Registre incidentes, melhorias e o acompanhamento do atendimento.",
        [field("subject","Assunto"),field("category","Categoria","select",options=["Suporte","Manutenção corretiva","Manutenção evolutiva"]),field("priority","Prioridade","select",options=["Baixa","Normal","Alta","Crítica"]),field("description","Descrição","textarea"),field("resolution","Solução","textarea",False)], ["subject","category","priority","created_at","status"], ["gestor","clinico","recepcao","farmacia","estoque","transporte","regulador","faturamento","vigilancia","juridico"]),
    "training": module("Implantação e treinamento", "Atividade", "Operação", "book", "Planeje a implantação, documente capacitações e registre os aceites.",
        [field("subject","Atividade"),field("category","Etapa","select",options=["Implantação","Migração","Treinamento","Aceite"]),D,field("responsible","Responsável"),field("audience","Equipe / participantes","textarea"),field("evidence","Relatório / evidência","textarea",False)], ["subject","category","date","responsible","status"], ["gestor"]),
}

ROLE_LABELS = {"admin":"Administrador", "gestor":"Gestor municipal", "clinico":"Profissional assistencial", "recepcao":"Recepção", "farmacia":"Farmácia", "estoque":"Almoxarifado", "transporte":"Transporte", "regulador":"Regulação", "faturamento":"Faturamento", "vigilancia":"Vigilância", "juridico":"Jurídico", "cidadao":"Cidadão"}

def reference(key, label, target, required=True):
    return {**field(key, label, "record", required), "module": target}

def clinical_field(key, label, kind="textarea", care=None, options=None):
    return {**field(key, label, kind, False, options), "care_types": care or []}

# Campos preenchidos pelo profissional; não geram diagnósticos ou condutas automáticas.
MODULES["encounters"]["fields"] += [
    clinical_field("blood_pressure", "Pressão arterial registrada", "text"),
    clinical_field("temperature", "Temperatura registrada (°C)", "number"),
    clinical_field("weight", "Peso registrado (kg)", "number"),
    clinical_field("height", "Altura registrada (cm)", "number"),
    clinical_field("heart_rate", "Frequência cardíaca registrada", "number"),
    clinical_field("oxygen", "Saturação registrada (%)", "number"),
    clinical_field("family_context", "Contexto familiar e territorial", care=["Atenção básica"]),
    clinical_field("prevention", "Prevenção, vacinação e acompanhamento", care=["Atenção básica"]),
    clinical_field("history", "Antecedentes e exame físico", care=["Atendimento médico", "Hospitalar"]),
    clinical_field("nursing_diagnosis", "Avaliação e necessidades de enfermagem", care=["Enfermagem"]),
    clinical_field("nursing_interventions", "Intervenções e avaliação dos resultados", care=["Enfermagem"]),
    clinical_field("odontogram", "Odontograma · condição registrada por dente", "odontogram", ["Odontologia"]),
    clinical_field("dental_plan", "Procedimentos odontológicos e plano", care=["Odontologia"]),
    clinical_field("mental_exam", "Avaliação psicossocial", care=["CAPS"]),
    clinical_field("therapeutic_project", "Projeto terapêutico singular · metas e ações", care=["CAPS"]),
    clinical_field("support_network", "Rede de apoio e profissionais responsáveis", care=["CAPS"]),
    clinical_field("followup_date", "Retorno / reavaliação", "date"),
]
MODULES["assets"]["fields"] += [field("useful_life", "Vida útil estimada (meses)", "number", False), field("residual_value", "Valor residual (R$)", "number", False)]
MODULES["transport"]["fields"] += [
    field("return_time", "Horário previsto de retorno (mesmo dia)", "time", False),
    field("route_stops", "Roteiro · paradas na ordem de execução", "textarea", False),
    field("authorization", "Autorização TFD / referência", required=False),
    field("travel_cost", "Passagens / deslocamento do paciente (R$)", "number", False),
    field("lodging_cost", "Hospedagem do paciente (R$)", "number", False),
    field("meal_cost", "Alimentação do paciente (R$)", "number", False),
    field("companion_cost", "Custeio do acompanhante (R$)", "number", False),
]
MODULES["billing"]["fields"] += [reference("source_id", "Atendimento / exame de origem", "clinical_source", False), field("review_notes", "Parecer de conferência / motivo de rejeição", "textarea", False)]
MODULES["surveillance"]["fields"] += [field("onset_date", "Início dos sintomas", "date", False), field("outcome", "Desfecho", "select", False, ["Em acompanhamento", "Recuperado", "Óbito", "Ignorado"]), field("investigation", "Investigação e medidas registradas", "textarea", False)]
MODULES["support"]["fields"] += [field("responsible", "Responsável pelo atendimento", required=False), field("deadline", "Prazo acordado", "date", False)]
MODULES["training"]["fields"] += [field("duration", "Carga horária (horas)", "number", False), field("attendance", "Presença e avaliação dos participantes", "textarea", False)]
MODULES.update({
    "shifts": module("Escalas assistenciais", "Plantão", "Assistência", "calendar", "Escalas por unidade e profissional, com bloqueio de sobreposição.",
        [U, field("professional_id", "Profissional", "professional"), D, field("time", "Início", "time"), field("end_date", "Data final", "date"), field("end_time", "Término", "time"), NOTE],
        ["professional_id", "unit_id", "date", "time", "end_time", "status"], CLINICAL, ["Programado", "Concluído", "Cancelado"]),
    "prescriptions": module("Prescrições e administração", "Item de prescrição", "Assistência", "pill", "Prescrição registrada pelo profissional e checagem de administração por dose.",
        [P,U,D, reference("hospital_id", "Internação vinculada", "hospital", False), field("medication", "Medicamento / apresentação"), field("dose", "Dose prescrita"), field("route", "Via prescrita"), field("frequency", "Frequência / horários prescritos"), field("end_date", "Data final", "date"), NOTE],
        ["patient_id", "medication", "dose", "date", "status"], CLINICAL, ["Ativa", "Concluída", "Suspensa"]),
    "fleet_events": module("Abastecimento e manutenção", "Evento da frota", "Administração", "truck", "Histórico de quilometragem, despesas, abastecimentos e manutenção.",
        [field("vehicle_id", "Veículo", "vehicle"), D, field("kind", "Tipo", "select", options=["Abastecimento", "Manutenção preventiva", "Manutenção corretiva"]), field("mileage", "Quilometragem", "number"), field("liters", "Litros (abastecimento)", "number", False), field("cost", "Custo total (R$)", "number"), field("description", "Serviço / comprovante", "textarea")],
        ["vehicle_id", "date", "kind", "mileage", "cost", "status"], ["transporte", "gestor"], ["Registrado"]),
    "territories": module("Territórios e população", "Base populacional", "Gestão", "building", "Cadastre o denominador e sua fonte para os indicadores epidemiológicos.",
        [field("territory", "Território"), field("population", "População de referência", "number"), D, field("source", "Fonte / documento da população")],
        ["territory", "population", "date", "source", "status"], ["vigilancia", "gestor"], ["Ativo", "Inativo"]),
    "goals": module("Metas de gestão", "Meta", "Gestão", "chart", "Defina metas por unidade, indicador e período para comparar com a produção registrada.",
        [field("unit_id", "Unidade (vazio = rede)", "unit", False), field("indicator", "Indicador", "select", options=["Atendimentos concluídos", "Exames laudados", "Produção conferida"]), D, field("end_date", "Fim do período", "date"), field("target", "Meta quantitativa", "number")],
        ["indicator", "unit_id", "date", "end_date", "target", "status"], ["gestor"], ["Ativa", "Encerrada"]),
})

def can_access(role, module_key):
    return role == "admin" or role in MODULES[module_key]["roles"]
