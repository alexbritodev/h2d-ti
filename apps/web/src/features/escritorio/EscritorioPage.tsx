import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Radio, WifiOff } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, Skeleton, Switch, Tabs } from "@/components/ui/primitives";

import {
  atendimentosQuery,
  escritorioConfigQuery,
  eventosQuery,
  type AttendanceRef,
} from "./api";
import { Controls } from "./Controls";
import { DEMO_SCENARIOS, demoEvents } from "./demo";
import {
  type AgentEvent,
  type Atendimento,
  attendanceKey,
  formatClock,
  mergeEvents,
  sceneAt,
} from "./engine";
import { useEventStream, useTimeline, type Timeline } from "./hooks";
import { LogPanel } from "./LogPanel";
import { useMiniMode } from "./mini";
import { OfficeScene } from "./Scene";

type Mode = "live" | "replay" | "demo";

function Notice({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-surface px-6 py-12 text-center shadow-card">
      <p className="font-medium">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-md text-muted">{children}</div>}
    </div>
  );
}

function refOf(attendance: Atendimento | undefined): AttendanceRef | null {
  return attendance
    ? { conversationId: attendance.conversation_id, ticketId: attendance.ticket_id }
    : null;
}

function labelOf(attendance: Atendimento): string {
  const name = attendance.ticket_code ?? `Conversa ${attendance.key.slice(0, 8)}`;
  return `${attendance.active ? "● " : ""}${name} · ${formatClock(attendance.last_at)}`;
}

function AttendanceSelect({
  attendances,
  value,
  onChange,
}: {
  attendances: readonly Atendimento[];
  value: string | null;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="escritorio-atendimento" className="text-sm font-medium">
        Atendimento
      </label>
      <Select
        id="escritorio-atendimento"
        className="w-full sm:w-96"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      >
        {attendances.map((attendance) => (
          <option key={attendance.key} value={attendance.key}>
            {labelOf(attendance)}
          </option>
        ))}
      </Select>
    </div>
  );
}

/** A cena, os controles (no replay e na demo) e o log, todos guiados pela mesma linha do tempo. */
function Stage({
  events,
  timeline,
  withControls,
}: {
  events: readonly AgentEvent[];
  timeline: Timeline;
  withControls: boolean;
}) {
  const state = useMemo(() => sceneAt(events, timeline.index), [events, timeline.index]);
  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-xl border border-border shadow-card">
        <OfficeScene state={state} />
      </div>
      {withControls && <Controls timeline={timeline} total={events.length} />}
      <LogPanel events={events.slice(0, Math.max(timeline.index + 1, 0))} />
    </div>
  );
}

function ConnectionBadge({ status }: { status: ReturnType<typeof useEventStream> }) {
  if (status === "open") {
    return (
      <Badge tone="accent" dot>
        <Radio aria-hidden className="size-3" /> Ao vivo
      </Badge>
    );
  }
  if (status === "unsupported") {
    return <Badge tone="warn">Tempo real indisponível neste navegador</Badge>;
  }
  return (
    <Badge tone="warn" role="status">
      <WifiOff aria-hidden className="size-3" />
      {status === "connecting" ? "Conectando…" : "Conexão perdida. Reconectando…"}
    </Badge>
  );
}

function LiveView() {
  const queryClient = useQueryClient();
  const list = useQuery(atendimentosQuery(true));
  const [selected, setSelected] = useState<string | null>(null);
  const [pushed, setPushed] = useState<Record<string, AgentEvent[]>>({});

  const connection = useEventStream(true, (event) => {
    const key = attendanceKey(event);
    if (!key) return;
    setPushed((previous) => ({ ...previous, [key]: mergeEvents(previous[key] ?? [], [event]) }));
    void queryClient.invalidateQueries({ queryKey: ["escritorio", "atendimentos"] });
  });

  const attendances = list.data ?? [];
  // Sem escolha, acompanha o atendimento mais recente. Quem escolhe um, fica nele.
  const current = selected ?? attendances[0]?.key ?? null;
  const attendance = attendances.find((item) => item.key === current);
  const history = useQuery(eventosQuery(refOf(attendance)));
  const events = useMemo(
    () => mergeEvents(history.data ?? [], current ? (pushed[current] ?? []) : []),
    [history.data, pushed, current],
  );
  const timeline = useTimeline(events.length, current ?? "nenhum", true);

  let body: ReactNode;
  if (list.isPending) {
    body = <Skeleton className="h-96 w-full rounded-xl" />;
  } else if (list.isError) {
    body = (
      <Notice title="Não foi possível carregar os atendimentos">
        <Button variant="primary" onClick={() => void list.refetch()} className="mt-3">
          Tentar de novo
        </Button>
      </Notice>
    );
  } else if (attendances.length === 0) {
    body = (
      <Notice title="Nenhum chamado em andamento">
        Quando alguém falar com o assistente ou abrir um chamado, o atendimento aparece aqui.
      </Notice>
    );
  } else {
    body = <Stage events={events} timeline={timeline} withControls={false} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {attendances.length > 0 ? (
          <AttendanceSelect attendances={attendances} value={current} onChange={setSelected} />
        ) : (
          <span />
        )}
        <ConnectionBadge status={connection} />
      </div>
      {body}
    </div>
  );
}

