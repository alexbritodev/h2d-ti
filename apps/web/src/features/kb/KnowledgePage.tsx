import { useQuery } from "@tanstack/react-query";
import { BookOpen, Lock, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/Markdown";
import { Card, Drawer } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

import { libraryDocumentQuery, libraryQuery, searchQuery } from "./api";

const ALL = "Todos";
const NO_CATEGORY = "Sem categoria";

/** Espera a pessoa parar de digitar antes de buscar. */
function useDebounced(value: string, ms = 400) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

export function KnowledgePage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(ALL);
  const [openedId, setOpenedId] = useState<string | null>(null);

  const term = useDebounced(search.trim());
  const searching = term.length >= 2;

  // O servidor já devolve só o que a pessoa pode ver: usuário comum nunca recebe conteúdo da TI.
  const library = useQuery(libraryQuery);
  const results = useQuery({ ...searchQuery(term), enabled: searching });
  const opened = useQuery({ ...libraryDocumentQuery(openedId ?? ""), enabled: openedId !== null });

  const items = library.data ?? [];
  const categories = useMemo(
    () => [ALL, ...new Set(items.map((item) => item.category ?? NO_CATEGORY))],
    [items],
  );
  const visible = items.filter((item) => category === ALL || (item.category ?? NO_CATEGORY) === category);

  return (
    <section>
      <PageHeader
        live
        title="Base de conhecimento"
        description="Consulte os manuais e procedimentos publicados pela TI."
      />

      <div className="relative mb-4">
        <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
        <Input
          aria-label="Buscar na base"
          placeholder="Ex.: VPN, senha, impressora"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="pl-9"
        />
      </div>

      {searching ? (
        <SearchResults
          loading={results.isFetching}
          error={results.isError}
          hits={results.data ?? []}
          onOpen={setOpenedId}
        />
      ) : (
        <>
          <div role="group" aria-label="Filtrar por categoria" className="mb-5 flex flex-wrap gap-2">
            {categories.map((name) => (
              <button
                key={name}
                type="button"
                aria-pressed={category === name}
                onClick={() => setCategory(name)}
                className={cn(
                  "h-8 cursor-pointer rounded-full border px-3 text-sm transition-colors",
                  category === name
                    ? "border-accent bg-accent-soft font-medium"
                    : "border-border bg-surface text-muted hover:text-text",
                )}
              >
                {name}
              </button>
            ))}
          </div>

          {library.isPending ? (
            <p className="text-muted">Carregando…</p>
          ) : library.isError ? (
            <p role="alert" className="text-danger">
              Não foi possível carregar a base.
            </p>
          ) : visible.length === 0 ? (
            <Card className="py-14 text-center text-muted">
              {items.length === 0 ? "Ainda não há documentos publicados." : "Nenhum documento nesta categoria."}
            </Card>
          ) : (
            <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visible.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setOpenedId(item.id)}
                    className="h-full w-full cursor-pointer rounded-xl border border-border bg-surface p-5 text-left shadow-card transition-colors hover:border-muted"
                  >
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <span aria-hidden className="flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent">
                        <BookOpen className="size-[18px]" />
                      </span>
                      {item.visibility === "it" && (
                        <Badge tone="warn">
                          <Lock aria-hidden className="size-3" />
                          Só TI
                        </Badge>
                      )}
                    </div>
                    <h2 className="mb-3 font-semibold">{item.title}</h2>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                      <Badge>{item.category ?? NO_CATEGORY}</Badge>
                      {item.published_at && (
                        <span>Publicado em {new Date(item.published_at).toLocaleDateString("pt-BR")}</span>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <Drawer
        open={openedId !== null}
        onOpenChange={(open) => !open && setOpenedId(null)}
        title={opened.data?.title ?? "Documento"}
        description={opened.data?.category ?? undefined}
      >
        {opened.isPending && openedId !== null && <p className="text-muted">Carregando…</p>}
        {opened.isError && (
          <p role="alert" className="text-danger">
            Não foi possível abrir este documento.
          </p>
        )}
        {opened.data && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={opened.data.visibility === "it" ? "warn" : "accent"}>
                {opened.data.visibility === "it" ? "Só TI" : "Público"}
              </Badge>
            </div>
            {opened.data.sections.map((section, index) => (
              <div key={index}>
                <h3 className="mb-1 text-xs font-medium text-muted">{section.breadcrumb}</h3>
                <Markdown>{section.content}</Markdown>
              </div>
            ))}
          </div>
        )}
      </Drawer>
    </section>
  );
}

function SearchResults({
  loading,
  error,
  hits,
  onOpen,
}: {
  loading: boolean;
  error: boolean;
  hits: { chunk_id: string; document_id: string; document_title: string; breadcrumb: string; content: string }[];
  onOpen: (documentId: string) => void;
}) {
  if (error)
    return (
      <p role="alert" className="text-danger">
        Não foi possível buscar agora.
      </p>
    );
  if (loading && hits.length === 0) return <p className="text-muted">Buscando…</p>;
  if (hits.length === 0)
    return <Card className="py-14 text-center text-muted">Não encontrei nada na base sobre isso.</Card>;
  return (
    <ul className="space-y-3">
      {hits.map((hit) => (
        <li key={hit.chunk_id}>
          <button
            type="button"
            onClick={() => onOpen(hit.document_id)}
            className="w-full cursor-pointer rounded-xl border border-border bg-surface p-4 text-left shadow-card transition-colors hover:border-muted"
          >
            <p className="mb-1 text-xs font-medium text-muted">{hit.breadcrumb}</p>
            <Markdown>{hit.content}</Markdown>
          </button>
        </li>
      ))}
    </ul>
  );
}
