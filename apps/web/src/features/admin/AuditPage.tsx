import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Avatar, Card, Drawer } from "@/components/ui/primitives";
import { Snippet } from "@/components/ui/snippet";

import { type AuditEntry, auditQuery } from "./api";

const ACTION_LABELS: Record<string, string> = {
  "user.create": "Criou usuário",
  "user.invite": "Convidou usuário",
  "user.invite_resend": "Reenviou convite",
  "user.update": "Alterou usuário",
  "user.delete": "Excluiu usuário",
  "user.password_reset": "Redefiniu senha",
  "user.password_set": "Definiu a senha pelo convite",
  "kb.upload": "Enviou documento",
  "kb.update": "Alterou documento",
  "settings.update": "Alterou ajuste",
};

const ENTITY_LABELS: Record<string, string> = {
  user: "Usuário",
  kb_document: "Documento",
  setting: "Ajuste",
};

const actionLabel = (entry: AuditEntry) => ACTION_LABELS[entry.action] ?? entry.action;
const actorLabel = (entry: AuditEntry) => entry.actor_name ?? "Sistema";
const entityLabel = (entry: AuditEntry) => {
  const kind = ENTITY_LABELS[entry.entity_type] ?? entry.entity_type;
  const name = entry.entity_label ?? entry.entity_id;
  return name ? `${kind}: ${name}` : kind;
};
const when = (entry: AuditEntry) =>
  new Date(entry.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

const COLUMNS: Column<AuditEntry>[] = [
  {
    key: "time",
    header: "Quando",
    sortValue: (entry) => entry.created_at,
    render: (entry) => <span className="font-mono text-xs whitespace-nowrap">{when(entry)}</span>,
  },
  {
    key: "actor",
    header: "Quem",
    sortValue: actorLabel,
    render: (entry) => (
      <span className="flex items-center gap-2 whitespace-nowrap">
        <Avatar name={actorLabel(entry)} className="size-6 text-[10px]" />
        {actorLabel(entry)}
      </span>
    ),
  },
  { key: "action", header: "Ação", sortValue: actionLabel, render: (entry) => <Badge>{actionLabel(entry)}</Badge> },
  { key: "entity", header: "O quê", sortValue: entityLabel, render: entityLabel },
];

export function AuditPage() {
  const audit = useQuery(auditQuery);
  const [search, setSearch] = useState("");
  const [opened, setOpened] = useState<AuditEntry | null>(null);
  const term = search.trim().toLowerCase();
  const rows = (audit.data ?? []).filter(
    (entry) =>
      !term || `${actorLabel(entry)} ${actionLabel(entry)} ${entityLabel(entry)}`.toLowerCase().includes(term),
  );

  return (
    <section>
      <PageHeader title="Auditoria" description="Quem alterou o quê, e como era antes." />
      <Card className="overflow-hidden">
        <div className="relative p-4">
          <Search aria-hidden className="absolute top-1/2 left-7 size-4 -translate-y-1/2 text-muted" />
          <Input
            aria-label="Buscar no registro"
            placeholder="Buscar por pessoa, ação ou item"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="pl-9"
          />
        </div>
        {audit.isError ? (
          <p role="alert" className="p-5 text-danger">
            Não foi possível carregar a auditoria.
          </p>
        ) : (
          <DataTable
            label="Registro de alterações"
            columns={COLUMNS}
            rows={rows}
            rowKey={(entry) => entry.id}
            onRowClick={setOpened}
            empty="Nenhuma alteração registrada."
          />
        )}
      </Card>

      <Drawer
        open={opened !== null}
        onOpenChange={(open) => !open && setOpened(null)}
        title={opened ? entityLabel(opened) : ""}
        description={opened ? `${actionLabel(opened)} por ${actorLabel(opened)} em ${when(opened)}` : undefined}
      >
        {opened && (
          <div className="space-y-4">
            <div>
              <h3 className="mb-2 font-semibold">Antes</h3>
              <Snippet language="json" code={JSON.stringify(opened.before ?? {}, null, 2)} />
            </div>
            <div>
              <h3 className="mb-2 font-semibold">Depois</h3>
              <Snippet language="json" code={JSON.stringify(opened.after ?? {}, null, 2)} />
            </div>
          </div>
        )}
      </Drawer>
    </section>
  );
}
