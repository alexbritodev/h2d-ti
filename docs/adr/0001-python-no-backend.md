# ADR-001: Python no backend

**Status:** proposta, aguardando confirmação de Darles e Hanover. A F1 já foi construída assim, então mudar agora custa refazer a API.

**Data:** 04/11/2026

## Contexto

O backend precisa de parsing de documentos, RAG e agentes, com entrega em 18/11/2026. As alternativas são Python ou TypeScript (Fastify ou NestJS).

## Decisão

Python 3.12 com FastAPI, Pydantic v2, SQLAlchemy 2 e Alembic.

## Consequências

- Docling, LangGraph e Ragas funcionam direto, sem um serviço à parte só para parsing.
- Front e back não compartilham tipos no código. O contrato OpenAPI, gerado e checado no CI, cobre essa diferença.
- Quem não conhece Python precisa de um tempo de adaptação, o que pesa com o prazo curto.
