# Validação local — 30/09/2026

Ambiente: Windows, Python 3.14, Flask/Waitress, SQLite, Chrome instalado.

## Resultado

- **36 testes automatizados aprovados** em `tests/test_app.py` e `tests/test_workflows.py` (44,12 s na revisão após o relato de travamento).
- Login, busca de paciente, prontuário e edição de cadastro verificados no navegador.
- Roteiro de regressão original com **23 páginas/módulos** aprovado; roteiro ampliado abriu os **21 módulos operacionais**, além de aderência, indicadores, migração e usuários, sem erros JavaScript.
- Layout conferido em 1440 px e 390 px, sem transbordamento horizontal no painel e no portal do cidadão.
- Backup criptografado e restauração para arquivo separado validados em bancos temporários, incluindo anexos cifrados.
- Compilação dos arquivos Python concluída sem erros.

## Cenários de negócio e segurança cobertos

1. Sessão obrigatória, token CSRF e bloqueio de recursos por perfil.
2. Identificação de paciente válida, duplicidade rejeitada e conteúdo criptografado.
3. Evolução clínica finalizada preservada contra alteração.
4. Dispensação vinculada ao paciente, saldo insuficiente, lote vencido e histórico.
5. Conflito de agenda e edição concorrente por versão.
6. Cidadão sem acesso a registros de outro paciente.
7. Migração atômica e neutralização de fórmulas na exportação CSV.
8. Verificação de cadeia de auditoria e detecção de alteração.
9. Revogação de sessão após desativação do usuário.
10. Backup criptografado e restauração sem sobrescrita de arquivo existente.
11. Limitação de tentativas de login.
12. Atualização concorrente do paciente e autorização de cadastro de unidades.
13. Leito ocupado bloqueado e alta com data obrigatória.
14. Capacidade de transporte incluindo acompanhante.
15. Duas saídas de estoque simultâneas sem saldo negativo.
16. Resultado de exame não liberado ausente da resposta ao cidadão.
17. Fichas de seis linhas de cuidado, odontograma válido e selo de integridade do documento finalizado.
18. Plantões sobrepostos, inclusive durante a noite, bloqueados por profissional.
19. Prescrição vinculada ao paciente/unidade da internação; doses duplicadas ou fora da vigência recusadas; conteúdo preservado após checagem.
20. Anexos cifrados, formatos/tamanho, autorização, liberação de laudos e inclusão no backup.
21. Tombamento único, transferência/inventário versionados e depreciação com limite residual.
22. Intervalos e custeio de transporte; placa única, manutenção, despesas e hodômetro sem retrocesso.
23. Transferência de estoque atômica preservando o total e registrando os dois movimentos.
24. Origem compatível da produção, prevenção de duplicidade e motivo obrigatório de rejeição.
25. População com fonte, confirmados distintos, filtros, metas e ausência de taxa quando falta denominador aplicável.
26. Acompanhamento de suporte, solução ao concluir, treinamento com evidência de execução.
27. Importação de registros: simulação sem persistência, reversão integral de lote inválido, recibo e prevenção de reimportação.
28. Eventos do portal restritos ao titular, revogação e acesso por perfil às novas rotas.
29. Identificação única por CPF cifrado de profissionais novos e atualização dos cadastros anteriores.
30. Autorização de regulação com data e bloqueio de segunda internação ativa do paciente.
31. Matriz com 70 IDs únicos, evidências locais e dependências com responsável/ação; acesso ao PDF.
32. Corpo JSON inválido recusado; indicadores de vigilância não expõem produção de módulos sem permissão.

## Fluxos completos no navegador

O roteiro `tests/browser_workflows.py` cadastra evolução odontológica, escolhe dente/condição, inclui PDF, finaliza, confirma bloqueio de edição e abre relatório. Executa inventário, filtros da aderência vermelha, indicadores em celular, importação com recibo e identificação de profissional pela interface. Em sessão separada do cidadão, verifica recebimento de nova mensagem sem recarga manual, isolamento de outro titular e página offline sem cache das APIs.

Os roteiros de navegador usaram `tests/browser_server.py` na porta 8081, com base temporária. Não alteraram a base de demonstração em `instance/`.

Para repetir, inicie em um terminal:

```powershell
.\.venv\Scripts\python.exe tests\browser_server.py
```

Em outro terminal, execute os roteiros uma vez sobre essa instância descartável:

```powershell
$env:INTEGRA_TEST_URL='http://127.0.0.1:8081'
.\.venv\Scripts\python.exe tests\browser_workflows.py
.\.venv\Scripts\python.exe tests\browser_check.py
```

Reinicie a instância descartável antes de repetir o roteiro de criação, pois ele testa tombamentos e identificadores únicos. A compilação Python e `git diff --check` também passaram. Docker e deploy não foram executados.

## Revisão após relato de travamento

Na inspeção, não havia servidor escutando nas portas 8080/8081; as conexões eram recusadas. O servidor principal foi iniciado com `run.py`, e `/api/health` retornou HTTP 200. Isso confirma a recuperação local, sem presumir a causa do encerramento anterior.

A revisão também corrigiu requisições da interface sem limite de espera: agora há prazo de 30 segundos, mensagem de falha e liberação dos botões pelos fluxos existentes. Em operações de gravação que excedem o prazo, o usuário é orientado a conferir o registro antes de repetir, pois o servidor pode ter concluído a transação. Não há repetição automática de gravações.

Respostas atrasadas do portal são descartadas quando a conta muda ou uma consulta mais recente já foi iniciada. Assim, uma resposta anterior não volta a exibir o portal depois do logout.

`tests/browser_resilience.py` passou em instância descartável: prazo de leitura e gravação, logout com resposta atrasada e servidor respondendo a consultas com seis portais simultâneos. Esse cenário é uma regressão de concorrência local, não um teste de capacidade municipal ou SLA.

```powershell
.\.venv\Scripts\python.exe tests\browser_resilience.py
```

## Capturas

- `artifacts/dashboard-desktop.png`
- `artifacts/dashboard-mobile.png`
- `artifacts/prontuario.png`
- `artifacts/cidadao-mobile.png`
- `artifacts/relatorio-clinico.png`
- `artifacts/aderencia-auditada.png`
- `artifacts/aderencia-mobile.png`
- `artifacts/indicadores-mobile.png`
- `artifacts/cidadao-tempo-real.png`

## O que esta validação não comprova

Não foram realizados testes de carga municipal, avaliação clínica, homologação de integração oficial, certificação de segurança, validação jurídica, execução de Docker/nuvem ou medição do SLA de 99,5%. Os resultados são locais e não substituem os critérios de aceite da contratante.