function ReplayView() {
  const list = useQuery(atendimentosQuery(false));
  const [selected, setSelected] = useState<string | null>(null);
  const attendances = list.data ?? [];
  const current = selected ?? attendances[0]?.key ?? null;
  const attendance = attendances.find((item) => item.key === current);
  const history = useQuery(eventosQuery(refOf(attendance)));
  const events = history.data ?? [];
  const timeline = useTimeline(events.length, current ?? "nenhum", false);

  if (list.isPending) return <Skeleton className="h-96 w-full rounded-xl" />;
  if (list.isError) {
    return (
      <Notice title="Não foi possível carregar os atendimentos">
        <Button variant="primary" onClick={() => void list.refetch()} className="mt-3">
          Tentar de novo
        </Button>
      </Notice>
    );
  }
  if (attendances.length === 0) {
    return (
      <Notice title="Nenhum atendimento para reproduzir">
        Os atendimentos dos últimos 3 dias aparecem aqui.
      </Notice>
    );
  }
  return (
    <div className="space-y-4">
      <AttendanceSelect attendances={attendances} value={current} onChange={setSelected} />
      {history.isPending ? (
        <Skeleton className="h-96 w-full rounded-xl" />
      ) : (
        <Stage events={events} timeline={timeline} withControls />
      )}
    </div>
  );
}

function DemoView() {
  const [scenarioId, setScenarioId] = useState(DEMO_SCENARIOS[0]!.id);
  const events = useMemo(() => demoEvents(scenarioId), [scenarioId]);
  const timeline = useTimeline(events.length, scenarioId, false);
  const scenario = DEMO_SCENARIOS.find((item) => item.id === scenarioId)!;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {DEMO_SCENARIOS.map((item) => (
          <Button
            key={item.id}
            variant={item.id === scenarioId ? "primary" : "ghost"}
            aria-pressed={item.id === scenarioId}
            onClick={() => setScenarioId(item.id)}
            className="border border-border"
          >
            {item.title}
          </Button>
        ))}
      </div>
      <p className="text-muted">
        {scenario.description} <Badge tone="info">demonstração, nada é gravado</Badge>
      </p>
      <Stage events={events} timeline={timeline} withControls />
    </div>
  );
}

export function EscritorioPage() {
  const config = useQuery(escritorioConfigQuery);
  const [mode, setMode] = useState<Mode>("live");
  const [mini, setMini] = useMiniMode();
  const tabs = [
    { value: "live", label: "Ao vivo" },
    { value: "replay", label: "Replay" },
    ...(config.data?.demo ? [{ value: "demo", label: "Demonstração" }] : []),
  ];
  return (
    <>
      <PageHeader
        title="Escritório virtual"
        description="Veja os agentes do sistema trabalhando, sala por sala, em cada atendimento."
        actions={
          <div className="flex items-center gap-2 text-sm text-muted">
            <span aria-hidden>Mini-escritório nas outras telas</span>
            <Switch
              label="Mostrar o mini-escritório nas outras telas"
              checked={mini !== "off"}
              onCheckedChange={(on) => setMini(on ? "open" : "off")}
            />
          </div>
        }
      />
      <Tabs label="Modo de exibição" tabs={tabs} value={mode} onValueChange={(v) => setMode(v as Mode)} />
      <div className="pt-4">
        {mode === "live" && <LiveView />}
        {mode === "replay" && <ReplayView />}
        {mode === "demo" && <DemoView />}
      </div>
    </>
  );
}
