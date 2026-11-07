import type { components } from "@/lib/api/schema";

export type AgentEvent = components["schemas"]["AgentEventOut"];
export type Atendimento = components["schemas"]["AtendimentoOut"];

export const ROOM_KEYS = ["recepcao", "triagem", "rag", "banco", "tecnicos", "auditoria"] as const;
export type RoomKey = (typeof ROOM_KEYS)[number];

export interface RoomInfo {
  key: RoomKey;
  name: string;
  /** Quem trabalha na sala (aparece no log e na descrição acessível). */
  agent: string;
  color: string;
}

export const ROOMS: readonly RoomInfo[] = [
  { key: "recepcao", name: "Recepção", agent: "Chatbot", color: "#4F9CF0" },
  { key: "triagem", name: "Triagem", agent: "Classificador", color: "#E8A33D" },
  { key: "rag", name: "Base de conhecimento", agent: "Busca RAG", color: "#2FB58A" },
  { key: "banco", name: "Banco de dados", agent: "Consulta ao banco", color: "#8B7FE8" },
  { key: "tecnicos", name: "Técnicos de TI", agent: "Roteador", color: "#EC6B3A" },
  { key: "auditoria", name: "Auditoria", agent: "Auditor", color: "#B5B5AE" },
];

export const ROOM_BY_KEY = Object.fromEntries(ROOMS.map((room) => [room.key, room])) as Record<
  RoomKey,
  RoomInfo
>;

export function isRoomKey(value: string): value is RoomKey {
  return (ROOM_KEYS as readonly string[]).includes(value);
}

export const BUBBLE_MAX = 22;

const BUBBLES: Record<string, string> = {
  mensagem_recebida: "Recebendo mensagem",
  classificado: "Classificando...",
  triagem_manual: "Triagem manual",
  rag_busca: "Buscando na base",
  sql_leitura: "Consultando banco",
  chamado_criado: "Chamado criado",
  chamado_atribuido: "Atribuindo técnico",
  aguardando_triagem: "Aguardando triagem",
  evento_registrado: "Registrando",
  resposta_enviada: "Resposta enviada",
};

function truncate(text: string, max: number): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length <= max ? clean : `${clean.slice(0, max - 1).trimEnd()}…`;
}

/** Texto curto do balão (até 22 caracteres): ação conhecida ou o começo do resumo. */
export function bubbleText(event: Pick<AgentEvent, "action" | "summary">): string {
  return truncate(BUBBLES[event.action] ?? event.summary, BUBBLE_MAX);
}

export interface SceneState {
  /** Posição no roteiro: -1 antes do primeiro evento. */
  index: number;
  total: number;
  active: RoomKey | null;
  /** Sala anterior à ativa, de onde o ícone do chamado sai. */
  previous: RoomKey | null;
  /** Salas já percorridas, sem repetir e sem a ativa. */
  visited: RoomKey[];
  bubble: string | null;
  event: AgentEvent | null;
}

/** O que a cena mostra depois de `index` eventos. Função pura: replay, ao vivo e demo a usam. */
export function sceneAt(events: readonly AgentEvent[], index: number): SceneState {
  const last = Math.min(index, events.length - 1);
  const trail: RoomKey[] = [];
  let current: AgentEvent | null = null;
  for (let i = 0; i <= last; i += 1) {
    const event = events[i]!;
    if (!isRoomKey(event.room)) continue; // sala que a cena não conhece: fica só no log
    if (trail[trail.length - 1] !== event.room) trail.push(event.room);
    current = event;
  }
  const active = current && isRoomKey(current.room) ? current.room : null;
  const before = active ? trail.slice(0, -1) : trail;
  return {
    index: Math.max(last, -1),
    total: events.length,
    active,
    previous: before[before.length - 1] ?? null,
    visited: [...new Set(before)].filter((room) => room !== active),
    bubble: current ? bubbleText(current) : null,
    event: current,
  };
}

export function formatClock(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString("pt-BR", { hour12: false });
}

/** Chave estável de um atendimento: a conversa e, sem ela, o chamado. */
export function attendanceKey(event: Pick<AgentEvent, "conversation_id" | "ticket_id">) {
  return event.conversation_id ?? event.ticket_id ?? null;
}

/** Junta listas de eventos sem repetir (pelo id) e na ordem em que aconteceram. */
export function mergeEvents(...lists: readonly (readonly AgentEvent[])[]): AgentEvent[] {
  const byId = new Map<string, AgentEvent>();
  for (const list of lists) for (const event of list) byId.set(event.id, event);
  return [...byId.values()].sort(
    (a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id),
  );
}
