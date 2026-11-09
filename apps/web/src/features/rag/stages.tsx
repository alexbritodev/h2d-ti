import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/primitives";

import type { RagChunk, RagOverview, RagTrace } from "./api";
import {
  Chip,
  CodeBox,
  formatNumber,
  HeatStrip,
  Kpi,
  KpiRow,
  Legend,
  ScoreBar,
  SectionLabel,
} from "./parts";

type Token = { text: string; id: number };

const isSpecial = (token: Token) => /^<.*>$/.test(token.text);

/** Os tokens do modelo, com os que passam da janela de leitura esmaecidos. */
export function TokenChips({ tokens, limit }: { tokens: Token[]; limit: number }) {
  return (
    <div className="flex flex-wrap gap-1">
      {tokens.map((token, index) => {
        const outside = index >= limit;
        const shown = token.text.replace(/^▁/, "") || "▁";
        return (
          <Chip
            key={index}
            tone={outside || isSpecial(token) ? "dim" : "neutral"}
            title={`id ${token.id}${token.text.startsWith("▁") ? " · começa uma palavra" : ""}${outside ? " · fora da janela do modelo" : ""}`}
          >
            {token.text.startsWith("▁") && <span className="mr-0.5 text-muted">▁</span>}
            {shown === "▁" ? "" : shown}
          </Chip>
        );
      })}
    </div>
  );
}

function WindowUse({ count, limit }: { count: number; limit: number }) {
  const over = count > limit;
  return (
    <div className="mt-3">
      <div className="mb-1 flex items-center justify-between text-xs text-muted">
        <span>
          {count} de {limit} tokens da janela do modelo
        </span>
        {over && (
          <Badge tone="warn">
            <AlertTriangle aria-hidden className="size-3" /> {count - limit} fora da janela
          </Badge>
        )}
      </div>
      <Progress value={(count / limit) * 100} tone={over ? "warn" : "accent"} label="Uso da janela do modelo" />
    </div>
  );
}

export function MaskingStage({ trace }: { trace: RagTrace }) {
  const { masking } = trace;
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        Senha, CPF, cartão e token são escondidos antes de qualquer gravação, busca ou envio ao modelo.
        Esta tela também nunca devolve o texto original.
      </p>
      <SectionLabel>Pergunta depois da máscara</SectionLabel>
      <CodeBox>{masking.masked_text}</CodeBox>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge tone={masking.redactions ? "warn" : "accent"} dot>
          {masking.redactions
            ? `${masking.redactions} dado(s) escondido(s)`
            : "Nada sensível encontrado"}
        </Badge>
        {masking.kinds.map((kind) => (
          <Badge key={kind} mono>
            {kind}
          </Badge>
        ))}
      </div>
    </div>
  );
}

export function TokenizationStage({ trace }: { trace: RagTrace }) {
  const { tokenization: t } = trace;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="min-w-0">
        <SectionLabel>Tokens do modelo de embeddings</SectionLabel>
        {t.model_tokens.length ? (
          <>
            <TokenChips tokens={t.model_tokens} limit={t.model_max_tokens} />
            <WindowUse count={t.model_token_count} limit={t.model_max_tokens} />
          </>
        ) : (
          <p className="text-sm text-muted">Este modelo não expõe o tokenizador.</p>
        )}
        <p className="mt-3 text-xs text-muted">
          O modelo quebra o texto em pedaços de palavra. Cada token vira um número (passe o mouse para ver o id).
        </p>
      </div>
      <div className="min-w-0">
        <SectionLabel>Radicais na busca por palavras</SectionLabel>
        <div className="flex flex-wrap gap-1">
          {t.words.map((word) =>
            word.lexeme ? (
              <Chip key={word.word} tone="accent" title={`${word.word} → ${word.lexeme}`}>
                {word.word !== word.lexeme ? `${word.word} → ${word.lexeme}` : word.lexeme}
              </Chip>
            ) : (
              <Chip key={word.word} tone="struck" title="Palavra vazia: sai da busca por palavras">
                {word.word}
              </Chip>
            ),
          )}
        </div>
        <Legend
          items={[
            { className: "bg-accent", label: "entra na busca (radical)" },
            { className: "bg-muted", label: "palavra vazia, descartada" },
          ]}
        />
        <div className="mt-4 space-y-2">
          <div>
            <div className="mb-1 text-xs text-muted">Consulta montada (palavras ligadas por OU)</div>
            <CodeBox>{t.tsquery_raw || "—"}</CodeBox>
          </div>
          <div>
            <div className="mb-1 text-xs text-muted">Como o Postgres entende a consulta</div>
            <CodeBox>{t.tsquery_parsed || "—"}</CodeBox>
          </div>
        </div>
      </div>
    </div>
  );
}

