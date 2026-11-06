import { AlertTriangle } from "lucide-react";

import { Badge, type Tone } from "@/components/ui/badge";

import type { Priority, Ticket, TicketStatus } from "./api";

const PRIORITY_TONES: Record<Priority, Tone> = { P1: "danger", P2: "warn", P3: "info", P4: "neutral" };

export function PriorityBadge({ priority }: { priority: Priority | null | undefined }) {
  if (!priority) return <Badge tone="neutral">Sem prioridade</Badge>;
  return (
    <Badge tone={PRIORITY_TONES[priority]} mono>
      {priority}
    </Badge>
  );
}

export const STATUS_LABELS: Record<TicketStatus, string> = {
  new: "Novo",
  triage: "Triagem manual",
  assigned: "Atribuído",
  in_progress: "Em andamento",
  waiting_user: "Aguardando usuário",
  resolved: "Resolvido",
};

const STATUS_TONES: Record<TicketStatus, Tone> = {
  new: "info",
  triage: "warn",
  assigned: "info",
  in_progress: "accent",
  waiting_user: "neutral",
  resolved: "neutral",
};

export function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <Badge tone={STATUS_TONES[status]} dot>
      {STATUS_LABELS[status]}
    </Badge>
  );
}

const SLA: Record<string, { label: string; tone: Tone }> = {
  ok: { label: "No prazo", tone: "accent" },
  at_risk: { label: "Em risco", tone: "warn" },
  breached: { label: "Estourado", tone: "danger" },
  met: { label: "Cumprido", tone: "neutral" },
};

export const formatDate = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";

export function SlaBadge({ sla }: { sla: Ticket["sla"] }) {
  const view = SLA[sla.state] ?? SLA.ok!;
  return (
    <div className="flex flex-col gap-0.5">
      <Badge tone={view.tone}>
        {(sla.state === "at_risk" || sla.state === "breached") && (
          <AlertTriangle aria-hidden className="size-3" />
        )}
        {view.label}
      </Badge>
      {sla.resolution_due && (
        <span className="text-[11px] text-muted">até {formatDate(sla.resolution_due)}</span>
      )}
    </div>
  );
}
