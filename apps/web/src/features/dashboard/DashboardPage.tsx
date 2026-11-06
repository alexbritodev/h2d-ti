import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { BarChart } from "@/components/ui/charts";
import { Card, CardHeader, Progress, Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

import { overviewQuery, percent, PERIODS, shortDay, usd } from "./metrics";

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card className="p-5">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
      <p className="mt-3 text-xs text-muted">{hint}</p>
    </Card>
  );
}

function Rows({ rows }: { rows: [string, string | number][] }) {
  return (
    <dl className="grid grid-cols-2 gap-4 p-5">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs text-muted">{label}</dt>
          <dd className="text-xl font-semibold">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [days, setDays] = useState(30);
  const { data, isPending, isError } = useQuery(overviewQuery(days));

  return (
    <section className="space-y-6">
      <PageHeader
        live
        title="Dashboard"
        description="Números reais do assistente e dos chamados no período."
        actions={
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
        }
      />

      {isError && (
        <p role="alert" className="rounded-xl bg-danger-soft p-4 text-sm text-danger">
          Não foi possível carregar o dashboard. Tente novamente em instantes.
        </p>
      )}

      {isPending && !isError && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-busy>
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-32 rounded-xl" />
          ))}
        </div>
      )}

      {data && (
        <>
          {data.sla.open_overdue > 0 && (
            <div
              role="alert"
              className="flex flex-wrap items-center gap-3 rounded-xl border border-warn/30 bg-warn/10 px-4 py-3"
            >
              <AlertTriangle aria-hidden className="size-5 shrink-0 text-warn" />
              <p className="min-w-0 flex-1">
                <strong className="font-semibold">
                  {data.sla.open_overdue} {data.sla.open_overdue === 1 ? "chamado aberto" : "chamados abertos"}
                </strong>{" "}
                com o prazo de resolução vencido.
              </p>
              <Button
                className="h-8 border border-border bg-surface"
                onClick={() => void navigate({ to: "/chamados" })}
              >
                Ver na fila
              </Button>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi
              label="Defleção do assistente"
              value={percent(data.bot.deflection_rate)}
              hint={`${data.bot.deflected} de ${data.bot.conversations} conversas sem chamado`}
            />
            <Kpi
              label="Custo por conversa"
              value={usd(data.cost.per_conversation_usd)}
              hint={`${usd(data.cost.total_usd)} em ${data.cost.llm_calls} chamadas ao modelo`}
            />
            <Kpi
              label="Chamados abertos no período"
              value={String(data.volume.tickets)}
              hint={`${data.volume.conversations} conversas no mesmo período`}
            />
            <Kpi
              label="SLA cumprido"
              value={percent(data.sla.met_rate)}
              hint={`${data.sla.met} de ${data.sla.resolved_with_due} resolvidos dentro do prazo`}
            />
          </div>

          <Card>
            <CardHeader title="Chamados por dia" description={`Últimos ${data.days} dias`} />
            <div className="p-5">
              <BarChart
                // A chave refaz a animação de entrada ao trocar de período.
                key={days}
                data={data.volume.by_day.map((d) => ({ label: shortDay(d.day), value: d.tickets }))}
                label={`Chamados por dia nos últimos ${data.days} dias`}
                unit="chamados"
              />
            </div>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card className="overflow-hidden">
              <CardHeader title="Conversas do assistente" description="Só conta quem fez ao menos uma pergunta" />
              <Rows
                rows={[
                  ["Conversas", data.bot.conversations],
                  ["Sem chamado (defletidas)", data.bot.deflected],
                  ["Viraram chamado", data.bot.with_ticket],
                  ["Escalonadas, sem chamado", data.bot.escalated_without_ticket],
                ]}
              />
              <div className="px-5 pb-5">
                <Progress
                  value={(data.bot.deflection_rate ?? 0) * 100}
                  tone="accent"
                  label="Defleção do assistente"
                />
              </div>
            </Card>
            <Card className="overflow-hidden">
              <CardHeader title="Prazo de resolução (SLA)" description="Chamados resolvidos no período, com prazo" />
              <Rows
                rows={[
                  ["Resolvidos com prazo", data.sla.resolved_with_due],
                  ["Dentro do prazo", data.sla.met],
                  ["Fora do prazo", data.sla.breached],
                  ["Abertos e vencidos agora", data.sla.open_overdue],
                ]}
              />
              <div className="px-5 pb-5">
                <Progress
                  value={(data.sla.met_rate ?? 0) * 100}
                  tone={data.sla.met_rate != null && data.sla.met_rate < 0.8 ? "warn" : "accent"}
                  label="SLA cumprido"
                />
              </div>
            </Card>
          </div>
        </>
      )}
    </section>
  );
}
