import { Search } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Avatar, Card, Drawer } from "@/components/ui/primitives";
import { Snippet } from "@/components/ui/snippet";
import { AUDIT_LOG } from "@/lib/demo/data";

type Entry = (typeof AUDIT_LOG)[number];

const COLUMNS: Column<Entry>[] = [
  {
    key: "time",
    header: "Quando",
    render: (entry) => <span className="font-mono text-xs whitespace-nowrap">{entry.time}</span>,
  },
  {
    key: "actor",
    header: "Quem",
    sortValue: (entry) => entry.actor,
    render: (entry) => (
      <span className="flex items-center gap-2 whitespace-nowrap">
        <Avatar name={entry.actor} className="size-6 text-[10px]" />
        {entry.actor}
      </span>
    ),
  },
  { key: "action", header: "Ação", sortValue: (entry) => entry.action, render: (entry) => <Badge>{entry.action}</Badge> },
  { key: "entity", header: "O quê", sortValue: (entry) => entry.entity, render: (entry) => entry.entity },
];

export function AuditPage() {
  const [search, setSearch] = useState("");
  const [opened, setOpened] = useState<Entry | null>(null);
  const term = search.trim().toLowerCase();
  const rows = AUDIT_LOG.filter(
    (entry) => !term || `${entry.actor} ${entry.action} ${entry.entity}`.toLowerCase().includes(term),
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
        <DataTable
          label="Registro de alterações"
          columns={COLUMNS}
          rows={rows}
          rowKey={(entry) => entry.id}
          onRowClick={setOpened}
        />
      </Card>

      <Drawer
        open={opened !== null}
        onOpenChange={(open) => !open && setOpened(null)}
        title={opened?.entity ?? ""}
        description={opened ? `${opened.action} por ${opened.actor} em ${opened.time}` : undefined}
      >
        {opened && (
          <div className="space-y-4">
            <div>
              <h3 className="mb-2 font-semibold">Antes</h3>
              <Snippet language="json" code={JSON.stringify(opened.before, null, 2)} />
            </div>
            <div>
              <h3 className="mb-2 font-semibold">Depois</h3>
              <Snippet language="json" code={JSON.stringify(opened.after, null, 2)} />
            </div>
          </div>
        )}
      </Drawer>
    </section>
  );
}
