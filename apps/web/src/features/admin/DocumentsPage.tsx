import { CheckCircle2, CircleAlert, FileText, LoaderCircle, RefreshCw, UploadCloud } from "lucide-react";
import { type ChangeEvent, type DragEvent, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge, type Tone } from "@/components/ui/badge";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Card, CardHeader, Progress } from "@/components/ui/primitives";
import { demoToast } from "@/components/ui/toast";
import { DOCUMENTS } from "@/lib/demo/data";
import { cn } from "@/lib/utils";

type Document = (typeof DOCUMENTS)[number];

const STATUS: Record<string, { label: string; tone: Tone; icon: typeof CheckCircle2 }> = {
  published: { label: "Publicado", tone: "accent", icon: CheckCircle2 },
  parsing: { label: "Lendo arquivo", tone: "info", icon: LoaderCircle },
  embedding: { label: "Indexando", tone: "info", icon: LoaderCircle },
  failed: { label: "Falhou", tone: "danger", icon: CircleAlert },
};

const COLUMNS: Column<Document>[] = [
  {
    key: "title",
    header: "Documento",
    sortValue: (doc) => doc.title,
    render: (doc) => (
      <div className="flex items-center gap-3">
        <FileText aria-hidden className="size-5 shrink-0 text-muted" />
        <div>
          <p className="font-medium">{doc.title}</p>
          <p className="font-mono text-[11px] text-muted">{doc.file}</p>
        </div>
      </div>
    ),
  },
  { key: "category", header: "Categoria", sortValue: (doc) => doc.category, render: (doc) => doc.category },
  {
    key: "visibility",
    header: "Visibilidade",
    render: (doc) => <Badge tone={doc.visibility === "Só TI" ? "warn" : "neutral"}>{doc.visibility}</Badge>,
  },
  {
    key: "version",
    header: "Versão",
    render: (doc) => (
      <Badge mono tone="neutral">
        {doc.version}
      </Badge>
    ),
  },
  { key: "owner", header: "Dono", render: (doc) => <span className="whitespace-nowrap">{doc.owner}</span> },
  { key: "expires", header: "Validade", render: (doc) => doc.expires },
  {
    key: "status",
    header: "Status",
    sortValue: (doc) => doc.status,
    render: (doc) => {
      const status = STATUS[doc.status]!;
      const Icon = status.icon;
      return (
        <Badge tone={status.tone}>
          <Icon aria-hidden className={cn("size-3", status.icon === LoaderCircle && "animate-spin")} />
          {status.label}
        </Badge>
      );
    },
  },
  {
    key: "actions",
    header: "Ações",
    render: (doc) => (
      <button
        type="button"
        aria-label={`Reindexar ${doc.title}`}
        title="Reindexar"
        onClick={() => demoToast(`Reindexação simulada de ${doc.title}`)}
        className="flex size-8 cursor-pointer items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-text"
      >
        <RefreshCw aria-hidden className="size-4" />
      </button>
    ),
  },
];

const JOBS = [
  { name: "Guia de impressoras v1", step: "Indexando trechos", progress: 72 },
  { name: "Manual do e-mail v1", step: "Lendo o arquivo", progress: 28 },
];

export function DocumentsPage() {
  const [dragging, setDragging] = useState(false);

  // O arquivo não sai do navegador: o envio de verdade entra na fase F2.
  function receive(files: FileList | null) {
    if (files?.[0]) demoToast(`${files[0].name} não foi enviado`);
  }

  return (
    <section className="space-y-4">
      <PageHeader
        title="Documentos"
        description="Envie manuais para a base e acompanhe o processamento."
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <label
          onDragOver={(event: DragEvent) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event: DragEvent) => {
            event.preventDefault();
            setDragging(false);
            receive(event.dataTransfer.files);
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed bg-surface p-8 text-center transition-colors focus-within:outline-2 focus-within:outline-accent xl:col-span-2",
            dragging ? "border-accent bg-accent-soft" : "border-border hover:border-muted",
          )}
        >
          <UploadCloud aria-hidden className="mb-3 size-9 text-accent" />
          <span className="font-medium">Arraste um arquivo ou clique para escolher</span>
          <span className="text-xs text-muted">PDF, DOCX, PPTX, HTML ou Markdown, até 50 MB</span>
          <input
            type="file"
            accept=".pdf,.docx,.pptx,.html,.md"
            className="sr-only"
            onChange={(event: ChangeEvent<HTMLInputElement>) => receive(event.target.files)}
          />
        </label>

        <Card>
          <CardHeader title="Em processamento" description={`${JOBS.length} arquivos na fila`} />
          <ul className="space-y-4 p-5">
            {JOBS.map((job) => (
              <li key={job.name}>
                <div className="mb-1 flex justify-between gap-2">
                  <span className="truncate font-medium">{job.name}</span>
                  <span className="text-xs text-muted">{job.progress}%</span>
                </div>
                <Progress value={job.progress} label={`Progresso de ${job.name}`} tone="info" />
                <p className="mt-1 text-xs text-muted">{job.step}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader title="Documentos da base" description={`${DOCUMENTS.length} documentos`} />
        <DataTable label="Documentos da base" columns={COLUMNS} rows={DOCUMENTS} rowKey={(doc) => doc.id} />
      </Card>
    </section>
  );
}
