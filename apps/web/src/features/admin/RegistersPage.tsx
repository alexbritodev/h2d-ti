import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Plus, XCircle } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Avatar, Card, Progress, Tabs } from "@/components/ui/primitives";
import { type Technician, techniciansQuery } from "@/features/tickets/api";
import { PriorityBadge } from "@/features/tickets/badges";

import { type CategoryRow, type SlaRow, categoriesQuery, formatMinutes, slaQuery } from "./api";
import { UsersTab } from "./UsersTab";

function ActiveBadge({ active, on, off }: { active: boolean; on: string; off: string }) {
  const Icon = active ? CheckCircle2 : XCircle;
  return (
    <Badge tone={active ? "accent" : "neutral"}>
      <Icon aria-hidden className="size-3" />
      {active ? on : off}
    </Badge>
  );
}

const TECHNICIAN_COLUMNS: Column<Technician>[] = [
  {
    key: "name",
    header: "Técnico",
    sortValue: (technician) => technician.name,
    render: (technician) => (
      <div className="flex items-center gap-3 whitespace-nowrap">
        <Avatar name={technician.name} />
        <span className="font-medium">{technician.name}</span>
      </div>
    ),
  },
  {
    key: "skills",
    header: "Habilidades",
    render: (technician) => (
      <div className="flex flex-wrap gap-1">
        {technician.skills.map((skill) => (
          <Badge key={skill} tone="info" mono>
            {skill}
          </Badge>
        ))}
      </div>
    ),
  },
  {
    key: "load",
    header: "Carga",
    sortValue: (technician) => technician.open_tickets,
    render: (technician) => (
      <div className="w-28">
        <p className="mb-1 text-xs text-muted">
          {technician.open_tickets} de {technician.max_capacity}
        </p>
        <Progress
          value={Math.min(100, (technician.open_tickets / technician.max_capacity) * 100)}
          tone={technician.open_tickets / technician.max_capacity >= 0.9 ? "warn" : "accent"}
          label={`Carga de ${technician.name}`}
        />
      </div>
    ),
  },
  {
    key: "available",
    header: "Situação",
    render: (technician) => (
      <ActiveBadge active={technician.is_available} on="Disponível" off="Ausente" />
    ),
  },
];

const CATEGORY_COLUMNS: Column<CategoryRow>[] = [
  {
    key: "name",
    header: "Categoria",
    sortValue: (c) => (c.parent_name ? `${c.parent_name} ${c.name}` : c.name),
    render: (c) => (
      <span className={c.parent_name ? "pl-4 text-muted" : "font-medium"}>{c.name}</span>
    ),
  },
  { key: "children", header: "Subcategorias", sortValue: (c) => c.children, render: (c) => c.children },
  {
    key: "skill",
    header: "Habilidade padrão",
    render: (c) =>
      c.skill ? (
        <Badge tone="info" mono>
          {c.skill}
        </Badge>
      ) : (
        "—"
      ),
  },
  { key: "sla", header: "Política de SLA", render: (c) => c.sla_policy ?? "—" },
  { key: "active", header: "Situação", render: (c) => <ActiveBadge active={c.is_active} on="Ativa" off="Inativa" /> },
];

const SLA_COLUMNS: Column<SlaRow>[] = [
  { key: "policy", header: "Política", render: (s) => s.policy },
  { key: "priority", header: "Prioridade", render: (s) => <PriorityBadge priority={s.priority} /> },
  { key: "first", header: "1ª resposta", render: (s) => formatMinutes(s.first_response_minutes) },
  { key: "resolution", header: "Resolução", render: (s) => formatMinutes(s.resolution_minutes) },
];

function Table<T>({
  query,
  label,
  columns,
  rowKey,
}: {
  query: { isError: boolean; data: T[] | undefined };
  label: string;
  columns: Column<T>[];
  rowKey: (row: T) => string;
}) {
  if (query.isError) {
    return (
      <p role="alert" className="py-5 text-danger">
        Não foi possível carregar: {label.toLowerCase()}.
      </p>
    );
  }
  return (
    <div className="-mx-4">
      <DataTable label={label} columns={columns} rows={query.data ?? []} rowKey={rowKey} />
    </div>
  );
}

export function RegistersPage() {
  const [tab, setTab] = useState("users");
  const [creating, setCreating] = useState(false);
  const technicians = useQuery(techniciansQuery);
  const categories = useQuery(categoriesQuery);
  const sla = useQuery(slaQuery);

  return (
    <section>
      <PageHeader
        title="Cadastros"
        description="Usuários, técnicos, categorias e prazos de atendimento."
        actions={
          // Só usuários são cadastrados por aqui; técnicos, categorias e prazos são lidos do banco.
          tab === "users" ? (
            <Button variant="primary" onClick={() => setCreating(true)}>
              <Plus aria-hidden className="size-4" />
              Novo: usuário
            </Button>
          ) : undefined
        }
      />

      <Card className="overflow-hidden p-4 pb-0">
        <Tabs
          label="Tipos de cadastro"
          value={tab}
          onValueChange={setTab}
          tabs={[
            {
              value: "users",
              label: "Usuários",
              content: <UsersTab creating={creating && tab === "users"} onCreatingChange={setCreating} />,
            },
            {
              value: "technicians",
              label: "Técnicos",
              count: technicians.data?.length,
              content: (
                <Table query={technicians} label="Técnicos" columns={TECHNICIAN_COLUMNS} rowKey={(t) => t.id} />
              ),
            },
            {
              value: "categories",
              label: "Categorias",
              count: categories.data?.length,
              content: (
                <Table query={categories} label="Categorias" columns={CATEGORY_COLUMNS} rowKey={(c) => c.id} />
              ),
            },
            {
              value: "sla",
              label: "SLAs",
              count: sla.data?.length,
              content: (
                <Table
                  query={sla}
                  label="Prazos de SLA"
                  columns={SLA_COLUMNS}
                  rowKey={(s) => `${s.policy}-${s.priority}`}
                />
              ),
            },
          ]}
        />
      </Card>
    </section>
  );
}
