import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

/** Bloco de comando ou código copiável, para soluções, manuais e auditoria. */
export function Snippet({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
  }

  return (
    <figure className="overflow-hidden rounded-lg border border-border bg-sidebar text-sidebar-text">
      <figcaption className="flex items-center justify-between border-b border-white/10 py-1 pr-1 pl-3 text-xs text-sidebar-muted">
        <span className="font-mono">{language ?? "texto"}</span>
        <button
          type="button"
          onClick={copy}
          className="flex h-7 cursor-pointer items-center gap-1.5 rounded-md px-2 hover:bg-sidebar-hover hover:text-white"
        >
          {copied ? (
            <Check aria-hidden className="size-3.5 text-sidebar-accent" />
          ) : (
            <Copy aria-hidden className="size-3.5" />
          )}
          {copied ? "Copiado" : "Copiar"}
        </button>
      </figcaption>
      <pre className="overflow-x-auto p-3 font-mono text-xs leading-relaxed">
        <code>{code}</code>
      </pre>
    </figure>
  );
}
