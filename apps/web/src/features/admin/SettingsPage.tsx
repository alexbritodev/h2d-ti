import { Save } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Card, CardHeader, Select, Switch } from "@/components/ui/primitives";
import { demoToast } from "@/components/ui/toast";
import { PROMPT_VERSIONS } from "@/lib/demo/data";

const PROMPT_COLUMNS: Column<(typeof PROMPT_VERSIONS)[number]>[] = [
  {
    key: "version",
    header: "Versão",
    render: (prompt) => (
      <Badge mono tone="neutral">
        {prompt.version}
      </Badge>
    ),
  },
  { key: "purpose", header: "Finalidade", render: (prompt) => prompt.purpose },
  {
    key: "status",
    header: "Situação",
    render: (prompt) => (
      <Badge tone={prompt.status === "Ativa" ? "accent" : "neutral"} dot>
        {prompt.status}
      </Badge>
    ),
  },
  { key: "accuracy", header: "Acerto na avaliação", render: (prompt) => prompt.accuracy },
  { key: "date", header: "Data", render: (prompt) => prompt.date },
];

const AUTOMATIONS = [
  { id: "notify", title: "Avisar técnico de novo chamado", detail: "Por e-mail, com resumo e prioridade", on: true },
  { id: "sla", title: "Alertar SLA em risco", detail: "Ao atingir 75% e 100% do prazo", on: true },
  { id: "report", title: "Relatório semanal", detail: "Toda segunda de manhã, para o gestor de TI", on: false },
  { id: "csat", title: "Pesquisa de satisfação", detail: "Depois que o chamado é resolvido", on: false },
];

export function SettingsPage() {
  const [threshold, setThreshold] = useState(70);
  const [triage, setTriage] = useState(60);
  const [enabled, setEnabled] = useState(
    Object.fromEntries(AUTOMATIONS.map((item) => [item.id, item.on])),
  );

  return (
    <section className="space-y-4">
      <PageHeader
        title="Configurações"
        description="Limiares da IA, modelos, versões de prompt e automações."
        actions={
          <Button variant="primary" onClick={() => demoToast("Configurações salvas")}>
            <Save aria-hidden className="size-4" />
            Salvar
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title="Inteligência artificial" description="Quando o assistente responde ou escalona" />
          <div className="space-y-5 p-5">
            {[
              {
                id: "threshold",
                label: "Confiança mínima para responder",
                value: threshold,
                set: setThreshold,
              },
              {
                id: "triage",
                label: "Confiança mínima para atribuir sem triagem",
                value: triage,
                set: setTriage,
              },
            ].map((field) => (
              <div key={field.id}>
                <div className="mb-1.5 flex justify-between gap-2">
                  <label htmlFor={field.id} className="font-medium">
                    {field.label}
                  </label>
                  <span className="font-mono text-xs">{field.value}%</span>
                </div>
                <input
                  id={field.id}
                  type="range"
                  min={0}
                  max={100}
                  value={field.value}
                  onChange={(event) => field.set(Number(event.target.value))}
                  className="w-full cursor-pointer accent-[var(--accent)]"
                />
              </div>
            ))}
            <div>
              <label htmlFor="model-answer" className="mb-1.5 block font-medium">
                Modelo para responder
              </label>
              <Select id="model-answer" defaultValue="medio">
                <option value="medio">Modelo médio (definição na fase F3)</option>
                <option value="pequeno">Modelo pequeno</option>
              </Select>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Automações" description="Avisos e relatórios" />
          <ul className="divide-y divide-border">
            {AUTOMATIONS.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="text-xs text-muted">{item.detail}</p>
                </div>
                <Switch
                  label={item.title}
                  checked={enabled[item.id]}
                  onCheckedChange={(checked: boolean) =>
                    setEnabled((current) => ({ ...current, [item.id]: checked }))
                  }
                />
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader title="Versões de prompt" description="Cada resposta guarda a versão que a gerou" />
        <DataTable
          label="Versões de prompt"
          columns={PROMPT_COLUMNS}
          rows={PROMPT_VERSIONS}
          rowKey={(prompt) => prompt.version}
        />
      </Card>
    </section>
  );
}
