import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

import { type AgentEvent, formatClock, isRoomKey, ROOM_BY_KEY } from "./engine";

/** Registro dos eventos já exibidos na cena. A última linha fica em destaque. */
export function LogPanel({ events }: { events: readonly AgentEvent[] }) {
  const lastRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    lastRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [events.length]);

  return (
    <div className="rounded-xl border border-border bg-surface shadow-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2 text-xs text-muted">
        <span className="font-medium text-text">Registro</span>
        <span>{events.length} evento(s)</span>
      </div>
      <ol
        role="log"
        aria-live="polite"
        aria-label="Registro de eventos do atendimento"
        className="max-h-56 min-h-32 overflow-y-auto p-2 font-mono text-xs leading-6"
      >
        {events.length === 0 && <li className="px-2 py-1 text-muted">Aguardando eventos…</li>}
        {events.map((event, index) => {
          const last = index === events.length - 1;
          return (
            <li
              key={event.id}
              ref={last ? lastRef : undefined}
              aria-current={last ? "step" : undefined}
              className={cn(
                "flex gap-3 rounded px-2",
                last ? "bg-accent-soft font-medium text-text" : "text-muted",
              )}
            >
              <time dateTime={event.created_at} className="shrink-0">
                {formatClock(event.created_at)}
              </time>
              <span className="w-24 shrink-0 truncate sm:w-36">
                {isRoomKey(event.room) ? ROOM_BY_KEY[event.room].name : event.room}
              </span>
              <span className="min-w-0 flex-1 break-words">{event.summary}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
