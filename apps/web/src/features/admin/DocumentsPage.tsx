import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Clock, FileText, LoaderCircle, Pencil, RefreshCw, UploadCloud } from "lucide-react";
import { type ChangeEvent, type DragEvent, type FormEvent, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, Field, Modal, Select } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";
import {
  ACCEPTED_EXTENSIONS,
  documentsQuery,
  isActive,
  jobsQuery,
  type KbDocument,
  type KbJob,
  MAX_UPLOAD_MB,
  reindex,
  updateDocument,
  uploadDocument,
  type Visibility,
} from "@/features/kb/api";
import { cn } from "@/lib/utils";

type StatusView = { label: string; tone: Tone; icon: typeof CheckCircle2; spin?: boolean };

const VERSION_STATUS: Record<string, StatusView> = {
  active: { label: "Publicado", tone: "accent", icon: CheckCircle2 },
  processing: { label: "Processando", tone: "info", icon: LoaderCircle, spin: true },
  failed: { label: "Falhou", tone: "danger", icon: CircleAlert },
  archived: { label: "Arquivado", tone: "neutral", icon: Clock },
};

const JOB_STATE: Record<string, StatusView> = {
  queued: { label: "Na fila", tone: "neutral", icon: Clock },
  running: { label: "Processando", tone: "info", icon: LoaderCircle, spin: true },
  succeeded: { label: "Concluído", tone: "accent", icon: CheckCircle2 },
  failed: { label: "Falhou", tone: "danger", icon: CircleAlert },
};

function StatusBadge({ view }: { view: StatusView }) {
  const Icon = view.icon;
  return (
    <Badge tone={view.tone}>
      <Icon aria-hidden className={cn("size-3", view.spin && "animate-spin")} />
      {view.label}
    </Badge>
  );
}

const formatDate = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";

const formatSize = (bytes: number | null) =>
  bytes === null ? "—" : bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