export function EmbeddingStage({ trace }: { trace: RagTrace }) {
  const { embedding } = trace;
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        A pergunta vira uma lista de {embedding.dimensions} números. Perguntas de sentido parecido ficam
        com vetores parecidos, mesmo sem palavras em comum.
      </p>
      <HeatStrip values={embedding.values} label={`Vetor de ${embedding.dimensions} dimensões da pergunta`} />
      <Legend
        items={[
          { className: "bg-accent", label: "valor positivo" },
          { className: "bg-muted", label: "valor negativo" },
        ]}
      />
      <KpiRow>
        <Kpi value={embedding.dimensions} label="dimensões" />
        <Kpi value={formatNumber(embedding.norm, 3)} label="norma (comprimento do vetor)" />
        <Kpi value={formatNumber(embedding.minimum, 3)} label="menor valor" />
        <Kpi value={formatNumber(embedding.maximum, 3)} label="maior valor" />
        <Kpi value={embedding.model.split("/").pop()} label="modelo local" />
      </KpiRow>
    </div>
  );
}

interface ResultButtonProps {
  title: string;
  breadcrumb: string;
  rank: number;
  value: string;
  width: number;
  barClass: string;
  onOpen: () => void;
}

function ResultRow({ title, breadcrumb, rank, value, width, barClass, onOpen }: ResultButtonProps) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        title={breadcrumb}
        className="w-full cursor-pointer rounded-lg px-2 py-1.5 text-left hover:bg-surface-2"
      >
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="min-w-0 truncate">
            <span className="mr-2 font-mono text-xs text-muted">#{rank}</span>
            {breadcrumb || title}
          </span>
          <span className="font-mono text-xs tabular-nums">{value}</span>
        </div>
        <ScoreBar parts={[{ value: width, className: barClass }]} label={`${breadcrumb}: ${value}`} />
      </button>
    </li>
  );
}

