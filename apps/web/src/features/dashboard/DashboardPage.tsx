import { useNavigate } from "@tanstack/react-router";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Download } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { PriorityBadge, SlaCell, StatusBadge } from "@/components/tickets";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BarChart, RankedBars, Sparkline } from "@/components/ui/charts";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Avatar, Card, CardHeader, Progress, Timeline } from "@/components/ui/primitives";
import { demoToast } from "@/components/ui/toast";
import {
  ACTIVITY,
  KPIS,
  TECHNICIANS,
  type Ticket,
  TICKETS,
  TICKETS_BY_CATEGORY,
  VOLUME_BY_DAY,
} from "@/lib/demo/data";
import { cn } from "@/lib/utils";

const PERIODS = [
  { days: 7, label: "7 dias" },
  { days: 14, label: "14 dias" },
];

const RECENT_COLUMNS: Column<Ticket>[] = [
  {
    key: "code",
    header: "Código",
    render: (ticket) => <span className="font-mono text-xs">{ticket.code}</span>,
  },
  { key: "subject", header: "Assunto", render: (ticket) => ticket.subject },
  { key: "priority", header: "Prioridade", render: (t) => <PriorityBadge priority={t.priority} /> },
  { key: "status", header: "Status", render: (t) => <StatusBadge status={t.status} /> },
  { key: "sla", header: "SLA", render: (t) => <SlaCell used={t.slaUsed} left={t.slaLeft} /> },
];

export function DashboardPage() {
  const navigate = useNavigate();
  const [days, setDays] = useState(14);
  const atRisk = TICKETS.filter((ticket) => ticket.slaUsed >= 75 && ticket.status !== "resolvido");

  return (
    <section className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Visão geral do atendimento e do assistente."
        actions={
          <>
            <div role="group" aria-label="Período" className="flex rounded-lg border border-border bg-surface p-0.5">
              {PERIODS.map((period) => (
                <button
                  key={period.days}
                  type="button"
                  aria-pressed={days === period.days}
                  onClick={() => setDays(period.days)}
                  className={cn(
                    "h-[34px] cursor-pointer rounded-md px-3 text-sm",
                    days === period.days ? "bg-surface-2 font-medium" : "text-muted hover:text-text",
                  )}
                >
                  {period.label}
                </button>
              ))}
            </div>
            <Button
              className="border border-border bg-surface"
              onClick={() => demoToast("Exportação simulada")}
            >
              <Download aria-hidden className="size-4" />
              Exportar
            </Button>
          </>
        }
      />

      {atRisk.length > 0 && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-warn/30 bg-warn/10 px-4 py-3"
        >
          <AlertTriangle aria-hidden className="size-5 shrink-0 text-warn" />
          <p className="min-w-0 flex-1">
            <strong className="font-semibold">{atRisk.length} chamados</strong> com o SLA em risco
            ou estourado.
          </p>
          <Button className="h-8 border border-border bg-surface" onClick={() => void navigate({ to: "/chamados" })}>
            Ver na fila
          </Button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {KPIS.map((kpi) => {
          const Arrow = kpi.delta.startsWith("-") ? ArrowDownRight : ArrowUpRight;
          return (
            <Card key={kpi.label} className="p-5">
              <p className="text-sm text-muted">{kpi.label}</p>
              <div className="mt-2 flex items-end justify-between gap-2">
                <p className="text-3xl font-semibold tracking-tight">{kpi.value}</p>
                <Sparkline values={kpi.trend} label={`Tendência de ${kpi.label}`} />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Badge tone={kpi.positive ? "accent" : "warn"}>
                  <Arrow aria-hidden className="size-3" />
                  {kpi.delta}
                </Badge>
                <span className="text-xs text-muted">{kpi.hint}</span>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Chamados por dia" description={`Últimos ${days} dias`} />
          <div className="p-5">
            <BarChart
              // A chave refaz a animação de entrada ao trocar de período.
              key={days}
              data={VOLUME_BY_DAY.slice(-days)}
              label={`Chamados por dia nos últimos ${days} dias`}
              unit="chamados"
            />
          </div>
        </Card>
        <Card>
          <CardHeader title="Chamados por categoria" description="Mês atual" />
          <div className="p-5">
            <RankedBars data={TICKETS_BY_CATEGORY} unit="chamados" />
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader title="Carga por técnico" description="Chamados abertos e capacidade" />
          <ul className="divide-y divide-border">
            {TECHNICIANS.map((technician) => {
              const load = (technician.open / technician.capacity) * 100;
              return (
                <li key={technician.email} className="flex items-center gap-3 px-5 py-3">
                  <Avatar name={technician.name} />
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="truncate font-medium">{technician.name}</span>
                      <span className="text-xs text-muted">
                        {technician.open}/{technician.capacity}
                      </span>
                    </div>
                    <Progress
                      value={load}
                      tone={load >= 90 ? "warn" : "accent"}
                      label={`Carga de ${technician.name}`}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Atividade recente" />
          <div className="p-5">
            <Timeline items={ACTIVITY} />
          </div>
        </Card>
        <Card className="overflow-hidden xl:col-span-1">
          <CardHeader title="Resolução do assistente" description="Conversas do mês" />
          <dl className="grid grid-cols-2 gap-4 p-5">
            {[
              ["Conversas", "1.284"],
              ["Resolvidas", "475"],
              ["Escalonadas", "809"],
              ["Avaliação positiva", "81%"],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="text-xl font-semibold">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader title="Chamados que pedem atenção" description="Ordenados pelo consumo do SLA" />
        <DataTable
          label="Chamados que pedem atenção"
          columns={RECENT_COLUMNS}
          rows={[...atRisk].sort((a, b) => b.slaUsed - a.slaUsed)}
          rowKey={(ticket) => ticket.code}
          onRowClick={() => void navigate({ to: "/chamados" })}
        />
      </Card>
    </section>
  );
}
