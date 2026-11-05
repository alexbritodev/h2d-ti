import { Plus } from "lucide-react";
import { type FormEvent, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { PriorityBadge, StatusBadge } from "@/components/tickets";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Card, Field, Modal, Select } from "@/components/ui/primitives";
import { demoToast } from "@/components/ui/toast";
import { CATEGORIES, type Ticket, TICKETS } from "@/lib/demo/data";

import { TicketDrawer } from "./TicketDrawer";

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
    render: (ticket) => <span className="font-medium">{ticket.subject}</span>,
  },
  { key: "category", header: "Categoria", render: (ticket) => ticket.category },
  { key: "priority", header: "Prioridade", render: (t) => <PriorityBadge priority={t.priority} /> },
  { key: "status", header: "Status", render: (t) => <StatusBadge status={t.status} /> },
  {
    key: "updated",
    header: "Atualizado",
    render: (ticket) => <span className="whitespace-nowrap text-muted">{ticket.updatedAt}</span>,
  },
];

const MY_TICKETS = TICKETS.filter((ticket) => ticket.requester === "Fátima Financeiro");

export function MyTicketsPage() {
  const [creating, setCreating] = useState(false);
  const [opened, setOpened] = useState<Ticket | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    setCreating(false);
    demoToast("Chamado aberto");
  }

  return (
    <section>
      <PageHeader
        title="Meus chamados"
        description="Acompanhe o andamento dos chamados que você abriu."
        actions={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus aria-hidden className="size-4" />
            Novo chamado
          </Button>
        }
      />

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        {[
          ["Em aberto", MY_TICKETS.filter((t) => t.status !== "resolvido").length],
          ["Aguardando você", MY_TICKETS.filter((t) => t.status === "aguardando").length],
          ["Resolvidos", MY_TICKETS.filter((t) => t.status === "resolvido").length],
        ].map(([label, value]) => (
          <Card key={label} className="p-5">
            <p className="text-sm text-muted">{label}</p>
            <p className="mt-1 text-3xl font-semibold tracking-tight">{value}</p>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <DataTable
          label="Meus chamados"
          columns={COLUMNS}
          rows={MY_TICKETS}
          rowKey={(ticket) => ticket.code}
          onRowClick={setOpened}
          empty="Você ainda não tem chamados."
        />
      </Card>

      <TicketDrawer ticket={opened} onClose={() => setOpened(null)} readOnly />

      <Modal
        open={creating}
        onOpenChange={setCreating}
        title="Novo chamado"
        description="Conte o que aconteceu. Quanto mais detalhes, mais rápida a solução."
        footer={
          <>
            <Button onClick={() => setCreating(false)}>Cancelar</Button>
            <Button variant="primary" type="submit" form="new-ticket">
              Abrir chamado
            </Button>
          </>
        }
      >
        <form id="new-ticket" onSubmit={submit} className="space-y-4">
          <Field label="Assunto" htmlFor="ticket-subject">
            <Input id="ticket-subject" required placeholder="Ex.: VPN não conecta" />
          </Field>
          <Field label="Categoria" htmlFor="ticket-category">
            <Select id="ticket-category" required defaultValue="">
              <option value="" disabled>
                Selecione
              </option>
              {CATEGORIES.map((category) => (
                <option key={category.name}>{category.name}</option>
              ))}
            </Select>
          </Field>
          <Field
            label="Descrição"
            htmlFor="ticket-description"
            hint="Nunca informe sua senha. A TI não precisa dela."
          >
            <textarea
              id="ticket-description"
              required
              rows={4}
              placeholder="Sistema afetado, mensagem de erro, desde quando..."
              className="w-full rounded-lg border border-border bg-surface p-3 placeholder:text-muted"
            />
          </Field>
        </form>
      </Modal>
    </section>
  );
}
