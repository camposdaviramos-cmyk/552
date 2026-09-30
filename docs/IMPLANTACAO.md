# Implantação e aceite

O TR exige implantação inicial em até 30 dias corridos a partir da Ordem de Serviço. O cronograma abaixo é uma proposta operacional; depende da disponibilização dos insumos e da conclusão das funcionalidades pendentes. Não é evidência de execução nem garantia de viabilidade de todas as homologações nesse prazo.

| Período | Atividades | Evidências para aceite |
|---|---|---|
| Dias 1–3 | Kickoff, responsáveis, unidades/CNES, profissionais, inventário de dados e detalhamento dos fluxos | Ata, mapa da rede, catálogo de perfis e escopo validado |
| Dias 4–7 | Infraestrutura, DNS/TLS, gestão de chaves, backups externos, monitoramento e carga de amostras | Evidências de configuração e teste de recuperação |
| Dias 8–14 | Migração piloto, validação de identidade/histórico, ajustes clínicos e testes de conectores oficiais | Relatório de reconciliação, erros corrigidos e retorno de homologação |
| Dias 15–21 | Capacitação assistencial, administrativa e gerencial; simulação por unidade | Material, listas de presença, avaliações e relatórios |
| Dias 22–26 | Piloto acompanhado, teste de carga, correções e validação do suporte | Relatório de testes, incidentes e tempos observados |
| Dias 27–30 | Carga final autorizada, conferência municipal, entrada em operação e aceite | Backup de corte, reconciliação final, ata e termo de aceite |

## Insumos que ainda precisam ser fornecidos

- Dados cadastrais oficiais das unidades e profissionais.
- Esquema, amostra autorizada e mecanismo de extração do legado.
- Protocolos e formulários usados por cada profissão, hospital e CAPS.
- Leiautes vigentes, ambiente de homologação e credenciais/certificados das integrações que os exigirem.
- Domínio, provedor, regras de acesso, política de backup/retenção e responsáveis por operação.
- Equipe de suporte, telefone, e-mail, horários e SLA de atendimento acordado.
- Políticas institucionais de tratamento de dados, responsáveis e critérios de aceite.
- Documentação e atestados da empresa licitante, que não são gerados por esta aplicação.

## Critérios de validação propostos

1. Um paciente não pode ser duplicado por CPF/CNS. O histórico deve permanecer vinculado ao mesmo identificador entre unidades.
2. Perfis sem autorização não consultam evoluções. O cidadão só consulta e altera ações permitidas sobre os próprios registros.
3. Agendamentos conflitantes e leitos ocupados são bloqueados.
4. Evoluções finalizadas não são sobrescritas; complementações entram como novos registros.
5. Movimentação concorrente não produz saldo negativo. Lote vencido não é dispensado.
6. Migração rejeita inconsistências e produz reconciliação quantitativa e amostral antes do aceite.
7. Arquivos oficiais só são considerados integrados após validação nos sistemas receptores e conferência dos retornos.
8. Backup é restaurado e comparado em ambiente separado; disponibilidade é medida externamente durante operação real.
9. Capacitação possui relatório e confirmação dos participantes. Suporte possui equipe, canais reais e histórico.
10. Aderência parcial permanece registrada como pendência até existir evidência de conclusão.

## Limites atuais de operação

Esta implementação foi verificada localmente. O backend usa SQLite e carrega listas de registros para filtragem e indicadores; paginação no servidor, índices analíticos, testes de carga e eventual migração para PostgreSQL precisam preceder escala municipal. A composição Docker disponibilizada não implementa replicação ou failover.

Os logs de auditoria detectam alteração de conteúdo e quebra dos vínculos HMAC, mas a própria base e a chave estão no mesmo ambiente. Preservação externa imutável e ancoragem periódica do último hash são necessárias para ampliar a resistência contra administradores de infraestrutura maliciosos e truncamento do final do histórico.

As chaves locais em `instance/keys.json` são um mecanismo de desenvolvimento. A operação real exige gestão separada, cópia protegida, rotação planejada e criptografia de volume. O procedimento de backup não prova sozinho conformidade LGPD nem garantia de disponibilidade.
