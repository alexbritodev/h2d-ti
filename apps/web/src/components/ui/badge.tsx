import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export type Tone = "neutral" | "accent" | "info" | "warn" | "danger";

const TONES: Record<Tone, string> = {
  neutral: "border-border bg-surface-2 text-muted",
  accent: "border-accent/30 bg-accent-soft text-accent",
  info: "border-info/30 bg-info/10 text-info",
  warn: "border-warn/30 bg-warn/10 text-warn",
  danger: "border-danger/30 bg-danger-soft text-danger",
};

const DOTS: Record<Tone, string> = {
  neutral: "bg-muted",
  accent: "bg-accent",
  info: "bg-info",
  warn: "bg-warn",
  danger: "bg-danger",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  dot?: boolean;
  mono?: boolean;
}

export function Badge({ tone = "neutral", dot, mono, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        mono && "font-mono",
        TONES[tone],
        className,
      )}
      {...props}
    >
      {dot && <span aria-hidden className={cn("size-1.5 rounded-full", DOTS[tone])} />}
      {children}
    </span>
  );
}

/** Conta itens em menus e botões. */
export function CountBadge({ count, className }: { count: number; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1.5 text-[11px] font-semibold text-white",
        className,
      )}
    >
      {count}
    </span>
  );
}
