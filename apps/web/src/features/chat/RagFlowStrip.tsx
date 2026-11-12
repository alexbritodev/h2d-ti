import { Card } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

import type { ChatAction, FlowStatus, FlowStep } from "./api";

const STAGES = [
  { id: "masking", label: "Mascarar" },
  { id: "triage", label: "Triagem" },
  { id: "rewrite", label: "Reescrever" },
  { id: "search", label: "Busca nos manuais" },
  { id: "expand", label: "Busca ampliada" },
  { id: "model", label: "Modelo" },
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

/**
 * Fluxo do RAG da última pergunta, numa linha só e compacto, para não empurrar a página.
 * Só o administrador vê (a API só envia os dados a ele).
 */
export function RagFlowStrip({ steps, action }: { steps: FlowStep[] | null; action?: ChatAction }) {
  const byId = new Map((steps ?? []).map((step) => [step.id, step]));
  return (
    <Card className="px-3 py-2">
      <p className="mb-1.5 text-[11px] text-muted">
        <span className="font-medium text-text">Fluxo do RAG</span>{" "}
        {steps
          ? "· última pergunta (só o administrador vê)"
          : "· aparece depois da primeira pergunta (só o administrador vê)"}
      </p>
      <ol aria-label="Etapas do RAG" className="grid grid-cols-4 gap-x-1.5 gap-y-2 sm:grid-cols-8">
        {STAGES.map((stage) => {
          const step = byId.get(stage.id);
          const status: FlowStatus = step?.status ?? "skip";
          const detail = stage.id === "outcome" && action ? OUTCOME[action] : step?.detail;
          return (
            <li key={stage.id} className="min-w-0" data-status={status} title={detail || undefined}>
              <span aria-hidden className={cn("block h-[3px] rounded-full", DOT[status])} />
              <span className={cn("mt-1 block truncate text-[10px] leading-tight", step ? "font-medium" : "text-muted")}>
                {stage.label}
              </span>
              <span className="sr-only">
                {STATUS_TEXT[status]}
                {detail ? `: ${detail}` : ""}
              </span>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
