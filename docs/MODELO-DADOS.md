# H2D - TI: Modelo de dados

Revisão de 05/11/2026 do modelo da seção 6 do plano. Mostra o que já existe, o que entra em cada fase e o que a revisão mudou. A fonte da verdade do que existe é [`models.py`](../apps/api/src/h2d/models.py) e as migrações; este documento explica o porquê.

**Versões verificadas no banco local:** PostgreSQL 17.11, pgvector 0.8.7 (tem varredura iterativa), pg_trgm 1.6.

## Convenções

- IDs UUID v7 gerados na aplicação: o PostgreSQL 17 não tem `uuidv7()` nativo.
- `timestamptz` em tudo; `created_at` e `updated_at` com valor do servidor.
- Migrações só por Alembic, uma por fase. `alembic check` roda nos testes e falha se o modelo e as migrações divergirem.
- Restrições no banco, não só na aplicação (e-mail em minúsculas, capacidade positiva, prazos coerentes).
- Prioridade P1 a P4 é um tipo enum do banco (`ticket_priority`), reaproveitado por `tickets`.

## Já existe (F1)

| Tabela | Observações |
| --- | --- |
| `users` | E-mail único e sempre em minúsculas (restrição no banco). `is_vip` alimenta a classificação. Desativar derruba a sessão na hora |
| `skills`, `technicians`, `technician_skills` | Horário em `jsonb`; capacidade máxima positiva |
| `sla_policies`, `sla_targets` | Os prazos ficam em `sla_targets` (uma linha por política e prioridade), e não em colunas da política |
| `categories` | Árvore por `parent_id`; nome único por pai, inclusive entre raízes (`NULLS NOT DISTINCT`) |
| `audit_log` | `actor_id` vira nulo se o usuário for removido: o histórico sobrevive |

## Entra por fase

| Fase | Tabelas | Observações |
| --- | --- | --- |
| F2 | `kb_documents`, `kb_document_versions`, `kb_chunks`, `ingestion_jobs` | Ver "Pontos de atenção" 1 a 4 |
| F3 | `conversations`, `messages`, `llm_calls`, `prompt_versions` | `messages` guarda só o texto já mascarado. `prompt_versions` é nova (D5) |
| F4 | `tickets`, `ticket_events`, `outbox_events`, `app_settings` | `app_settings` é nova (D5) e guarda limiares e regras de roteamento |
| F7 | `kb_drafts` | Nova (D5); só se o ciclo de aprendizado não for cortado |

## Pontos de atenção

A revisão encontrou estes pontos, que não estavam no plano:

1. **Dimensão do vetor.** `kb_chunks.embedding` é `vector(N)` e N depende do modelo escolhido no spike da F2 (ADR-003). O índice HNSW do pgvector aceita até 2.000 dimensões, o que cobre os modelos previstos (o BGE-M3 tem 1.024). Trocar para um modelo de outra dimensão exige migração, e não só reindexação.
2. **Visibilidade copiada.** Cada chunk repete a visibilidade do documento para o filtro rodar na mesma consulta. Mudar a visibilidade de um documento precisa atualizar os chunks na mesma transação, com teste que prove que nenhum trecho restrito vaza depois da mudança.
3. **Varredura iterativa.** Sem ela, o filtro de visibilidade pode devolver menos resultados que o pedido. Ela se liga com `SET hnsw.iterative_scan = relaxed_order` por sessão. O parâmetro só existe depois que a biblioteca do pgvector é carregada, então a conexão precisa usar o tipo `vector` antes (verificado: antes disso o PostgreSQL responde "unrecognized configuration parameter").
4. **Tabelas de outras ferramentas fora do Alembic.** O Procrastinate e o checkpointer do LangGraph criam as próprias tabelas. Se ficarem no esquema `public`, o `alembic check` (e o autogenerate) tentam apagá-las. Decisão: cada uma em esquema próprio (`procrastinate`, `checkpoints`), que o Alembic ignora por padrão.
5. **Código legível do chamado.** O plano mostra `H2D-0142`, mas nenhuma coluna o gera. `tickets` terá um número sequencial (`GENERATED ... AS IDENTITY`, único) e o código será derivado dele.
6. **Linha do tempo só acrescenta.** `ticket_events` e `audit_log` nunca sofrem `UPDATE` nem `DELETE` pela aplicação. O banco ainda não impede isso; um gatilho que bloqueie fica como melhoria.
7. **Retenção (LGPD).** `conversations` precisa de uma data de expiração e de exclusão a pedido. O prazo depende de decisão da empresa, e a tela só entra na F7.
8. **Idempotência do outbox.** `outbox_events.event_id` é único, para a reentrega ao n8n não duplicar aviso.
9. **Custo.** `llm_calls` guarda o custo em `numeric`, não em `float`, para a soma do dashboard bater.
