import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Card, Select } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

import { type Priority, type Ticket, type TicketFilters, ticketsQuery } from "./api";
import { formatDate, PriorityBadge, SlaBadge, StatusBadge } from "./badges";
import { TicketDrawer } from "./TicketDrawer";

type View = "all" | "mine" | "triage" | "open";

const VIEWS: { value: View; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "open", label: "Em aberto" },
  { value: "mine", label: "Minha fila" },
  { value: "triage", label: "Triagem manual" },
];

const PRIORITY_RANK: Record<string, number> = { P1: 1, P2: 2, P3: 3, P4: 4 };

const COLUMNS: Column<Ticket>[] = [
  {
    key: "code",
    header: "Código",
    sortValue: (ticket) => ticket.code,
    render: (ticket) => <span className="font-mono text-xs">{ticket.code}</span>,
  },
  {
    key: "summary",
    header: "Assunto",
    sortValue: (ticket) => ticket.summary,
    render: (ticket) => (
      <div className="max-w-xs min-w-48">
        <p className="truncate font-medium">{ticket.summary}</p>
        <p className="truncate text-xs text-muted">
          {ticket.requester_name}
          {ticket.is_vip ? " · VIP" : ""}
        </p>
      </div>
    ),
  },
  {
    key: "priority",
    header: "Prioridade",
    sortValue: (ticket) => PRIORITY_RANK[ticket.priority ?? ""] ?? 5,
    render: (ticket) => <PriorityBadge priority={ticket.priority} />,
  },
  {
    key: "status",
    header: "Status",
    sortValue: (ticket) => ticket.status,
    render: (ticket) => <StatusBadge status={ticket.status} />,
  },
  { key: "sla", header: "Prazo", render: (ticket) => <SlaBadge sla={ticket.sla} /> },
  {
    key: "assignee",
    header: "Responsável",
    sortValue: (ticket) => ticket.technician_name ?? "",
    render: (ticket) => ticket.technician_name ?? <span className="text-muted">—</span>,
  },
  {
    key: "updated",
    header: "Atualizado",
    sortValue: (ticket) => ticket.updated_at,
    render: (ticket) => <span className="whitespace-nowrap text-muted">{formatDate(ticket.updated_at)}</span>,
  },
];

export function QueuePage() {
  const [view, setView] = useState<View>("all");
  const [priority, setPriority] = useState<Priority | "">("");
  const [openedId, setOpenedId] = useState<string | null>(null);

  const filters: TicketFilters = {
    ...(view === "mine" ? { mine: true } : {}),
    ...(view === "triage" ? { triage: true } : {}),
    ...(priority ? { priority } : {}),
  };
  const tickets = useQuery({ ...ticketsQuery(filters), refetchInterval: 15_000 });
  const all = tickets.data ?? [];
  const rows = view === "open" ? all.filter((t) => t.status !== "resolved") : all;
  const triageCount = useQuery(ticketsQuery({ triage: true })).data?.length ?? 0;

  return (
    <section className="space-y-4">
      <PageHeader title="Fila de chamados" description="Chamados da equipe, do mais urgente ao mais antigo." />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Filtrar a fila" className="flex flex-wrap gap-2">
          {VIEWS.map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={view === item.value}
              onClick={() => setView(item.value)}
              className={cn(
                "h-9 cursor-pointer rounded-full border px-3 text-sm transition-colors sm:h-8",
                view === item.value
                  ? "border-accent bg-accent-soft font-medium"
                  : "border-border bg-surface text-muted hover:text-text",
              )}
            >
              {item.label}
              {item.value === "triage" && triageCount > 0 && (
                <span className="ml-1.5 rounded-full bg-warn/15 px-1.5 text-xs text-warn">{triageCount}</span>
              )}
            </button>
          ))}
        </div>
        <div className="w-full sm:w-44">
          <Select
            aria-label="Filtrar por prioridade"
            value={priority}
            onChange={(event) => setPriority(event.target.value as Priority | "")}
          >
            <option value="">Todas as prioridades</option>
            {(["P1", "P2", "P3", "P4"] as const).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <Card className="overflow-hidden">
        {tickets.isError ? (
          <p role="alert" className="p-5 text-danger">
            Não foi possível carregar a fila.
          </p>
        ) : (
          <DataTable
            label="Fila de chamados"
            columns={COLUMNS}
            rows={rows}
            rowKey={(ticket) => ticket.id}
            onRowClick={(ticket) => setOpenedId(ticket.id)}
            pageSize={10}
            empty={view === "triage" ? "Nenhum chamado esperando triagem manual." : "Nenhum chamado por aqui."}
          />
        )}
      </Card>

      <TicketDrawer ticketId={openedId} onClose={() => setOpenedId(null)} />
    </section>
  );
}
