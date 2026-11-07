import { useEffect, useRef, useState } from "react";

import type { AgentEvent } from "./engine";

/** Tempo que cada passo fica na cena, na velocidade 1x. */
export const DWELL_MS = 1100;
const FAST_DWELL_MS = 250;
export const SPEEDS = [0.5, 1, 2] as const;

export interface Timeline {
  index: number;
  playing: boolean;
  speed: number;
  finished: boolean;
  toggle: () => void;
  stepForward: () => void;
  stepBack: () => void;
  restart: () => void;
  setSpeed: (speed: number) => void;
}

/**
 * Posição da animação no roteiro de eventos. Serve ao replay, à demo e ao ao vivo:
 * - replay e demo: começam no início e tocam;
 * - ao vivo: ao abrir um atendimento mostra o último passo e depois acompanha os novos,
 *   um de cada vez (com muitos pendentes, acelera para não ficar para trás).
 */
export function useTimeline(total: number, resetKey: string, live: boolean): Timeline {
  const [index, setIndex] = useState(-1);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const jumpToEnd = useRef(live);

  useEffect(() => {
    setIndex(-1);
    setPlaying(true);
    jumpToEnd.current = live;
  }, [resetKey, live]);

  useEffect(() => {
    if (jumpToEnd.current && total > 0) {
      jumpToEnd.current = false;
      setIndex(total - 1);
    }
  }, [total, resetKey]);

  useEffect(() => {
    if (!playing || index >= total - 1) return;
    const backlog = total - 1 - index;
    const dwell = (backlog > 3 ? FAST_DWELL_MS : DWELL_MS) / speed;
    const timer = setTimeout(() => setIndex((i) => Math.min(i + 1, total - 1)), dwell);
    return () => clearTimeout(timer);
  }, [playing, index, total, speed]);

  const finished = total > 0 && index >= total - 1;
  return {
    index: Math.min(index, total - 1),
    playing,
    speed,
    finished,
    toggle: () => {
      if (finished && !live) {
        setIndex(-1);
        setPlaying(true);
      } else {
        setPlaying((p) => !p);
      }
    },
    stepForward: () => {
      setPlaying(false);
      setIndex((i) => Math.min(i + 1, total - 1));
    },
    stepBack: () => {
      setPlaying(false);
      setIndex((i) => Math.max(i - 1, -1));
    },
    restart: () => {
      setIndex(-1);
      setPlaying(true);
    },
    setSpeed,
  };
}

export type Connection = "connecting" | "open" | "reconnecting" | "unsupported";

const STREAM_URL = "/api/escritorio/stream";

/**
 * Eventos ao vivo por SSE. Se a conexão cair (rede, deploy, fim dos 5 min do servidor),
 * reconecta sozinho com espera crescente e retoma de onde parou, sem repetir eventos.
 */
export function useEventStream(enabled: boolean, onEvent: (event: AgentEvent) => void): Connection {
  const [status, setStatus] = useState<Connection>("connecting");
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (!enabled) return;
    if (typeof EventSource === "undefined") {
      setStatus("unsupported");
      return;
    }
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let closed = false;
    let cursor = new Date().toISOString();
    setStatus("connecting");

    const connect = () => {
      source = new EventSource(`${STREAM_URL}?after=${encodeURIComponent(cursor)}`);
      source.onopen = () => {
        attempt = 0;
        setStatus("open");
      };
      source.addEventListener("agent_event", (message) => {
        try {
          const event = JSON.parse((message as MessageEvent<string>).data) as AgentEvent;
          if (event.created_at > cursor) cursor = event.created_at;
          handler.current(event);
        } catch {
          // Mensagem malformada: ignora, o próximo evento segue normalmente.
        }
      });
      source.onerror = () => {
        source?.close();
        if (closed) return;
        setStatus("reconnecting");
        timer = setTimeout(connect, Math.min(500 * 2 ** attempt, 15_000));
        attempt += 1;
      };
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      source?.close();
    };
  }, [enabled]);

  return status;
}
