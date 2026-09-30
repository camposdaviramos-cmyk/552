# Validação local — 30/09/2026

Ambiente: Windows, Python 3.14, Flask/Waitress, SQLite, Chrome instalado.

## Resultado

- **16 testes automatizados aprovados** em `tests/test_app.py`.
- Login, busca de paciente, prontuário e edição de cadastro verificados no navegador.
- **23 páginas/módulos** visitados e formulários dos 16 módulos operacionais abertos sem erros JavaScript.
- Layout conferido em 1440 px e 390 px, sem transbordamento horizontal no painel e no portal do cidadão.
- Snapshot criptografado criado em `instance/backups/`; restauração para arquivo separado validada pelo teste automatizado.
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

## Capturas

- `artifacts/dashboard-desktop.png`
- `artifacts/dashboard-mobile.png`
- `artifacts/prontuario.png`
- `artifacts/cidadao-mobile.png`

## O que esta validação não comprova

Não foram realizados testes de carga municipal, avaliação clínica, homologação de integração oficial, certificação de segurança, validação jurídica, execução de Docker/nuvem ou medição do SLA de 99,5%. Os resultados são locais e não substituem os critérios de aceite da contratante.
