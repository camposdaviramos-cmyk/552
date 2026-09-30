# Integra Saúde

Plataforma web de gestão municipal de saúde, desenvolvida a partir das **13 páginas do TR.pdf** da Secretaria Municipal de Saúde de Conceição de Macabu/RJ.

**Situação após auditoria das 13 páginas: 38 critérios locais implementados e 32 dependências externas identificadas.** A [matriz](docs/aderencia.json) descreve os critérios e as evidências. As dependências externas aparecem em vermelho no sistema. O percentual local não representa homologação nem atendimento integral do contrato. Veja o [relatório da auditoria](docs/AUDITORIA-TR.md).

## Abrir a demonstração

No PowerShell, na pasta do projeto:

```powershell
.\iniciar.ps1
```

Se o ambiente já estiver preparado:

```powershell
.\.venv\Scripts\python.exe run.py
```

Acesse **http://127.0.0.1:8080**. O botão **Acessar demonstração** preenche o acesso de demonstração.

| Perfil | Usuário | Senha de demonstração |
|---|---|---|
| Administrador | `admin` | `Demo@Saude2026!` |
| Gestor municipal | `gestor` | `Demo@Saude2026!` |
| Assistencial | `laura` ou `andre` | `Demo@Saude2026!` |
| Recepção | `recepcao` | `Demo@Saude2026!` |
| Farmácia | `farmacia` | `Demo@Saude2026!` |
| Cidadão | `cidadao` | `Demo@Saude2026!` |

O portal do cidadão também abre em **http://127.0.0.1:8080/cidadao**. As contas acima são exclusivamente demonstrativas. A carga contém 80 pacientes fictícios, 19 unidades e registros de exemplo em todos os módulos. Nomes de UBS, veículos, valores e registros assistenciais são demonstrativos; somente as denominações expressamente identificadas no TR foram preservadas.

## Funcionalidades executáveis

- Cadastro único de pacientes, unidades e profissionais; CPF profissional único e cifrado para novas contas assistenciais, com identificação de contas anteriores pela administração.
- Prontuário municipal com SOAP, fichas específicas de atenção básica, médico, enfermagem e CAPS; odontograma de permanentes/decíduos; autoria, selo de integridade local e finalização imutável.
- Anexos PDF/PNG/JPEG cifrados no banco, histórico de versões, liberação de laudos, acesso do titular e relatório imprimível.
- Agenda, regulação, leitos, alta/transferência, escalas sem sobreposição, prescrições vinculadas à internação e checagem individual de doses sem duplicação.
- Estoque, lotes, validade e dispensação por paciente; transferência entre unidades com saída/entrada atômicas e histórico.
- Patrimônio com tombamento único, inventário, transferências e cálculo linear de depreciação por parâmetros cadastrados.
- Transporte/TFD com capacidade incluindo acompanhante, intervalos, roteiro manual ordenado e custeio; frota com placa única, despesas, abastecimento e hodômetro sem retrocesso.
- Produção local SUS vinculada ao atendimento, conferência/rejeição com parecer e bloqueio de duplicidade; CSV interno, sem alegação de arquivo oficial BPA/SIA.
- Vigilância, investigação, desfechos, bases populacionais com fonte, indicadores epidemiológicos, metas de gestão e BI por período/unidade com exportação do recorte.
- Portal instalável por navegador compatível, mensagens por eventos enquanto conectado, confirmação de agenda, resultados e anexos liberados; página offline sem cache de dados de saúde.
- Suporte e treinamento com acompanhamento, responsáveis, presença, carga horária, evidências, anexos e relatórios. [Manual operacional](static/manual.html) disponível no menu.
- Importação CSV de pacientes e JSON dos módulos com simulação transacional, identificadores de origem, recibos de reconciliação e bloqueio de reimportação.
- 12 perfis, CSRF, isolamento do titular, bloqueio de tentativas, revogação de acesso, auditoria encadeada e backups consistentes cifrados com restauração não destrutiva.

## Roteiro de demonstração

1. Entre como administrador, filtre o painel e abra a agenda.
2. Em **Cadastro de pacientes**, busque Maria, abra o histórico e consulte uma evolução finalizada.
3. Cadastre um paciente com CPF/CNS válido. Tente repetir o cadastro para verificar a deduplicação.
4. Registre um agendamento e uma evolução. Finalize a evolução e comprove que ela fica somente para consulta.
5. Em **Assistência farmacêutica**, abra as setas do lote, registre uma dispensação e confira o saldo e o histórico do paciente.
6. Consulte regulação, internações, TFD e demandas judiciais.
7. Abra o portal com o usuário `cidadao` em outro navegador/perfil. Confirme uma consulta e confira a atualização no ambiente administrativo.
8. Em **Trilha de auditoria**, veja os eventos e a verificação da cadeia.
9. Em **Migração de dados**, baixe o modelo, valide o CSV e só então importe.
10. Apresente **Aderência ao TR** e **Integrações SUS** para distinguir o que foi demonstrado do que ainda requer homologação.

## Instalação manual

