# Integra Saúde

Plataforma web de gestão municipal de saúde, desenvolvida a partir das **13 páginas do TR.pdf** da Secretaria Municipal de Saúde de Conceição de Macabu/RJ.

**Situação: versão funcional local de demonstração, com backend e persistência. Não está homologada nem comprova atendimento integral ao TR.** A matriz dentro do sistema e [docs/aderencia.json](docs/aderencia.json) distinguem implementação local, atendimento parcial e dependências externas.

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

- Painel calculado a partir da base, filtros por unidade/período, agenda do dia, alertas e relatórios CSV.
- Cadastro único com validação de CPF/CNS, busca, atualização, prevenção de duplicidade e histórico municipal.
- Agenda com profissional, unidade, especialidade, controle de conflito e situação do atendimento.
- Evolução SOAP por linha de cuidado: atenção básica, médico, enfermagem, odontologia, CAPS e hospitalar. Registros finalizados são imutáveis.
- Internações com leito, prevenção de dupla ocupação, alta e transferência.
- Regulação com prioridade, justificativa, autorização e fila de espera.
- Solicitações de exames/procedimentos e resultados textuais.
- Vigilância com agravo, território, classificação e acompanhamento.
- Farmácia e almoxarifado com lotes, validade, saldo, mínimo, movimentações e dispensação por paciente. Saídas de lote vencido ou acima do saldo são bloqueadas.
- Patrimônio, frota, viagens TFD e controle de capacidade por veículo/horário, incluindo acompanhantes.
- Produção SUS por competência, conferência e exportação interna em CSV.
- Demandas judiciais com prazos e alertas.
- Mensagens individuais no portal; cidadão acessa somente seus dados, confirma/cancela agenda e acompanha solicitações/exames liberados.
- Chamados de suporte/manutenção, atividades de implantação e relatórios textuais de capacitação.
- Gestão de unidades/CNES e usuários em 13 perfis; desativação revoga sessões existentes.
- Trilha de auditoria encadeada, criptografia dos conteúdos sensíveis, proteção CSRF e bloqueio temporário de tentativas de login.
- Migração de cadastro em CSV com validação prévia e gravação atômica.
- Backup criptografado consistente e restauração para um arquivo separado.

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

Esse roteiro verifica a navegação, busca, prontuário, módulos, estoque, portal do cidadão e responsividade. Capturas ficam em `artifacts/`. Não é um teste de carga ou homologação clínica.

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
- `static/`: interface responsiva sem CDN e sem dependências de frontend.
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

## Pendências para atendimento integral

O TR descreve um objeto de contratação amplo. Construir telas para cada nome de módulo não equivale a homologar todos os processos da saúde municipal.

1. **Integrações oficiais:** conectores e validação dos leiautes e fluxos de e-SUS APS, SISAB, CNES, BPA, SIA/SUS e demais sistemas MS. O CSV entregue é interno e não deve ser enviado como arquivo oficial BPA/SIA.
2. **Fluxos assistenciais especializados:** aprofundar fichas de cada profissão, odontograma, protocolos CAPS, prescrição hospitalar, anexos, assinaturas e validação com responsáveis clínicos.
3. **Aplicativo/mensageria:** o portal responsivo tem manifesto e consulta de mensagens a cada 30 segundos; não há aplicativo nativo, push, WhatsApp ou SMS conectado. Não há envio externo de mensagens.
4. **Operação e SLA:** implantação real, teste de carga, monitoramento externo, disponibilidade de 99,5%, recuperação de desastre e equipe de suporte por telefone/e-mail.
5. **Migração:** mapeamento dos históricos e demais tabelas do sistema legado, amostras, reconciliação e aceite municipal.
6. **Governança:** validação institucional das obrigações LGPD/MS/DATASUS, políticas de acesso e retenção, documentação e evidências de execução.
7. **Licitação e contrato:** atestados da licitante, certidões, documentação jurídica, proposta, aceite, notas fiscais e demais obrigações administrativas. Não são comprovados por software.

Consulte [o mapa do TR](docs/TR-MAPEADO.md), [o plano de implantação](docs/IMPLANTACAO.md) e a matriz no próprio sistema. Não foi declarado atendimento integral, homologação oficial ou garantia de resultado na licitação.
