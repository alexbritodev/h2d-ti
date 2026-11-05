import { AlertTriangle } from "lucide-react";

import { Badge, type Tone } from "@/components/ui/badge";
import { Progress } from "@/components/ui/primitives";
import type { Priority, TicketStatus } from "@/lib/demo/data";

const PRIORITY_TONES: Record<Priority, Tone> = {
  P1: "danger",
  P2: "warn",
  P3: "info",
  P4: "neutral",
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <Badge tone={PRIORITY_TONES[priority]} mono>
      {priority}
    </Badge>
  );
}

export const STATUS_LABELS: Record<TicketStatus, string> = {
  triagem: "Triagem manual",
  aberto: "Aberto",
  andamento: "Em andamento",
  aguardando: "Aguardando usuário",
  resolvido: "Resolvido",
};

const STATUS_TONES: Record<TicketStatus, Tone> = {
  triagem: "warn",
  aberto: "info",
  andamento: "accent",
  aguardando: "neutral",
  resolvido: "neutral",
};

export function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <Badge tone={STATUS_TONES[status]} dot>
      {STATUS_LABELS[status]}
    </Badge>
  );
}

export function SlaCell({ used, left }: { used: number; left: string }) {
  const tone: Tone = used >= 100 ? "danger" : used >= 75 ? "warn" : "accent";
  return (
    <div className="w-32">
      <div className="mb-1 flex items-center gap-1 text-xs">
        {used >= 75 && <AlertTriangle aria-hidden className="size-3 text-warn" />}
        <span className={used >= 100 ? "font-medium text-danger" : "text-muted"}>{left}</span>
      </div>
      <Progress value={used} tone={tone} label={`Prazo de SLA consumido: ${used}%`} />
    </div>
  );
}
