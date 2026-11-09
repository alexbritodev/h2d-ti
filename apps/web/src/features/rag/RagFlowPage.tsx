import { useMutation, useQuery } from "@tanstack/react-query";
import {
  BadgeCheck,
  Binary,
  Bot,
  ChevronRight,
  Database,
  FileText,
  FileUp,
  Loader2,
  type LucideIcon,
  Merge,
  Scissors,
  Search,
  ShieldCheck,
  Type,
} from "lucide-react";
import { type CSSProperties, type FormEvent, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, Drawer, Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

import { ragChunkQuery, ragOverviewQuery, type RagTrace, traceQuestion } from "./api";
import { formatNumber, Kpi } from "./parts";
import {
  CheckStage,
  ChunkAnatomyView,
  EmbeddingStage,
  FusionStage,
  GenerationStage,
  IngestionStage,
  MaskingStage,
  PromptStage,
  SearchStage,
  TokenizationStage,
} from "./stages";

type StepKey =
  | "doc"
  | "text"
  | "chunks"
  | "embed"
  | "index"
  | "masking"
  | "tokenization"
  | "embedding"
  | "search"
  | "fusion"
  | "prompt"
  | "generation"
  | "check";

interface Step {
  key: StepKey;
  title: string;
  hint: string;
  icon: LucideIcon;
  /** Nome da etapa em `timings`, quando o rastreio mede esse passo. */
  timing?: string;
}

const INGESTION: Step[] = [
  { key: "doc", title: "Documento", hint: "PDF, DOCX, MD", icon: FileUp },
  { key: "text", title: "Texto", hint: "vira Markdown", icon: FileText },
  { key: "chunks", title: "Trechos", hint: "corte por título", icon: Scissors },
  { key: "embed", title: "Embedding", hint: "vetor por trecho", icon: Binary },
  { key: "index", title: "Índices", hint: "HNSW + GIN", icon: Database },
];

const QUERY: Step[] = [
  { key: "masking", title: "Máscara", hint: "dados sensíveis", icon: ShieldCheck, timing: "masking" },
  { key: "tokenization", title: "Tokenização", hint: "modelo e radicais", icon: Type, timing: "tokenization" },
  { key: "embedding", title: "Embedding", hint: "vetor da pergunta", icon: Binary, timing: "embedding" },
  { key: "search", title: "Busca dupla", hint: "vetor e palavras", icon: Search, timing: "search" },
  { key: "fusion", title: "Fusão RRF", hint: "soma das posições", icon: Merge, timing: "fusion" },
  { key: "prompt", title: "Prompt", hint: "regras e fontes", icon: FileText, timing: "prompt" },
  { key: "generation", title: "Modelo", hint: "OpenRouter", icon: Bot },
  { key: "check", title: "Conferência", hint: "citação e fidelidade", icon: BadgeCheck },
];

const ALL_STEPS = [...INGESTION, ...QUERY];

const EXAMPLES = [
  "Como conecto na VPN de casa?",
  "Minha impressora não imprime",
  "Minha senha é Abc12345 e a VPN não conecta",
];

function StepNode({
  step,
  active,
  ms,
  order,
  onSelect,
}: {
  step: Step;
  active: boolean;
  ms: number | undefined;
  order: number;
  onSelect: () => void;
}) {
  const Icon = step.icon;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      style={{ "--delay": `${order * 0.12}s` } as CSSProperties}
      className={cn(
        "flex min-w-[7rem] flex-1 cursor-pointer flex-col items-center gap-0.5 rounded-lg border px-2 py-2.5 text-center transition-colors",
        active ? "border-accent bg-accent-soft" : "border-border bg-surface hover:bg-surface-2",
        ms !== undefined && "chart-fade",
      )}
    >
      <Icon aria-hidden className={cn("size-4", active ? "text-accent" : "text-muted")} />
      <span className="text-sm font-medium">{step.title}</span>
      <span className="text-xs text-muted">{ms !== undefined ? `${formatNumber(ms, 1)} ms` : step.hint}</span>
    </button>
  );
}

