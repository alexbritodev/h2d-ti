import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Card, CardHeader } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";

import { type PromptRow, promptsQuery, saveTriageSettings, triageSettingsQuery } from "./api";

const PROMPT_COLUMNS: Column<PromptRow>[] = [
  {
    key: "version",
    header: "Versão",
    render: (prompt) => (
      <Badge mono tone="neutral">
        {prompt.name}-v{prompt.version}
      </Badge>
    ),
  },
  {
    key: "status",
    header: "Situação",
    render: (prompt) => (
      <Badge tone={prompt.is_active ? "accent" : "neutral"} dot>
        {prompt.is_active ? "Ativa" : "Arquivada"}
      </Badge>
    ),
  },
  {
    key: "date",
    header: "Criada em",
    sortValue: (prompt) => prompt.created_at,
    render: (prompt) => new Date(prompt.created_at).toLocaleDateString("pt-BR"),
  },
];

// Avisos que o n8n já envia hoje. Não há chave para ligar ou desligar: aparecem só para consulta.
const AUTOMATIONS = [
  { title: "Avisar técnico de novo chamado", detail: "Por e-mail, com resumo e prioridade" },
  { title: "Alertar SLA em risco", detail: "Ao atingir 75% e 100% do prazo" },
  { title: "Convite de usuário", detail: "E-mail com o link para definir a senha" },
];

function TriageField({ initial }: { initial: number }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(Math.round(initial * 100));
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    const result = await saveTriageSettings({ confidence_threshold: value / 100 });
    setBusy(false);
    if (!result.ok) return toast("Não foi possível salvar", result.message);
    await queryClient.invalidateQueries({ queryKey: ["admin"] });
    toast("Ajuste salvo", `Confiança mínima: ${value}%.`);
  }

  return (
    <div className="space-y-5 p-5">
      <div>
        <div className="mb-1.5 flex justify-between gap-2">
          <label htmlFor="triage" className="font-medium">
            Confiança mínima para atribuir sem triagem
          </label>
          <span className="font-mono text-xs">{value}%</span>
        </div>
        <input
          id="triage"
          type="range"
          min={0}
          max={100}
          value={value}
          onChange={(event) => setValue(Number(event.target.value))}
          className="w-full cursor-pointer accent-[var(--accent)]"
        />
        <p className="mt-1.5 text-xs text-muted">
          Abaixo deste valor o chamado vai para a triagem manual do líder.
        </p>
      </div>
      <Button variant="primary" onClick={save} disabled={busy}>
        <Save aria-hidden className="size-4" />
        {busy ? "Salvando…" : "Salvar"}
      </Button>
    </div>
  );
}

export function SettingsPage() {
  const settings = useQuery(triageSettingsQuery);
  const prompts = useQuery(promptsQuery);

  return (
    <section className="space-y-4">
      <PageHeader title="Configurações" description="Limiar de triagem, versões de prompt e avisos." />

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title="Triagem" description="Quando o chamado é atribuído sozinho" />
          {settings.isError && (
            <p role="alert" className="p-5 text-danger">
              Não foi possível carregar o ajuste.
            </p>
          )}
          {settings.data && (
            <TriageField
              // A chave refaz o campo quando o valor salvo muda.
              key={settings.data.confidence_threshold}
              initial={settings.data.confidence_threshold}
            />
          )}
        </Card>

        <Card>
          <CardHeader title="Avisos por e-mail" description="Enviados pelo n8n" />
          <ul className="divide-y divide-border">
            {AUTOMATIONS.map((item) => (
              <li key={item.title} className="flex items-center justify-between gap-4 px-5 py-3.5">
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="text-xs text-muted">{item.detail}</p>
                </div>
                <Badge tone="accent" dot>
                  Ativo
                </Badge>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader title="Versões de prompt" description="Cada resposta guarda a versão que a gerou" />
        {prompts.isError ? (
          <p role="alert" className="p-5 text-danger">
            Não foi possível carregar os prompts.
          </p>
        ) : (
          <DataTable
            label="Versões de prompt"
            columns={PROMPT_COLUMNS}
            rows={prompts.data ?? []}
            rowKey={(prompt) => prompt.id}
            empty="Nenhuma versão de prompt gravada."
          />
        )}
      </Card>
    </section>
  );
}
