import { Server } from "lucide-react";

import { cn } from "@/lib/utils";

export function Logo({
  className,
  subtitle,
  iconOnly,
}: {
  className?: string;
  subtitle?: boolean;
  iconOnly?: boolean;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span
        aria-hidden
        className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent text-sidebar"
      >
        <Server className="size-5" />
      </span>
      {iconOnly ? (
        <span className="sr-only">H2D TI</span>
      ) : (
        <span className="leading-tight">
          <span className="block text-base font-semibold">H2D TI</span>
          {subtitle && <span className="block text-xs opacity-80">Gestão de atendimento</span>}
        </span>
      )}
    </div>
  );
}
