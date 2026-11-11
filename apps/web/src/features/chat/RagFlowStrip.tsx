import { ChevronRight } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

import type { ChatAction, FlowStatus, FlowStep } from "./api";

const STAGES = [
  { id: "masking", label: "Mascarar" },
  { id: "triage", label: "Triagem" },
  { id: "rewrite", label: "Reescrever" },
  { id: "search", label: "Buscar nos manuais" },
  { id: "model", label: "Modelo responde" },
  { id: "fidelity", label: "Conferir" },
  { id: "outcome", label: "Desfecho" },
] as const;

const OUTCOME: Record<ChatAction, string> = {
  answered: "Respondeu com fonte",
  smalltalk: "Conversa",
  clarify: "Pediu detalhes",
  not_found: "Não achou: oferece chamado",
  escalate: "Encaminhou à TI",
  unavailable: "Modelo indisponível",
  limit: "Teto diário atingido",
};

const DOT: Record<FlowStatus, string> = {
  ok: "bg-accent",
  warn: "bg-warn",
  fail: "bg-danger",
  skip: "bg-muted/40",
};

const STATUS_TEXT: Record<FlowStatus, string> = {
  ok: "ok",
  warn: "atenção",
  fail: "falhou",
  skip: "não rodou",
};

/** Fluxo do RAG da última pergunta, etapa por etapa. Só o administrador vê (a API só envia a ele). */
export function RagFlowStrip({ steps, action }: { steps: FlowStep[] | null; action?: ChatAction }) {
  const byId = new Map((steps ?? []).map((step) => [step.id, step]));
  return (
    <Card>
      <CardHeader
        title="Fluxo do RAG"
        description={
          steps
            ? "O que aconteceu na última pergunta, etapa por etapa (visível só ao administrador)"
            : "Aparece depois da primeira pergunta (visível só ao administrador)"
        }
      />
      <ol aria-label="Etapas do RAG" className="flex flex-wrap items-stretch gap-y-2 p-4">
        {STAGES.map((stage, index) => {
          const step = byId.get(stage.id);
          const status: FlowStatus = step?.status ?? "skip";
          const detail = stage.id === "outcome" && action ? OUTCOME[action] : step?.detail;
          return (
            <li key={stage.id} className="flex items-stretch" data-status={status}>
              <div
                title={step?.detail || undefined}
                className={cn(
                  "flex w-[132px] flex-col gap-1 rounded-lg border border-border bg-surface-2 px-2.5 py-2",
                  !step && "opacity-60",
                )}
              >
                <span className="flex items-center gap-1.5 text-xs font-medium">
                  <span aria-hidden className={cn("size-2 shrink-0 rounded-full", DOT[status])} />
                  {stage.label}
                </span>
                <span className="sr-only">{STATUS_TEXT[status]}</span>
                <span className="line-clamp-3 text-[11px] leading-snug text-muted">
                  {detail || (step ? "" : "—")}
                </span>
              </div>
              {index < STAGES.length - 1 && (
                <ChevronRight aria-hidden className="mx-0.5 size-4 shrink-0 self-center text-muted" />
              )}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
