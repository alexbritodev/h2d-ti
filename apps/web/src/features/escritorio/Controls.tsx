import { Pause, Play, RotateCcw, SkipBack, SkipForward } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { SPEEDS, type Timeline } from "./hooks";

/** Reproduzir, pausar, passo a passo e velocidade (replay e demonstração). */
export function Controls({ timeline, total }: { timeline: Timeline; total: number }) {
  const PlayIcon = timeline.playing && !timeline.finished ? Pause : Play;
  const playLabel = timeline.finished
    ? "Reproduzir de novo"
    : timeline.playing
      ? "Pausar"
      : "Reproduzir";
  return (
    <div
      role="group"
      aria-label="Controles do replay"
      className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface p-2 shadow-card"
    >
      <Button
        aria-label="Passo anterior"
        title="Passo anterior"
        onClick={timeline.stepBack}
        disabled={total === 0 || timeline.index < 0}
        className="size-10 px-0"
      >
        <SkipBack aria-hidden className="size-4" />
      </Button>
      <Button
        variant="primary"
        aria-label={playLabel}
        title={playLabel}
        onClick={timeline.toggle}
        disabled={total === 0}
        className="size-10 px-0"
      >
        <PlayIcon aria-hidden className="size-4" />
      </Button>
      <Button
        aria-label="Próximo passo"
        title="Próximo passo"
        onClick={timeline.stepForward}
        disabled={total === 0 || timeline.finished}
        className="size-10 px-0"
      >
        <SkipForward aria-hidden className="size-4" />
      </Button>
      <Button
        aria-label="Reiniciar"
        title="Reiniciar"
        onClick={timeline.restart}
        disabled={total === 0}
        className="size-10 px-0"
      >
        <RotateCcw aria-hidden className="size-4" />
      </Button>
      <div role="group" aria-label="Velocidade" className="ml-1 flex items-center gap-1">
        <span className="mr-1 text-xs text-muted">Velocidade</span>
        {SPEEDS.map((speed) => (
          <button
            key={speed}
            type="button"
            aria-pressed={timeline.speed === speed}
            onClick={() => timeline.setSpeed(speed)}
            className={cn(
              "h-8 cursor-pointer rounded-md px-2 text-xs font-medium",
              timeline.speed === speed
                ? "bg-accent text-accent-fg"
                : "text-muted hover:bg-surface-2 hover:text-text",
            )}
          >
            {String(speed).replace(".", ",")}x
          </button>
        ))}
      </div>
      <span className="ml-auto font-mono text-xs text-muted" aria-live="off">
        passo {Math.max(timeline.index + 1, 0)} de {total}
      </span>
    </div>
  );
}
