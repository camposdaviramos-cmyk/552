# Mapa do Termo de Referência

Fonte: `TR.pdf` fornecido pelo usuário, 13 páginas digitalizadas. Leitura visual integral das páginas extraídas, preservadas localmente em `docs/paginas/`. Documento datado de 31/08/2026. Este mapa é uma síntese de rastreabilidade, não substitui o original.

| Seção / páginas | Conteúdo |
|---|---|
| 1.1 / p.1 | Solução integrada de saúde pública municipal em cloud/SaaS, implantação, migração, treinamento, suporte e manutenção corretiva/evolutiva. |
| 1.2 / p.1–5 | Licenciamento e serviços; módulos mínimos; web; base única ou integração nativa; interoperabilidade MS; LGPD. |
| 1.3 / p.5–6 | 11 UBS, Hospital Municipal Ana Moreira, CAPS, Central de Controle e Avaliação, Farmácia Municipal, Almoxarifado, Transporte Sanitário, Vigilância e sede administrativa. |
| 2 / p.6 | Prontuário único, redução de retrabalho, faturamento, rastreabilidade clínica e apoio à decisão. |
| 3.1 / p.6–7 | Cloud, criptografia, backups automáticos, auditoria, perfis de acesso e disponibilidade mínima de 99,5%. |
| 3.2 / p.7 | Lei 14.133/2021, LGPD e normativas MS/DATASUS são citadas como requisitos do documento. |
| 3.3 / p.7 | Atestados de capacidade técnica; treinamento das equipes; atendimento permanente com telefone e e-mail. |
| 4 / p.7–9 | Solução integrada, persistência única, identificação unívoca de pacientes e profissionais; módulos e integrações obrigatórias. |
| 5 / p.9 | Estimativa global de R$ 226.666,70. |
| 6 / p.9 | Implantação inicial em até 30 dias corridos da Ordem de Serviço. |
| 7 / p.9 | Vigência de 12 meses e previsão de prorrogações. |
| 8 / p.10–11 | Pregão eletrônico, menor preço global; habilitação e documentação da licitante. |
| 9 / p.11 | Fiscal técnico a designar; fiscal administrativo e gestor identificados no documento. |
| 10 / p.11–12 | Medição e pagamento por componente, aceite, relatório, SLA, nota fiscal e atesto; pagamento até 30 dias após atesto. |
| 11–12 / p.12 | Planejamento anual em elaboração e conclusão administrativa. |
| 13 / p.12–13 | Dotação para setembro a dezembro de 2026 e vinculação dos meses de 2027 à lei orçamentária futura. |
| 14–15 / p.13 | Penalidades/condições gerais, responsáveis e assinaturas. |

## Valores expressos no documento

| Item | Quantidade | Valor unitário | Total |
|---|---:|---:|---:|
| Licenciamento mensal | 12 | R$ 9.000,00 | R$ 108.000,00 |
| Implantação | 1 | R$ 14.000,00 | R$ 14.000,00 |
| Migração | 1 | R$ 12.333,33 | R$ 12.333,33 |
| Treinamento | 1 | R$ 12.333,33 | R$ 12.333,33 |
| Suporte técnico mensal | 12 | R$ 3.666,67 | R$ 44.000,04 |
| Manutenção mensal | 12 | R$ 3.000,00 | R$ 36.000,00 |
| Total estimado | | | **R$ 226.666,70** |

Valores transcritos para rastreabilidade do TR, não constituem proposta comercial desta implementação.

## Módulos enumerados

Assistenciais: cadastro único; prontuário; atenção básica; atendimento médico; enfermagem; odontologia; CAPS; regulação; exames; procedimentos; atendimento ambulatorial/hospitalar; vigilância. O capítulo 4 também menciona aplicativo, mensagem instantânea, demandas judiciais, controle/avaliação e faturamento SUS.

Administrativos: farmácia, almoxarifado, patrimônio, transporte sanitário/TFD, frota e estoques.

Gerenciais: painéis, BI, indicadores epidemiológicos e relatórios estratégicos.

Integrações obrigatórias: **e-SUS APS, SISAB, CNES, BPA, SIA/SUS e sistemas disponibilizados pelo Ministério da Saúde.**

O documento não contém leiautes de interoperabilidade, regras detalhadas por especialidade, lista nominal das 11 UBS, credenciais, esquema do legado, roteiro detalhado de prova de conceito nem tempos de resposta de suporte por severidade. Tais informações devem ser obtidas com a contratante. A disponibilidade mínima de 99,5% é explícita.

## Evidência por requisito

A matriz legível pelo sistema está em `aderencia.json`. Uma funcionalidade marcada como implementada localmente significa que há fluxo executável nesta versão; não representa aceite municipal, certificação, validação clínica ou cumprimento automático de obrigação contratual.
