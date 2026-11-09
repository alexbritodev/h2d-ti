import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Números do dia a dia do pipeline: valor grande, legenda pequena. */
export function Kpi({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="rounded-lg bg-surface-2 px-3 py-2">
      <div className="text-lg leading-tight font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}

export function KpiRow({ children }: { children: ReactNode }) {
  return <div className="mt-4 flex flex-wrap gap-2">{children}</div>;
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <h3 className="mb-2 text-xs font-medium tracking-wide text-muted uppercase">{children}</h3>;
}

/** Texto que o sistema montou (pergunta mascarada, consulta, prompt), em fonte de código. */
export function CodeBox({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <pre
      className={cn(
        "overflow-x-auto rounded-lg border border-border bg-surface-2 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap",
        className,
      )}
    >
      {children}
    </pre>
  );
}

export function Chip({
  children,
  tone = "neutral",
  title,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "struck" | "dim";
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-block rounded-md border px-1.5 py-0.5 font-mono text-xs",
        tone === "neutral" && "border-border bg-surface-2",
        tone === "accent" && "border-accent/40 bg-accent-soft text-text",
        tone === "struck" && "border-border text-muted line-through",
        tone === "dim" && "border-dashed border-border text-muted opacity-60",
      )}
    >
      {children}
    </span>
  );
}

function delay(seconds: number): CSSProperties {
  return { "--delay": `${seconds}s` } as CSSProperties;
}

const COLUMNS = 48;

/**
 * Cada célula é uma dimensão do vetor: verde para valor positivo, cinza para negativo, e a
 * intensidade acompanha o módulo. A raiz do módulo evita que poucos picos apaguem o resto.
 */
export function HeatStrip({ values, label }: { values: number[]; label: string }) {
  const peak = values.reduce((max, value) => Math.max(max, Math.abs(value)), 1e-9);
  return (
    <div
      role="img"
      aria-label={label}
      className="grid gap-px"
      style={{ gridTemplateColumns: `repeat(${COLUMNS}, minmax(0, 1fr))` }}
    >
      {values.map((value, index) => {
        const strength = Math.round(10 + 90 * Math.sqrt(Math.abs(value) / peak));
        const base = value >= 0 ? "var(--accent)" : "var(--muted)";
        return (
          <span
            key={index}
            title={`dimensão ${index}: ${value}`}
            className="chart-fade h-3 rounded-[1px]"
            style={{
              ...delay((index % COLUMNS) * 0.01),
              background: `color-mix(in srgb, ${base} ${strength}%, transparent)`,
            }}
          />
        );
      })}
    </div>
  );
}

/** Barra de uma ou duas partes (ex.: contribuição vetorial e por palavras na fusão). */
export function ScoreBar({
  parts,
  label,
}: {
  parts: { value: number; className: string }[];
  label: string;
}) {
  return (
    <div role="img" aria-label={label} className="flex h-2 w-full overflow-hidden rounded-full bg-surface-2">
      {parts.map((part, index) => (
        <div
          key={index}
          className={cn("chart-bar-h h-full", part.className)}
          style={{ width: `${Math.min(100, Math.max(0, part.value))}%` }}
        />
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { className: string; label: string }[] }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span aria-hidden className={cn("size-2 rounded-full", item.className)} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export const formatNumber = (value: number, digits = 2) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
