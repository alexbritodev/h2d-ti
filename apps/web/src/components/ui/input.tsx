import type { InputHTMLAttributes, Ref } from "react";

import { cn } from "@/lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  ref?: Ref<HTMLInputElement>;
}

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-text transition-colors placeholder:text-muted hover:border-muted aria-invalid:border-danger",
        className,
      )}
      {...props}
    />
  );
}