export function DocumentsPage() {
  const queryClient = useQueryClient();
  const jobs = useQuery({
    ...jobsQuery,
    // Enquanto houver job na fila ou rodando, a tela acompanha sozinha.
    refetchInterval: (query) => (isActive(query.state.data) ? 2000 : false),
  });
  const documents = useQuery(documentsQuery);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [visibility, setVisibility] = useState<Visibility | "">("");
  const [editing, setEditing] = useState<KbDocument | null>(null);

  // A lista de documentos acompanha os jobs: quando um job muda, o status do documento também.
  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: documentsQuery.queryKey });
  }, [jobs.dataUpdatedAt, queryClient]);

  async function receive(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      const result = await uploadDocument(file, visibility);
      if (!result.ok) toast(`${file.name} não foi enviado`, result.message);
      else if (result.data.duplicate) toast(`${file.name} já estava na base`, "Nada foi processado de novo.");
      else toast(`${file.name} enviado`, "Entrou na fila de processamento.");
    }
    setUploading(false);
    void queryClient.invalidateQueries({ queryKey: jobsQuery.queryKey });
  }

  async function doReindex(doc: KbDocument) {
    const result = await reindex(doc.id);
    if (!result.ok) return toast("Não foi possível reindexar", result.message);
    toast("Reindexação na fila", doc.title);
    void queryClient.invalidateQueries({ queryKey: jobsQuery.queryKey });
  }

  const active = (jobs.data ?? []).filter((job) => job.state === "queued" || job.state === "running");

  const columns: Column<KbDocument>[] = [
    {
      key: "title",
      header: "Documento",
      sortValue: (doc) => doc.title,
      render: (doc) => (
        <div className="flex items-center gap-3">
          <FileText aria-hidden className="size-5 shrink-0 text-muted" />
          <div>
            <p className="font-medium">{doc.title}</p>
            <p className="font-mono text-[11px] text-muted">
              {doc.filename ?? "—"} · {formatSize(doc.size_bytes)}
            </p>
          </div>
        </div>
      ),
    },
    { key: "category", header: "Categoria", sortValue: (doc) => doc.category ?? "", render: (doc) => doc.category ?? "—" },
    {
      key: "visibility",
      header: "Visibilidade",
      render: (doc) => (
        <Badge tone={doc.visibility === "it" ? "warn" : "neutral"}>{doc.visibility === "it" ? "Só TI" : "Público"}</Badge>
      ),
    },
    {
      key: "version",
      header: "Versão",
      render: (doc) => (
        <Badge mono tone="neutral">
          {doc.version_number ? `v${doc.version_number}` : "—"}
        </Badge>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (doc) => doc.version_status ?? "",
      render: (doc) => (
        <div>
          {doc.version_status && <StatusBadge view={VERSION_STATUS[doc.version_status]!} />}
          {doc.error && (
            <p role="alert" className="mt-1 max-w-64 text-xs text-danger">
              {doc.error}
            </p>
          )}
        </div>
      ),
    },
    { key: "published", header: "Publicado em", sortValue: (doc) => doc.published_at ?? "", render: (doc) => formatDate(doc.published_at) },
    {
      key: "actions",
      header: "Ações",
      render: (doc) => (
        <div className="flex gap-1">
          <Button aria-label={`Editar ${doc.title}`} title="Editar" onClick={() => setEditing(doc)}>
            <Pencil aria-hidden className="size-4" />
          </Button>
          <Button aria-label={`Reindexar ${doc.title}`} title="Reindexar" onClick={() => void doReindex(doc)}>
            <RefreshCw aria-hidden className="size-4" />
          </Button>
        </div>
      ),
    },
  ];

  const jobColumns: Column<KbJob>[] = [
    {
      key: "doc",
      header: "Documento",
      render: (job) => (
        <div>
          <p className="font-medium">{job.document_title}</p>
          <p className="font-mono text-[11px] text-muted">
            {job.filename} · v{job.version_number}
          </p>
        </div>
      ),
    },
    { key: "state", header: "Estado", render: (job) => <StatusBadge view={JOB_STATE[job.state]!} /> },
    { key: "attempts", header: "Tentativas", render: (job) => job.attempts },
    { key: "queued", header: "Enviado em", sortValue: (job) => job.queued_at, render: (job) => formatDate(job.queued_at) },
    { key: "finished", header: "Terminou em", render: (job) => formatDate(job.finished_at) },
    {
      key: "error",
      header: "Motivo da falha",
      render: (job) => (job.error ? <span className="text-xs text-danger">{job.error}</span> : "—"),
    },
  ];

  return (
    <section className="space-y-4">
      <PageHeader
        live
        title="Documentos"
        description="Envie manuais para a base e acompanhe o processamento."
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-3 xl:col-span-2">
          <label
            onDragOver={(event: DragEvent) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event: DragEvent) => {
              event.preventDefault();
              setDragging(false);
              void receive(event.dataTransfer.files);
            }}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed bg-surface p-8 text-center transition-colors focus-within:outline-2 focus-within:outline-accent",
              dragging ? "border-accent bg-accent-soft" : "border-border hover:border-muted",
              uploading && "pointer-events-none opacity-60",
            )}
          >
            <UploadCloud aria-hidden className="mb-3 size-9 text-accent" />
            <span className="font-medium">{uploading ? "Enviando…" : "Arraste arquivos ou clique para escolher"}</span>
            <span className="text-xs text-muted">
              Markdown, texto, PDF ou DOCX, até {MAX_UPLOAD_MB} MB cada. PDF digitalizado (só imagem) não é lido.
            </span>
            <input
              type="file"
              multiple
              accept={ACCEPTED_EXTENSIONS}
              className="sr-only"
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                void receive(event.target.files);
                event.target.value = "";
              }}
            />
          </label>
          <Field
            label="Visibilidade dos novos documentos"
            htmlFor="upload-visibility"
            hint="Manual em Markdown pode trazer o campo “visibilidade” no cabeçalho. PDF e DOCX não têm cabeçalho: sem escolher aqui, o documento fica público."
          >
            <Select
              id="upload-visibility"
              value={visibility}
              onChange={(event) => setVisibility(event.target.value as Visibility | "")}
            >
              <option value="">Seguir o cabeçalho do arquivo</option>
              <option value="public">Público (todos os usuários)</option>
              <option value="it">Só TI (técnicos e administradores)</option>
            </Select>
          </Field>
        </div>

        <Card>
          <CardHeader
            title="Em processamento"
            description={active.length ? `${active.length} na fila` : "Nenhum arquivo na fila"}
          />
          <ul className="space-y-3 p-5">
            {active.length === 0 && <li className="text-muted">Tudo processado.</li>}
            {active.map((job) => (
              <li key={job.id} className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">{job.document_title}</span>
                <StatusBadge view={JOB_STATE[job.state]!} />
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader title="Documentos da base" description={`${documents.data?.length ?? 0} documentos`} />
        {documents.isError ? (
          <p role="alert" className="p-5 text-danger">
            Não foi possível carregar os documentos.
          </p>
        ) : (
          <DataTable
            label="Documentos da base"
            columns={columns}
            rows={documents.data ?? []}
            rowKey={(doc) => doc.id}
            empty="Nenhum documento ainda. Envie um manual acima."
          />
        )}
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Histórico de processamento" description="Os 30 envios mais recentes" />
        <DataTable
          label="Histórico de processamento"
          columns={jobColumns}
          rows={jobs.data ?? []}
          rowKey={(job) => job.id}
          pageSize={6}
          empty="Nenhum processamento ainda."
        />
      </Card>

      <EditModal
        key={editing?.id ?? "none"}
        document={editing}
        onClose={() => setEditing(null)}
        onDone={() => {
          setEditing(null);
          void queryClient.invalidateQueries({ queryKey: documentsQuery.queryKey });
        }}
      />
    </section>
  );
}

function EditModal({
  document,
  onClose,
  onDone,
}: {
  document: KbDocument | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!document) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    const result = await updateDocument(document.id, {
      title: String(form.get("title") ?? ""),
      category: String(form.get("category") ?? ""),
      visibility: String(form.get("visibility")) as Visibility,
    });
    setBusy(false);
    if (!result.ok) return setError(result.message);
    toast("Documento atualizado", document.title);
    onDone();
  }

  return (
    <Modal
      open={document !== null}
      onOpenChange={(open) => !open && onClose()}
      title="Editar documento"
      description={document?.filename ?? undefined}
      footer={
        <>
          <Button onClick={onClose}>Cancelar</Button>
          <Button variant="primary" type="submit" form="edit-document" disabled={busy}>
            {busy ? "Salvando…" : "Salvar"}
          </Button>
        </>
      }
    >
      {document && (
        <form id="edit-document" onSubmit={save} className="space-y-4">
          <Field label="Título" htmlFor="doc-title">
            <Input id="doc-title" name="title" required maxLength={300} defaultValue={document.title} />
          </Field>
          <Field label="Categoria" htmlFor="doc-category" hint="Opcional">
            <Input id="doc-category" name="category" maxLength={120} defaultValue={document.category ?? ""} />
          </Field>
          <Field
            label="Visibilidade"
            htmlFor="doc-visibility"
            hint="Ao mudar, os trechos já publicados passam a valer na hora."
          >
            <Select id="doc-visibility" name="visibility" defaultValue={document.visibility}>
              <option value="public">Público (todos os usuários)</option>
              <option value="it">Só TI (técnicos e administradores)</option>
            </Select>
          </Field>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
        </form>
      )}
    </Modal>
  );
}