Requer Python 3.11 ou superior; desenvolvimento e testes realizados com Python 3.14 no Windows.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe seed.py --demo
.\.venv\Scripts\python.exe run.py
```

A carga é idempotente: não altera a base se já existir algum usuário. O servidor utiliza Waitress, sem modo de debug, e escuta apenas no endereço local por padrão.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam bancos temporários e cobrem autenticação, CSRF, perfis, CPF/CNS, criptografia, evolução imutável, estoque, conflitos e concorrência de edição, isolamento do cidadão, migração atômica, integridade de auditoria, revogação de acesso e restauração.

Com o servidor local aberto e o Chrome instalado no caminho padrão:

```powershell
.\.venv\Scripts\python.exe tests\browser_check.py
```

Esse roteiro verifica a navegação, busca, prontuário, módulos, estoque, portal do cidadão e responsividade. `tests/browser_workflows.py` valida os novos fluxos contra uma instância descartável indicada por `INTEGRA_TEST_URL` (padrão: porta 8081). Capturas ficam em `artifacts/`. Não é um teste de carga ou homologação clínica.

## Backups

```powershell
# Backup único
.\.venv\Scripts\python.exe backup.py

# Backup automático a cada hora, mantendo os últimos 168 arquivos
.\.venv\Scripts\python.exe backup.py --watch --interval 3600 --retain 168

# Restauração validada para um NOVO arquivo; não sobrescreve a base em uso
.\.venv\Scripts\python.exe backup.py --restore instance\backups\ARQUIVO.db.enc --output instance\restaurado.db
```

Os snapshots usam a API de backup do SQLite, verificação de integridade e criptografia autenticada. A chave está em `instance/keys.json` no ambiente local; guarde-a separadamente e proteja seu acesso. Sem ela não é possível recuperar os dados. As chaves não entram no backup do banco.

O worker precisa estar ativo para produzir backups automáticos. A composição Docker inclui esse serviço. A cópia para armazenamento externo, monitoramento de falhas, política institucional de retenção e recuperação de desastre precisam ser configurados na implantação. RPO e RTO não foram aferidos.

## Arquitetura

```text
Navegador / portal responsivo
          │ mesma origem, sessão e CSRF
          ▼
Flask + Waitress ─── autorização por perfil
          │
          ├── SQLite / transações / referências entre módulos
          ├── conteúdo cadastral e clínico criptografado
          ├── auditoria HMAC encadeada
          └── backup criptografado
```

- `saude/catalog.py`: contratos dos formulários, módulos e perfis.
- `saude/app.py`: API, validações, autorização e fluxos.
- `saude/db.py`: esquema, serialização criptografada e auditoria.
- `saude/workflows.py`: validações, anexos, eventos, transferências e autoria.
- `saude/analytics.py`: indicadores, metas e exportação filtrada.
- `saude/migration.py`: importação transacional de registros e recibos.
- `static/`: interface, fichas especializadas, manual e PWA, sem CDN.
- `seed.py`: dados e contas fictícias.
- `backup.py`: snapshot, retenção e restauração.
- `docs/`: rastreabilidade, plano e pendências.

SQLite é uma escolha para demonstração e instalação inicial em uma única instância. A capacidade para a rede municipal inteira precisa de testes de carga. Escalabilidade horizontal, alta disponibilidade e replicação exigem arquitetura de banco apropriada antes de assumir o SLA.

## Implantação em nuvem

Os arquivos `Dockerfile`, `compose.yaml` e `Caddyfile` preparam aplicação, worker de backup e proxy HTTPS. **A composição não foi executada neste ambiente, que não possui Docker.**

Em um servidor com Docker e domínio apontado:

```sh
export DOMAIN=saude.exemplo.gov.br
docker compose up -d --build
docker compose exec app python manage.py
```

Depois de criar o administrador, cadastre as unidades oficiais pela interface. A imagem não contém a carga demonstrativa. `APP_DEMO=0` remove o atalho da demonstração, mas **não apaga contas ou dados existentes**; use uma base vazia para implantação real.

O proxy solicita certificados para o domínio configurado. Acesso público, DNS, firewall, gestão de chaves, disco criptografado, cópia externa dos backups, monitoramento e dimensionamento devem ser verificados antes de inserir dados reais. O Compose descreve uma única instância e não comprova alta disponibilidade.

## Dependências externas para atendimento integral

Os 32 itens vermelhos da matriz especificam dependência, responsável e próxima ação. Incluem dados oficiais da rede e população; bases e versões de e-SUS APS, SISAB, CNES, SIGTAP, BPA e SIA/SUS; sistemas laboratoriais; legado; certificados quando aplicáveis; infraestrutura cloud/TLS, cópias externas, monitoramento e SLA; execução real de suporte e treinamento; validações institucionais; e obrigações licitatórias/contratuais.

As fichas registram avaliações e condutas informadas pelo profissional. Não geram diagnóstico nem recomendam dose. O selo HMAC local atesta integridade/autoria dentro da aplicação e não substitui assinatura qualificada. O TR não detalha padrões de assinatura nem exige nominalmente SMS, WhatsApp, push ou lojas; esses complementos estão identificados separadamente das funções locais de portal e mensagens.

`vercel.json` direciona rotas a `run.py`. Essa configuração não converte o banco SQLite local em armazenamento persistente de uma plataforma serverless. O ambiente de produção precisa oferecer persistência e execução apropriadas para o servidor, eventos e backups; essa dependência aparece em vermelho.

Consulte [a auditoria](docs/AUDITORIA-TR.md), [a validação](docs/VALIDACAO.md), [o mapa do TR](docs/TR-MAPEADO.md) e [o plano de implantação](docs/IMPLANTACAO.md).
