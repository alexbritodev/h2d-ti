# ADR-003: Modelo de embeddings

**Status:** decidida pelo tech lead em 05/11/2026.

## Contexto

A coluna `kb_chunks.embedding` é `vector(N)` e o índice HNSW depende de N, então a escolha vem antes da migração da F2. A VPS tem 7,8 GB de RAM, sem swap, dividida com outros projetos. Os embeddings rodam no próprio servidor (FastEmbed, ONNX em CPU), sem enviar texto a terceiros e sem gastar a cota do OpenRouter.

O "multilingual-e5" do plano existe (`intfloat/multilingual-e5-large`); o BGE-M3 citado no modelo de dados não está na lista do FastEmbed.

## Teste

22 perguntas em português sobre os 15 manuais fictícios (96 trechos, divididos por título `##`), mais 4 perguntas fora da base. "Acerto" é um dos trechos do topo conter a resposta. O CPU é o do PC de desenvolvimento, não o da VPS.

| Modelo | Dim. | Top-1 | Top-3 | Top-5 | Memória | Por pergunta |
| --- | --- | --- | --- | --- | --- | --- |
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | 13/22 | 18/22 | 20/22 | ~1,2 GB | 35 ms |
| paraphrase-multilingual-mpnet-base-v2 | 768 | 14/22 | 19/22 | 22/22 | ~3,2 GB | 114 ms |
| multilingual-e5-large | 1024 | 18/22 | 22/22 | 22/22 | ~3,8 GB | 404 ms |

Nenhum modelo separa bem "dentro da base" de "fora da base" só pela nota de similaridade (MiniLM: pior pergunta dentro 0,395, melhor fora 0,361).

## Decisão

**`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensões, local**, com busca híbrida (vetor + `tsvector` + RRF).

- É o único que cabe na VPS com folga: o modelo fica residente para embutir as perguntas do chat.
- A parte lexical da busca híbrida cobre números e termos exatos ("90 dias", `systemctl --failed`), onde o modelo pequeno é mais fraco.
- O e5-large é mais preciso, mas ~3,8 GB residentes só para isso inviabilizam a VPS atual (decidir sobre a KVM 4 só se a avaliação mostrar que precisa).

## Consequências

- `kb_chunks.embedding` é `vector(384)`, com índice HNSW em `vector_cosine_ops`. Trocar por um modelo de outra dimensão exige migração, além de reindexar tudo.
- Cada trecho guarda o nome do modelo (`embedding_model`), para reindexar de forma controlada e para a busca nunca misturar vetores de modelos diferentes.
- **O MiniLM lê poucos tokens por trecho** (limite próprio do modelo, na casa de 128 tokens). Os trechos precisam ser curtos, na ordem de 100 a 120 palavras, e isso precisa ser medido no chunking. Se o acerto ficar abaixo da meta, as saídas são: trechos menores, reranking (fase 1.5) ou um modelo maior em outro servidor.
- Como a nota de similaridade não separa "sabe" de "não sabe", a recusa "não encontrei" (F3) usa também a busca lexical e a checagem de fidelidade da resposta, e não só um limiar de similaridade.
- **Ressalva do teste:** as perguntas foram escritas a partir dos mesmos manuais, então o resultado é otimista. O conjunto de avaliação v0 deve ser escrito por outra pessoa e medido de novo.
- Fora do escopo do teste por licença: `jina-embeddings-v3` (uso não comercial).
