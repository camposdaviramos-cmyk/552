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

def can_access(role, module_key):
    return role == "admin" or role in MODULES[module_key]["roles"]