export function SearchStage({ trace, onOpen }: { trace: RagTrace; onOpen: (id: string) => void }) {
  const topLexical = Math.max(...trace.lexical.map((hit) => hit.score), 1e-9);
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        Duas buscas independentes sobre até {trace.candidates} candidatos cada. Um trecho pode aparecer só
        em uma delas. Clique num trecho para ver como ele foi guardado.
      </p>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="min-w-0">
          <SectionLabel>Vetorial · similaridade de cosseno</SectionLabel>
          {trace.vector.length ? (
            <ul className="space-y-0.5">
              {trace.vector.map((hit) => (
                <ResultRow
                  key={hit.chunk_id}
                  title={hit.title}
                  breadcrumb={hit.breadcrumb}
                  rank={hit.rank}
                  value={formatNumber(hit.similarity, 3)}
                  width={Math.max(0, hit.similarity) * 100}
                  barClass="bg-accent"
                  onOpen={() => onOpen(hit.chunk_id)}
                />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Nenhum trecho na base.</p>
          )}
        </div>
        <div className="min-w-0">
          <SectionLabel>Por palavras · ts_rank_cd</SectionLabel>
          {trace.lexical.length ? (
            <ul className="space-y-0.5">
              {trace.lexical.map((hit) => (
                <ResultRow
                  key={hit.chunk_id}
                  title={hit.title}
                  breadcrumb={hit.breadcrumb}
                  rank={hit.rank}
                  value={formatNumber(hit.score, 3)}
                  width={(hit.score / topLexical) * 100}
                  barClass="bg-warn"
                  onOpen={() => onOpen(hit.chunk_id)}
                />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Nenhum trecho contém essas palavras.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export function FusionStage({ trace, onOpen }: { trace: RagTrace; onOpen: (id: string) => void }) {
  const peak = Math.max(...trace.fusion.map((row) => row.score), 1e-9);
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        Cada lista dá 1 / ({trace.rrf_k} + posição) ao trecho, e as notas se somam. Quem aparece nas duas
        sobe. Os {trace.search_limit} primeiros vão ao prompt.
      </p>
      {trace.fusion.length ? (
        <ul className="space-y-0.5">
          {trace.fusion.map((row, index) => (
            <li key={row.chunk_id}>
              <button
                type="button"
                onClick={() => onOpen(row.chunk_id)}
                title={row.snippet}
                className="w-full cursor-pointer rounded-lg px-2 py-1.5 text-left hover:bg-surface-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="min-w-0 truncate">
                    <span className="mr-2 font-mono text-xs text-muted">#{index + 1}</span>
                    {row.breadcrumb || row.title}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Badge mono>vet {row.vector_rank ? `#${row.vector_rank}` : "—"}</Badge>
                    <Badge mono>pal {row.lexical_rank ? `#${row.lexical_rank}` : "—"}</Badge>
                    <span className="w-14 text-right font-mono text-xs tabular-nums">
                      {formatNumber(row.score, 4)}
                    </span>
                    {row.selected ? (
                      <Badge tone="accent" dot>
                        vai ao prompt
                      </Badge>
                    ) : (
                      <span className="w-[6.5rem]" />
                    )}
                  </span>
                </div>
                <ScoreBar
                  label={`Contribuição ao trecho ${index + 1}`}
                  parts={[
                    { value: (row.vector_part / peak) * 100, className: "bg-accent" },
                    { value: (row.lexical_part / peak) * 100, className: "bg-warn" },
                  ]}
                />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">Sem candidatos para fundir.</p>
      )}
      <Legend
        items={[
          { className: "bg-accent", label: "parte da busca vetorial" },
          { className: "bg-warn", label: "parte da busca por palavras" },
        ]}
      />
    </div>
  );
}

export function PromptStage({ trace }: { trace: RagTrace }) {
  const { prompt } = trace;
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        É este texto que seguiria ao modelo: as regras, as últimas {prompt.history_messages} mensagens da
        conversa, os trechos como dados numerados e a pergunta.
      </p>
      <SectionLabel>Fontes e pergunta</SectionLabel>
      {prompt.sources_block ? (
        <CodeBox className="max-h-72 overflow-y-auto">
          {`${prompt.sources_block}\n\nPergunta: ${prompt.question}`}
        </CodeBox>
      ) : (
        <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted">
          Sem trechos, o chat nem chama o modelo: responde que não encontrou e oferece abrir chamado.
        </p>
      )}
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted hover:text-text">Ver as regras do sistema</summary>
        <CodeBox className="mt-2">{prompt.system_prompt}</CodeBox>
      </details>
      {prompt.sources.length > 0 && (
        <div className="mt-4">
          <SectionLabel>Tamanho de cada fonte para o modelo de embeddings</SectionLabel>
          <ul className="space-y-1 text-sm">
            {prompt.sources.map((source, index) => (
              <li key={source.chunk_id} className="flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 truncate">
                  <span className="mr-2 font-mono text-xs text-muted">[{index + 1}]</span>
                  {source.breadcrumb || source.title}
                </span>
                <Badge tone={source.truncated ? "warn" : "neutral"} mono>
                  {source.token_count} tokens{source.truncated ? " · passa da janela" : ""}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
      <KpiRow>
        <Kpi value={`≈ ${prompt.approx_input_tokens}`} label="tokens de entrada (estimativa)" />
        <Kpi value={prompt.sources.length} label="fontes no prompt" />
      </KpiRow>
    </div>
  );
}

export function GenerationStage({ trace }: { trace: RagTrace }) {
  const { generation: g } = trace;
  const used = g.daily_limit ? (g.calls_today / g.daily_limit) * 100 : 100;
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        Rastrear não chama o modelo, então não gasta o limite diário. Abaixo está a configuração que o
        chat usaria agora.
      </p>
      <KpiRow>
        <Kpi value={g.model.split("/").pop()} label="modelo principal (OpenRouter)" />
        <Kpi value={g.fallbacks.length} label="modelos de reserva" />
        <Kpi value={formatNumber(g.temperature, 1)} label="temperatura" />
        <Kpi value={g.max_tokens} label="máximo de tokens na resposta" />
      </KpiRow>
      <div className="mt-4">
        <div className="mb-1 flex justify-between text-xs text-muted">
          <span>Chamadas ao modelo hoje (todos os usuários)</span>
          <span className="tabular-nums">
            {g.calls_today} de {g.daily_limit}
          </span>
        </div>
        <Progress value={used} tone={used >= 90 ? "danger" : used >= 60 ? "warn" : "accent"} label="Chamadas hoje" />
        <p className="mt-2 text-xs text-muted">Cada pergunta usa {g.calls_per_turn}.</p>
      </div>
      {g.fallbacks.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-1">
          <span className="mr-1 text-xs text-muted">Reservas, em ordem:</span>
          {g.fallbacks.map((model) => (
            <Chip key={model}>{model}</Chip>
          ))}
        </div>
      )}
    </div>
  );
}

export function CheckStage() {
  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted">
        A resposta só vai ao usuário se passar por duas travas. Se falhar em qualquer uma, o assistente
        diz que não encontrou e oferece abrir um chamado.
      </p>
      <ol className="space-y-2">
        <li className="rounded-lg border border-border p-3">
          <b>1. Citação obrigatória.</b> A resposta precisa citar ao menos um trecho como [1] ou [2].
          Resposta sem fonte é descartada.
        </li>
        <li className="rounded-lg border border-border p-3">
          <b>2. Conferência de fidelidade.</b> Uma segunda chamada pergunta ao modelo se toda afirmação
          está sustentada pelos trechos. Se a resposta for NÃO, é descartada.
        </li>
      </ol>
    </div>
  );
}

export function ChunkAnatomyView({ chunk }: { chunk: RagChunk }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={chunk.visibility === "public" ? "accent" : "warn"} dot>
          {chunk.visibility === "public" ? "público" : "só TI"}
        </Badge>
        <Badge mono>trecho #{chunk.position}</Badge>
        <Badge mono>{chunk.words} palavras</Badge>
      </div>
      <section>
        <SectionLabel>1. Texto do trecho</SectionLabel>
        <p className="mb-1 text-xs text-muted">{chunk.breadcrumb}</p>
        <CodeBox>{chunk.content}</CodeBox>
      </section>
      <section>
        <SectionLabel>2. Tokens do modelo</SectionLabel>
        <TokenChips tokens={chunk.tokens} limit={chunk.model_max_tokens} />
        <WindowUse count={chunk.token_count} limit={chunk.model_max_tokens} />
        {chunk.truncated && (
          <p className="mt-2 text-xs text-warn">
            O que passa da janela não entra no vetor: a busca por significado não enxerga o fim deste
            trecho.
          </p>
        )}
      </section>
      <section>
        <SectionLabel>3. Radicais guardados para a busca por palavras</SectionLabel>
        <div className="flex flex-wrap gap-1">
          {chunk.lexemes.map((item) => (
            <Chip key={item.lexeme} tone="accent" title={`aparece ${item.count}×`}>
              {item.lexeme}
              {item.count > 1 && <span className="ml-1 text-muted">×{item.count}</span>}
            </Chip>
          ))}
        </div>
      </section>
      <section>
        <SectionLabel>4. Vetor guardado</SectionLabel>
        <HeatStrip values={chunk.embedding.values} label="Vetor do trecho" />
        <KpiRow>
          <Kpi value={chunk.embedding.dimensions} label="dimensões" />
          <Kpi value={formatNumber(chunk.embedding.norm, 3)} label="norma" />
        </KpiRow>
      </section>
    </div>
  );
}

export function IngestionStage({
  step,
  overview,
}: {
  step: "doc" | "text" | "chunks" | "embed" | "index";
  overview: RagOverview | undefined;
}) {
  const p = overview?.params;
  const copy = {
    doc: {
      text: "O administrador envia PDF, DOCX ou Markdown. Cada envio vira uma versão, com visibilidade (pública ou só da TI) e registro na auditoria. Documento repetido é reconhecido pelo hash e não duplica.",
      kpis: overview ? [[overview.documents, "documentos ativos"]] : [],
    },
    text: {
      text: "O arquivo vira Markdown, preservando títulos, listas e tabelas. É o título de cada seção que forma o caminho (breadcrumb) usado na citação.",
      kpis: [],
    },
    chunks: {
      text: `O texto é cortado por título, sem partir tabela, bloco de código nem passos numerados, em trechos de até ${p?.chunk_max_words ?? 60} palavras. Trechos curtos cabem inteiros na janela de ${p?.model_max_tokens ?? 128} tokens do modelo.`,
      kpis: overview
        ? [
            [overview.chunks, "trechos"],
            [formatNumber(overview.avg_words, 1), "palavras por trecho (média)"],
            [overview.max_words, "palavras no maior trecho"],
            [overview.restricted_chunks, "trechos só da TI"],
          ]
        : [],
    },
    embed: {
      text: `Cada trecho passa pelo modelo ${p?.embedding_model ?? "de embeddings"}, que roda no próprio servidor, sem custo por uso, e vira um vetor de ${p?.embedding_dimensions ?? 384} números.`,
      kpis: p ? [[p.embedding_dimensions, "dimensões"], [p.model_max_tokens, "tokens lidos por trecho"]] : [],
    },
    index: {
      text: "O trecho é guardado com dois índices: HNSW para achar vizinhos no espaço dos vetores (distância de cosseno) e GIN sobre o texto em português, com radicais, para a busca por palavras.",
      kpis: [],
    },
  }[step];
  return (
    <div>
      <p className="text-sm text-muted">{copy.text}</p>
      {copy.kpis.length > 0 && (
        <KpiRow>
          {copy.kpis.map(([value, label]) => (
            <Kpi key={String(label)} value={value} label={String(label)} />
          ))}
        </KpiRow>
      )}
      {(step === "chunks" || step === "embed") && (
        <p className="mt-3 text-xs text-muted">
          Para ver um trecho de verdade (tokens, radicais e vetor), rastreie uma pergunta e clique num dos
          resultados.
        </p>
      )}
    </div>
  );
}
