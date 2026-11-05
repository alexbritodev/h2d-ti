import { FlaskConical } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";

/** Título de página. O selo deixa claro que os dados da tela ainda não são reais. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <Badge tone="info">
            <FlaskConical aria-hidden className="size-3" />
            Dados de demonstração
          </Badge>
        </div>
        <p className="mt-1 text-muted">{description}</p>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
