import { CheckCircle2, Crown, Plus, XCircle } from "lucide-react";
import { type FormEvent, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { PriorityBadge } from "@/components/tickets";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Avatar, Card, Field, Modal, Progress, Tabs } from "@/components/ui/primitives";
import { demoToast } from "@/components/ui/toast";
import { CATEGORIES, SLA_TARGETS, TECHNICIANS, USERS } from "@/lib/demo/data";

function ActiveBadge({ active, on, off }: { active: boolean; on: string; off: string }) {
  const Icon = active ? CheckCircle2 : XCircle;
  return (
    <Badge tone={active ? "accent" : "neutral"}>
      <Icon aria-hidden className="size-3" />
      {active ? on : off}
    </Badge>
  );
}

const USER_COLUMNS: Column<(typeof USERS)[number]>[] = [
  {
    key: "name",
    header: "Nome",
    sortValue: (user) => user.name,
    render: (user) => (
      <div className="flex items-center gap-3">
        <Avatar name={user.name} />
        <div>
          <p className="flex items-center gap-1.5 font-medium whitespace-nowrap">
            {user.name}
            {user.vip && (
              <Badge tone="warn">
                <Crown aria-hidden className="size-3" />
                VIP
              </Badge>
            )}
          </p>
          <p className="font-mono text-[11px] text-muted">{user.email}</p>
        </div>
      </div>
    ),
  },
  { key: "role", header: "Papel", sortValue: (user) => user.role, render: (user) => <Badge>{user.role}</Badge> },
  { key: "department", header: "Setor", sortValue: (user) => user.department, render: (user) => user.department },
  {
    key: "active",
    header: "Situação",
    render: (user) => <ActiveBadge active={user.active} on="Ativo" off="Inativo" />,
  },
];

const TECHNICIAN_COLUMNS: Column<(typeof TECHNICIANS)[number]>[] = [
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
    sortValue: (technician) => technician.open,
    render: (technician) => (
      <div className="w-28">
        <p className="mb-1 text-xs text-muted">
          {technician.open} de {technician.capacity}
        </p>
        <Progress
          value={(technician.open / technician.capacity) * 100}
          tone={technician.open / technician.capacity >= 0.9 ? "warn" : "accent"}
          label={`Carga de ${technician.name}`}
        />
      </div>
    ),
  },
  { key: "resolved", header: "Resolvidos no mês", sortValue: (t) => t.resolved, render: (t) => t.resolved },
  {
    key: "available",
    header: "Situação",
    render: (technician) => (
      <ActiveBadge active={technician.available} on="Disponível" off="Ausente" />
    ),
  },
];

const CATEGORY_COLUMNS: Column<(typeof CATEGORIES)[number]>[] = [
  { key: "name", header: "Categoria", sortValue: (c) => c.name, render: (c) => <span className="font-medium">{c.name}</span> },
  { key: "children", header: "Subcategorias", sortValue: (c) => c.children, render: (c) => c.children },
  {
    key: "skill",
    header: "Habilidade padrão",
    render: (c) => (
      <Badge tone="info" mono>
        {c.skill}
      </Badge>
    ),
  },
  { key: "sla", header: "Política de SLA", render: (c) => c.sla },
  { key: "active", header: "Situação", render: (c) => <ActiveBadge active={c.active} on="Ativa" off="Inativa" /> },
];

const SLA_COLUMNS: Column<(typeof SLA_TARGETS)[number]>[] = [
  { key: "priority", header: "Prioridade", render: (s) => <PriorityBadge priority={s.priority} /> },
  { key: "first", header: "1ª resposta", render: (s) => s.firstResponse },
  { key: "resolution", header: "Resolução", render: (s) => s.resolution },
  {
    key: "compliance",
    header: "Cumprimento",
    render: (s) => (
      <div className="flex w-40 items-center gap-2">
        <Progress value={s.compliance} label={`Cumprimento de ${s.priority}`} />
        <span className="text-xs text-muted">{s.compliance}%</span>
      </div>
    ),
  },
];

const NEW_LABELS: Record<string, string> = {
  users: "usuário",
  technicians: "técnico",
  categories: "categoria",
  sla: "política de SLA",
};

export function RegistersPage() {
  const [tab, setTab] = useState("users");
  const [creating, setCreating] = useState(false);
  const newLabel = NEW_LABELS[tab]!;

  function submit(event: FormEvent) {
    event.preventDefault();
    setCreating(false);
    demoToast("Cadastro criado");
  }

  return (
    <section>
      <PageHeader
        title="Cadastros"
        description="Usuários, técnicos, categorias e prazos de atendimento."
        actions={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus aria-hidden className="size-4" />
            Novo: {newLabel}
          </Button>
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
              count: USERS.length,
              content: (
                <div className="-mx-4">
                  <DataTable label="Usuários" columns={USER_COLUMNS} rows={USERS} rowKey={(u) => u.email} pageSize={6} />
                </div>
              ),
            },
            {
              value: "technicians",
              label: "Técnicos",
              count: TECHNICIANS.length,
              content: (
                <div className="-mx-4">
                  <DataTable label="Técnicos" columns={TECHNICIAN_COLUMNS} rows={TECHNICIANS} rowKey={(t) => t.email} />
                </div>
              ),
            },
            {
              value: "categories",
              label: "Categorias",
              count: CATEGORIES.length,
              content: (
                <div className="-mx-4">
                  <DataTable label="Categorias" columns={CATEGORY_COLUMNS} rows={CATEGORIES} rowKey={(c) => c.name} />
                </div>
              ),
            },
            {
              value: "sla",
              label: "SLAs",
              count: SLA_TARGETS.length,
              content: (
                <div className="-mx-4">
                  <DataTable label="Prazos de SLA" columns={SLA_COLUMNS} rows={SLA_TARGETS} rowKey={(s) => s.priority} />
                </div>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        open={creating}
        onOpenChange={setCreating}
        title={`Novo: ${newLabel}`}
        footer={
          <>
            <Button onClick={() => setCreating(false)}>Cancelar</Button>
            <Button variant="primary" type="submit" form="new-register">
              Salvar
            </Button>
          </>
        }
      >
        <form id="new-register" onSubmit={submit} className="space-y-4">
          <Field label="Nome" htmlFor="register-name">
            <Input id="register-name" required />
          </Field>
          <Field label="Descrição" htmlFor="register-description" hint="Opcional">
            <Input id="register-description" />
          </Field>
        </form>
      </Modal>
    </section>
  );
}
