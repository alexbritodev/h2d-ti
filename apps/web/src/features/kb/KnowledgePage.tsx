import { useQuery } from "@tanstack/react-query";
import { BookOpen, Lock, Search, ThumbsUp } from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, Drawer } from "@/components/ui/primitives";
import { Snippet } from "@/components/ui/snippet";
import { meQuery } from "@/lib/auth";
import { ARTICLES, type Article } from "@/lib/demo/data";
import { cn } from "@/lib/utils";

const ALL = "Todos";

export function KnowledgePage() {
  const { data: user } = useQuery(meQuery);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(ALL);
  const [opened, setOpened] = useState<Article | null>(null);

  // Quem é usuário comum não vê conteúdo restrito à TI. No backend, o filtro roda no SQL.
  const allowed = useMemo(
    () => ARTICLES.filter((article) => article.visibility === "public" || user?.role !== "user"),
    [user],
  );
  const categories = useMemo(() => [ALL, ...new Set(allowed.map((a) => a.category))], [allowed]);
  const articles = allowed.filter((article) => {
    const term = search.trim().toLowerCase();
    return (
      (category === ALL || article.category === category) &&
      (!term || `${article.title} ${article.excerpt}`.toLowerCase().includes(term))
    );
  });

  return (
    <section>
      <PageHeader
        title="Base de conhecimento"
        description="Consulte os manuais e procedimentos publicados pela TI."
      />

      <div className="relative mb-4">
        <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
        <Input
          aria-label="Buscar artigos"
          placeholder="Ex.: VPN, senha, impressora"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="pl-9"
        />
      </div>

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

      {articles.length === 0 ? (
        <Card className="py-14 text-center text-muted">Nenhum artigo encontrado.</Card>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {articles.map((article) => (
            <li key={article.id}>
              <button
                type="button"
                onClick={() => setOpened(article)}
                className="h-full w-full cursor-pointer rounded-xl border border-border bg-surface p-5 text-left shadow-card transition-colors hover:border-muted"
              >
                <div className="mb-3 flex items-center justify-between gap-2">
                  <span
                    aria-hidden
                    className="flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent"
                  >
                    <BookOpen className="size-[18px]" />
                  </span>
                  {article.visibility === "it" && (
                    <Badge tone="warn">
                      <Lock aria-hidden className="size-3" />
                      Só TI
                    </Badge>
                  )}
                </div>
                <h2 className="font-semibold">{article.title}</h2>
                <p className="mt-1 mb-3 text-muted">{article.excerpt}</p>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                  <Badge>{article.category}</Badge>
                  <span className="flex items-center gap-1">
                    <ThumbsUp aria-hidden className="size-3" />
                    {article.helpful}%
                  </span>
                  <span>Atualizado {article.updatedAt}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}

      <Drawer
        open={opened !== null}
        onOpenChange={(open) => !open && setOpened(null)}
        title={opened?.title ?? ""}
        description={opened?.excerpt}
      >
        {opened && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{opened.category}</Badge>
              <Badge tone={opened.visibility === "it" ? "warn" : "accent"}>
                {opened.visibility === "it" ? "Só TI" : "Público"}
              </Badge>
            </div>
            <ol className="list-decimal space-y-2 pl-5">
              {opened.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            {opened.snippet && <Snippet {...opened.snippet} />}
          </div>
        )}
      </Drawer>
    </section>
  );
}
