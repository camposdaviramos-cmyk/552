# Auditoria funcional do TR — 30/09/2026

Fonte primária: `TR.pdf`, 13 páginas digitalizadas, conferidas visualmente. O documento não possui camada de texto utilizável; as imagens de todas as páginas foram lidas. O mapa por seção permanece em `TR-MAPEADO.md`.

## Resultado e critério de classificação

A matriz foi desdobrada em **70 itens: 38 critérios de implementação local e 32 dependências externas**. Cada critério local possui escopo de aceite, arquivos de evidência e testes/validação. As dependências possuem descrição do insumo, responsável e próxima ação. A tela permite busca, filtro, abertura do PDF e exportação da auditoria.

O percentual local é calculado a partir dos estados dos critérios locais. Não é percentual de cumprimento do contrato: instalação cloud, disponibilidade, homologação oficial, prestação de serviços e atos administrativos não foram executados nem comprovados nesta auditoria. A cor vermelha marca essas dependências, mesmo quando uma capacidade local relacionada já está disponível.

O TR enumera módulos, mas não especifica fichas clínicas, leiautes, protocolos ou uma prova de conceito detalhada. Os critérios locais descritos na matriz tornam a implementação verificável. Protocolos municipais e aceites precisam ser validados com os responsáveis competentes. Assinatura qualificada, WhatsApp, SMS, push e lojas não são exigências nominalmente detalhadas no PDF; foram distinguidos de autoria local e comunicação dentro do portal.

## Lacunas encontradas e implementadas

| Área | Situação encontrada | Implementação e verificação local |
|---|---|---|
| Prontuário | SOAP genérico, sem anexos nem fichas específicas | Campos por linha de cuidado, odontograma de permanentes/decíduos, autoria e integridade HMAC, preservação após finalização, histórico de versões e impressão |
| Documentos/exames | Resultado textual, sem documentos vinculados | PDF/PNG/JPEG cifrados no banco, validação de formato/tamanho, download por perfil, liberação ao titular somente após laudo e proteção de documentos finalizados |
| Hospital | Internação/leito/alta, sem escalas ou checagem de prescrição | Escalas com intervalo e bloqueio de sobreposição; prescrição vinculada a paciente/unidade/internação; doses com horário, desfecho e autoria, sem checagem duplicada |
| Profissionais | Unicidade apenas do login | CPF único cifrado para contas assistenciais novas; identificação de contas anteriores pela administração; índice único e prevenção de duplicidade |
| Estoques | Movimentações locais sem transferência entre unidades | Transferência atômica, saída e entrada pareadas, preservação do saldo total e histórico em ambos os lotes |
| Patrimônio | Cadastro e situação | Tombamento único, eventos de inventário, transferência com origem/destino/responsável, proteção por versão e depreciação mensal parametrizada |
| TFD/frota | Viagens e capacidade básica | Intervalos, conflitos, roteiro manual ordenado, autorização/custeio por paciente, placa única, abastecimento/manutenção, despesas e hodômetro sem retrocesso |
| Produção SUS local | Competência e status, sem origem/conferência detalhada | Vínculo a atendimento concluído, compatibilidade paciente/unidade, bloqueio de mesmo procedimento por origem e motivo obrigatório de rejeição |
| Vigilância/BI | Registros e painel de agenda | Investigação/desfecho, população com fonte, confirmados distintos, taxas condicionadas ao denominador, filtros, agrupamentos, despesas, espera, absenteísmo, metas e CSV do recorte |
| Cidadão | Consulta de mensagens a cada 30 segundos | Atualização por eventos do servidor, revisão restrita ao titular, reconexão/fallback, revogação, instalação web e página offline sem dados privados em cache |
| Migração | CSV de pacientes | JSON dos módulos, simulação real em transação revertida, aplicação das regras de negócio no lote, gravação integral, origem/identificador estável e recibos contra reimportação |
| Suporte/treinamento | Registros simples de chamado/atividade | Acompanhamento com autoria, responsáveis/prazos, solução/evidência obrigatória ao concluir, presença/avaliação/carga horária, anexos e relatório imprimível; manual operacional |
| Aderência | Itens amplos misturavam código incompleto e obrigações externas | Critérios separados; todas as dependências externas em vermelho, com responsável e ação necessária; evidências rastreáveis |

## Dependências externas preservadas em vermelho

- Sistemas obrigatórios da página 9: e-SUS APS, SISAB, CNES, BPA, SIA/SUS e demais sistemas MS; tabela SIGTAP, versões/leiautes, acesso ao receptor e homologação. Nenhum conector foi declarado operacional.
- Bases reais de unidades/profissionais, população, parâmetros e metas; extração e mapeamento do legado.
- Laboratórios, certificados e canais externos complementares quando aplicáveis.
- Ambiente cloud, persistência, TLS, volumes/chaves, backup externo, logs externos, dimensionamento, monitoramento e comprovação de disponibilidade mínima de 99,5%.
- Equipes, telefone/e-mail, capacitações realmente realizadas, validações clínicas/institucionais, políticas de dados e aceites.
- Atestados, habilitação, contrato, OS, prazo de implantação, fiscalização, orçamento, certidões, notas fiscais e pagamentos.

O `vercel.json` solicitado anteriormente foi preservado. A aplicação usa SQLite, arquivos de chave, worker de backup e eventos de conexão persistente; é necessário prover um ambiente de produção compatível e persistente. A configuração de roteamento, isoladamente, não comprova essa implantação.

## Preservação e limites

Na revisão após relato de travamento, o servidor estava parado e foi iniciado novamente. Foram adicionados prazo de 30 segundos nas chamadas da interface e descarte de respostas atrasadas do portal após logout/troca de conta. A regressão verificou também seis portais simultâneos sem bloquear as consultas do servidor. Detalhes e evidências constam em `VALIDACAO.md` e `tests/browser_resilience.py`.

As alterações de esquema são aditivas (`CREATE TABLE IF NOT EXISTS`, novas colunas opcionais e índice). Não apagam registros existentes. Dados anteriores sem CPF profissional, novas fichas, vida útil ou população permanecem identificáveis para preenchimento; valores reais não são inventados. Documentos clínicos antigos finalizados continuam imutáveis; somente novos documentos finalizados recebem o selo local.

Os fluxos do navegador foram exercitados em banco temporário descartável. Os testes não efetuam envio a sistemas oficiais nem a provedores de mensagens. Os resultados e capturas estão descritos em `VALIDACAO.md`.

O ambiente local não comprova carga municipal, failover, homologação clínica/jurídica, certificação de assinatura nem disponibilidade contratual. Mensagens instantâneas exigem portal conectado; em sobrecarga do canal ou indisponibilidade de eventos, há atualização periódica. O worker de eventos limita conexões locais para preservar capacidade de resposta das demais rotas. Escala e monitoramento devem ser dimensionados na implantação.

Referências técnicas consultadas na implementação: [streaming no Flask](https://flask.palletsprojects.com/en/stable/patterns/streaming/) e [instalação de PWA no navegador](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable). Não foram usadas para substituir exigências do PDF ou produzir declaração jurídica de conformidade.