function Lane({
  title,
  steps,
  selected,
  trace,
  onSelect,
}: {
  title: string;
  steps: Step[];
  selected: StepKey;
  trace: RagTrace | undefined;
  onSelect: (key: StepKey) => void;
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium tracking-wide text-muted uppercase">{title}</h3>
      <div className="flex flex-wrap items-stretch gap-1">
        {steps.map((step, index) => (
          <div key={step.key} className="flex min-w-[7rem] flex-1 items-stretch gap-1">
            <StepNode
              step={step}
              active={selected === step.key}
              ms={trace?.timings.find((timing) => timing.stage === step.timing)?.ms}
              order={index}
              onSelect={() => onSelect(step.key)}
            />
            {index < steps.length - 1 && (
              <ChevronRight aria-hidden className="hidden size-4 shrink-0 self-center text-muted xl:block" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function TimingCard({ trace }: { trace: RagTrace }) {
  const total = Math.max(...trace.timings.map((timing) => timing.ms), 0.1);
  return (
    <Card>
      <CardHeader
        title="Tempo por etapa"
        description={`Total de ${formatNumber(trace.total_ms, 1)} ms. O modelo de linguagem não entra: não é chamado aqui.`}
      />
      <ul className="space-y-2 p-5">
        {trace.timings.map((timing, index) => (
          <li key={timing.stage} className="grid grid-cols-[9rem_1fr_4.5rem] items-center gap-3 text-sm">
            <span className="truncate text-muted">{timing.label}</span>
            <div className="h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className="chart-bar-h h-full rounded-full bg-accent"
                style={{ width: `${Math.max(2, (timing.ms / total) * 100)}%`, "--delay": `${index * 0.08}s` } as CSSProperties}
              />
            </div>
            <span className="text-right font-mono text-xs tabular-nums">{formatNumber(timing.ms, 1)} ms</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ChunkDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const chunk = useQuery(ragChunkQuery(id));
  return (
    <Drawer
      open={id !== null}
      onOpenChange={(open) => !open && onClose()}
      title={chunk.data?.title ?? "Anatomia do trecho"}
      description="O que a ingestão guardou: texto, tokens, radicais e vetor."
    >
      {chunk.isPending && id !== null ? (
        <div className="space-y-3">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : chunk.isError ? (
        <p role="alert" className="text-danger">
          {chunk.error.message}
        </p>
      ) : chunk.data ? (
        <ChunkAnatomyView chunk={chunk.data} />
      ) : null}
    </Drawer>
  );
}

export function RagFlowPage() {
  const overview = useQuery(ragOverviewQuery);
  const [question, setQuestion] = useState("");
  const [selected, setSelected] = useState<StepKey>("tokenization");
  const [openChunk, setOpenChunk] = useState<string | null>(null);
  const [runs, setRuns] = useState(0);
  const mutation = useMutation({
    mutationFn: traceQuestion,
    onSuccess: () => setRuns((count) => count + 1),
  });
  const trace = mutation.data;

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (text) mutation.mutate(text);
  }

  const step = ALL_STEPS.find((item) => item.key === selected) ?? ALL_STEPS[0];
  const timing = trace?.timings.find((item) => item.stage === step?.timing);
  const ingestionKey = INGESTION.find((item) => item.key === selected)?.key;

  function renderDetail() {
    if (ingestionKey) {
      return <IngestionStage step={ingestionKey as "doc" | "text" | "chunks" | "embed" | "index"} overview={overview.data} />;
    }
    if (selected === "check") return <CheckStage />;
    if (!trace) {
      return (
        <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted">
          Faça uma pergunta de teste acima para ver esta etapa com dados reais.
        </p>
      );
    }
    switch (selected) {
      case "masking":
        return <MaskingStage trace={trace} />;
      case "tokenization":
        return <TokenizationStage trace={trace} />;
      case "embedding":
        return <EmbeddingStage trace={trace} />;
      case "search":
        return <SearchStage trace={trace} onOpen={setOpenChunk} />;
      case "fusion":
        return <FusionStage trace={trace} onOpen={setOpenChunk} />;
      case "prompt":
        return <PromptStage trace={trace} />;
      case "generation":
        return <GenerationStage trace={trace} />;
      default:
        return null;
    }
  }

  const data = overview.data;
  return (
    <section className="space-y-6">
      <PageHeader
        title="Fluxo do RAG"
        description="Como o assistente transforma documentos em respostas, etapa por etapa, com dados reais."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {data ? (
          <>
            <Kpi value={data.documents} label="documentos ativos" />
            <Kpi value={data.chunks} label="trechos indexados" />
            <Kpi value={formatNumber(data.avg_words, 1)} label="palavras por trecho (média)" />
            <Kpi value={data.params.embedding_dimensions} label="dimensões do vetor" />
            <Kpi value={`${data.params.calls_today} / ${data.params.daily_limit}`} label="chamadas ao modelo hoje" />
          </>
        ) : (
          Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="h-[58px]" />)
        )}
      </div>

      <Card>
        <CardHeader
          title="Pergunta de teste"
          description="Roda só a busca, sem chamar o modelo de linguagem: não gasta o limite diário nem grava nada."
        />
        <form onSubmit={submit} className="space-y-3 p-5">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Como conecto na VPN de casa?"
              aria-label="Pergunta de teste"
              maxLength={500}
            />
            <Button type="submit" variant="primary" disabled={mutation.isPending || !question.trim()}>
              {mutation.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}
              Rastrear
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted">Exemplos:</span>
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setQuestion(example)}
                className="cursor-pointer rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-text"
              >
                {example}
              </button>
            ))}
          </div>
          {mutation.isError && (
            <p role="alert" className="text-sm text-danger">
              {mutation.error.message}
            </p>
          )}
        </form>
      </Card>

      <Card>
        <CardHeader
          title="Pipeline"
          description="Clique em uma etapa para ver o que acontece nela."
          action={trace && <Badge tone="accent" dot>{`rastreio de ${formatNumber(trace.total_ms, 1)} ms`}</Badge>}
        />
        <div className="space-y-5 p-5" key={runs}>
          <Lane title="Ingestão · quando um documento é enviado" steps={INGESTION} selected={selected} trace={undefined} onSelect={setSelected} />
          <Lane title="Consulta · a cada pergunta no chat" steps={QUERY} selected={selected} trace={trace} onSelect={setSelected} />
        </div>
      </Card>

      <Card>
        <CardHeader
          title={step?.title ?? ""}
          description={ingestionKey ? "Ingestão" : "Consulta"}
          action={timing && <Badge mono>{formatNumber(timing.ms, 1)} ms</Badge>}
        />
        <div className="p-5" aria-live="polite">
          {renderDetail()}
        </div>
      </Card>

      {trace && <TimingCard trace={trace} />}

      <ChunkDrawer id={openChunk} onClose={() => setOpenChunk(null)} />
    </section>
  );
}
