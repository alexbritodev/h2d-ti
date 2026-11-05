import { CheckCircle2, X } from "lucide-react";
import { useSyncExternalStore } from "react";

interface ToastItem {
  id: number;
  title: string;
  detail?: string;
}

let toasts: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function publish(next: ToastItem[]) {
  toasts = next;
  listeners.forEach((listener) => listener());
}

function dismiss(id: number) {
  publish(toasts.filter((item) => item.id !== id));
}

export function toast(title: string, detail?: string) {
  const id = nextId++;
  publish([...toasts, { id, title, detail }]);
  setTimeout(() => dismiss(id), 4000);
}

/** Aviso padrão das telas que ainda não têm backend. */
export function demoToast(title: string) {
  toast(title, "Demonstração: nada foi salvo.");
}

export function Toaster() {
  const items = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => toasts,
  );

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed right-4 bottom-4 z-[60] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2"
    >
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-start gap-3 rounded-lg border border-border bg-surface p-3 shadow-card"
        >
          <CheckCircle2 aria-hidden className="mt-0.5 size-[18px] shrink-0 text-accent" />
          <div className="min-w-0 flex-1">
            <p className="font-medium">{item.title}</p>
            {item.detail && <p className="text-xs text-muted">{item.detail}</p>}
          </div>
          <button
            type="button"
            aria-label="Fechar aviso"
            onClick={() => dismiss(item.id)}
            className="cursor-pointer text-muted hover:text-text"
          >
            <X aria-hidden className="size-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
