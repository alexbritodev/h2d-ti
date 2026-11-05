# ADR-002: Divergências do plano e premissas da F0

**Status:** decidida pelo tech lead em 05/11/2026. Itens marcados com ⚠ ainda precisam da confirmação de Darles e Hanover ou de dados que só o time de TI tem.

## Contexto

Ao ler o plano do projeto apareceram inconsistências que mudam a ordem de construção. Cada decisão abaixo vale até alguém abrir um novo ADR que a substitua.

## Divergências

| # | Decisão | Por quê |
| --- | --- | --- |
| D1 | Custo **por conversa** entra no MVP; custo por chamado e lacunas da base ficam para depois | Custo por conversa é critério de sucesso do MVP; o resto é fase 2 |
| D2 | A API serve os webhooks do n8n em `/api/hooks/n8n/*`, chamados pela rede interna do Docker. O Caddyfile responde 404 a `/api/hooks/*` | Um único prefixo público (`/api`); webhook nunca passa pela internet |
| D3 | O n8n não acessa o banco `h2d`. Consultas como "chamados em risco" viram endpoints assinados com HMAC | Regra de negócio fica no backend, com teste e versão |
| D4 | O n8n **não é exposto publicamente** no MVP: não existe `hooks.<domínio>` até a fase 2 | Nenhum gatilho externo chega ao n8n no MVP |
| D5 | Tabelas novas: `prompt_versions` (F3), `app_settings` (F4, com as regras de roteamento) e `kb_drafts` (F7). `sla_targets` já existe desde a F1 | A tela de IA, o roteamento e o ciclo de aprendizado precisam de onde gravar |
| D6 | Endpoints novos: avaliação CSAT, histórico de conversas, carga do técnico | Faltavam no documento-base |
| D7 | O campo de solução aplicada entra na F4; o rascunho de artigo na F7, cortável | O ciclo de aprendizado não tinha sprint |
| D8 | Mascaramento de dados e aviso de IA entram na F3, antes da primeira chamada ao LLM | A conversa não pode sair do servidor sem proteção |
| D9 | ⚠ O modelo de embeddings sai de um spike de meio dia na F2 (ADR-003). "multilingual-e5" parece erro de digitação | Não foi verificado se os modelos citados existem no FastEmbed nem se o OpenRouter oferece embeddings |
| D10 | ERP moderno com temática de TI, tema claro por padrão, base em preto e cinza | O console denso foi reprovado ao ser visto |
| D11 | A interface usa primitivas do Radix com componentes próprios em Tailwind, e **não** o CLI do shadcn/ui | O CLI mexe em arquivos do projeto e os componentes já estavam prontos; o `components.json` foi removido por não ter uso |

## Premissas da F0

Valem até o time de TI real dizer o contrário.

| Assunto | Premissa |
| --- | --- |
| Entrega | 18/11/2026 |
| Piloto | 50 usuários e 100 documentos |
| Notificação | E-mail. Outro canal só se o time de TI usar |
| Manuais | 10 a 15 fictícios, escritos pelo time |
| Prazos de SLA | P1: 30 min / 4 h · P2: 1 h / 8 h · P3: 4 h / 24 h · P4: 8 h / 3 d (1ª resposta / resolução). Provisórios |
| LLM | OpenRouter, com limite mensal de gasto configurado no provedor ⚠ |
| Backend | Python (ADR-001) ⚠ |

## Consequências

- A F2 começa com o spike de embeddings, porque a dimensão do vetor define a coluna `kb_chunks.embedding`.
- As telas de Cadastros, Auditoria e Configurações existem só como demonstração. ⚠ Falta decidir se Cadastros ganha backend até 18/11.
