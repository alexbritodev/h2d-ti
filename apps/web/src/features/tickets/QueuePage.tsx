import { Download, Search, UserRoundPlus, X } from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { PriorityBadge, SlaCell, StatusBadge } from "@/components/tickets";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Avatar, Card, Select, Tabs } from "@/components/ui/primitives";
import { demoToast } from "@/components/ui/toast";
import { type Ticket, TICKETS } from "@/lib/demo/data";

import { TicketDrawer } from "./TicketDrawer";

const PRIORITY_ORDER = { P1: 1, P2: 2, P3: 3, P4: 4 };

const COLUMNS: Column<Ticket>[] = [
  {
    key: "code",
    header: "Código",
    sortValue: (ticket) => ticket.code,
    render: (ticket) => <span className="font-mono text-xs">{ticket.code}</span>,
  },
  {
    key: "subject",
    header: "Assunto",
    sortValue: (ticket) => ticket.subject,
    render: (ticket) => (
      <div className="max-w-xs min-w-48">
        <p className="truncate font-medium">{ticket.subject}</p>
        <p className="truncate text-xs text-muted">
          {ticket.category} · {ticket.requester} · {ticket.updatedAt}
        </p>
      </div>
    ),
  },
  {
    key: "priority",
    header: "Prioridade",
    sortValue: (ticket) => PRIORITY_ORDER[ticket.priority],
    render: (ticket) => <PriorityBadge priority={ticket.priority} />,
  },
  {
    key: "status",
    header: "Status",
    sortValue: (ticket) => ticket.status,
    render: (ticket) => <StatusBadge status={ticket.status} />,
  },
  {
    key: "sla",
    header: "SLA",
    sortValue: (ticket) => ticket.slaUsed,
    render: (ticket) => <SlaCell used={ticket.slaUsed} left={ticket.slaLeft} />,
  },
  {
    key: "assignee",
    header: "Responsável",
    sortValue: (ticket) => ticket.assignee ?? "",
    render: (ticket) =>
      ticket.assignee ? (
        <span className="flex items-center gap-2 whitespace-nowrap">
          <Avatar name={ticket.assignee} className="size-6 text-[10px]" />
          {ticket.assignee}
        </span>
      ) : (
        <span className="text-muted">Sem responsável</span>
      ),
  },
];

const VIEWS: Record<string, { label: string; match: (ticket: Ticket) => boolean }> = {
  open: { label: "Em aberto", match: (t) => t.status !== "resolvido" },
  risk: { label: "SLA em risco", match: (t) => t.slaUsed >= 75 && t.status !== "resolvido" },
  triage: { label: "Triagem manual", match: (t) => t.status === "triagem" },
  resolved: { label: "Resolvidos", match: (t) => t.status === "resolvido" },
};

export function QueuePage() {
  const [view, setView] = useState("open");
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [opened, setOpened] = useState<Ticket | null>(null);

  const categories = useMemo(() => [...new Set(TICKETS.map((t) => t.category))].sort(), []);
  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return TICKETS.filter(
      (ticket) =>
        VIEWS[view]!.match(ticket) &&
        (!priority || ticket.priority === priority) &&
        (!category || ticket.category === category) &&
        (!term || `${ticket.code} ${ticket.subject} ${ticket.requester}`.toLowerCase().includes(term)),
    );
  }, [view, search, priority, category]);
  const hasFilters = Boolean(search || priority || category);

  return (
    <section>
      <PageHeader
        title="Fila de chamados"
        description="Chamados classificados e atribuídos, por prioridade e prazo de SLA."
        actions={
          <Button
            className="border border-border bg-surface"
            onClick={() => demoToast("Exportação simulada")}
          >
            <Download aria-hidden className="size-4" />
            Exportar
          </Button>
        }
      />

      <Card className="overflow-hidden">
        <div className="px-4 pt-2">
          <Tabs
            label="Visões da fila"
            value={view}
            onValueChange={setView}
            tabs={Object.entries(VIEWS).map(([value, { label, match }]) => ({
              value,
              label,
              count: TICKETS.filter(match).length,
            }))}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 p-4">
          <div className="relative min-w-52 flex-1">
            <Search
              aria-hidden
              className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
            />
            <Input
              aria-label="Buscar por código, assunto ou solicitante"
              placeholder="Buscar por código, assunto ou solicitante"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="pl-9"
            />
          </div>
          <Select
            aria-label="Filtrar por prioridade"
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
            className="w-40"
          >
            <option value="">Toda prioridade</option>
            {Object.keys(PRIORITY_ORDER).map((value) => (
              <option key={value}>{value}</option>
            ))}
          </Select>
          <Select
            aria-label="Filtrar por categoria"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="w-52"
          >
            <option value="">Toda categoria</option>
            {categories.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </Select>
          {hasFilters && (
            <Button
              onClick={() => {
                setSearch("");
                setPriority("");
                setCategory("");
              }}
            >
              <X aria-hidden className="size-4" />
              Limpar
            </Button>
          )}
        </div>

        {selected.size > 0 && (
          <div className="flex flex-wrap items-center gap-3 border-t border-border bg-accent-soft px-4 py-2">
            <span className="font-medium">
              {selected.size} {selected.size === 1 ? "selecionado" : "selecionados"}
            </span>
            <Button
              className="h-8 border border-border bg-surface"
              onClick={() => {
                demoToast(`${selected.size} chamados reatribuídos`);
                setSelected(new Set());
              }}
            >
              <UserRoundPlus aria-hidden className="size-4" />
              Atribuir
            </Button>
            <Button className="h-8" onClick={() => setSelected(new Set())}>
              Cancelar
            </Button>
          </div>
        )}

        <DataTable
          label="Fila de chamados"
          columns={COLUMNS}
          rows={rows}
          rowKey={(ticket) => ticket.code}
          onRowClick={setOpened}
          selected={selected}
          onSelectedChange={setSelected}
          pageSize={6}
        />
      </Card>

      <TicketDrawer ticket={opened} onClose={() => setOpened(null)} />
    </section>
  );
}
