import { describe, expect, it } from "vitest";

import { DEMO_SCENARIOS, demoEvents } from "./demo";
import {
  type AgentEvent,
  BUBBLE_MAX,
  bubbleText,
  isRoomKey,
  mergeEvents,
  ROOM_KEYS,
  sceneAt,
} from "./engine";

function event(room: string, action: string, order: number, summary = "passo"): AgentEvent {
  return {
    id: `id-${String(order).padStart(3, "0")}`,
    conversation_id: "c1",
    ticket_id: null,
    room,
    action,
    summary,
    agent_name: "Agente",
    metadata: {},
    created_at: new Date(Date.UTC(2026, 10, 6, 14, 0, order)).toISOString(),
  };
}

const FLOW = [
  event("recepcao", "mensagem_recebida", 0),
  event("triagem", "classificado", 1),
  event("rag", "rag_busca", 2),
  event("recepcao", "resposta_enviada", 3),
];

describe("sceneAt: transição entre salas", () => {
  it("antes do primeiro evento não há sala ativa", () => {
    const state = sceneAt(FLOW, -1);
    expect(state).toMatchObject({ index: -1, total: 4, active: null, previous: null, visited: [] });
    expect(state.bubble).toBeNull();
  });

  it("o primeiro evento acende a sala e ainda não marca nenhuma como percorrida", () => {
    expect(sceneAt(FLOW, 0)).toMatchObject({ active: "recepcao", previous: null, visited: [] });
  });

  it("ao mudar de sala, a anterior fica marcada e o chamado sai dela", () => {
    expect(sceneAt(FLOW, 1)).toMatchObject({
      active: "triagem",
      previous: "recepcao",
      visited: ["recepcao"],
    });
    expect(sceneAt(FLOW, 2)).toMatchObject({
      active: "rag",
      previous: "triagem",
      visited: ["recepcao", "triagem"],
    });
  });

  it("voltar a uma sala já visitada a tira da lista de percorridas", () => {
    const state = sceneAt(FLOW, 3);
    expect(state.active).toBe("recepcao");
    expect(state.previous).toBe("rag");
    expect(state.visited).toEqual(["triagem", "rag"]);
  });

  it("vários eventos seguidos na mesma sala não contam como mudança", () => {
    const flow = [event("rag", "rag_busca", 0), event("rag", "rag_busca", 1), event("banco", "sql_leitura", 2)];
    expect(sceneAt(flow, 1)).toMatchObject({ active: "rag", previous: null, visited: [] });
    expect(sceneAt(flow, 2)).toMatchObject({ active: "banco", previous: "rag", visited: ["rag"] });
  });

  it("índice maior que o roteiro vale o último evento; sala desconhecida fica só no log", () => {
    expect(sceneAt(FLOW, 99).index).toBe(3);
    const flow = [event("recepcao", "mensagem_recebida", 0), event("cozinha", "cafe", 1)];
    expect(sceneAt(flow, 1)).toMatchObject({ active: "recepcao", visited: [] });
  });
});

describe("bubbleText", () => {
  it("nunca passa de 22 caracteres para as ações conhecidas", () => {
    const actions = [
      "mensagem_recebida",
      "classificado",
      "triagem_manual",
      "rag_busca",
      "sql_leitura",
      "chamado_criado",
      "chamado_atribuido",
      "aguardando_triagem",
      "evento_registrado",
      "resposta_enviada",
    ];
    for (const action of actions) {
      const text = bubbleText({ action, summary: "x" });
      expect(text.length, action).toBeLessThanOrEqual(BUBBLE_MAX);
      expect(text, action).not.toBe("x");
    }
  });

  it("ação desconhecida usa o resumo, cortado em 22 com reticências", () => {
    const text = bubbleText({
      action: "outra",
      summary: "Um resumo bem longo que não cabe no balão do personagem",
    });
    expect(text.length).toBeLessThanOrEqual(BUBBLE_MAX);
    expect(text.endsWith("…")).toBe(true);
    expect(bubbleText({ action: "outra", summary: "curto" })).toBe("curto");
  });
});

describe("mergeEvents", () => {
  it("não repete pelo id e ordena pelo horário", () => {
    const merged = mergeEvents([FLOW[2]!, FLOW[0]!], [FLOW[0]!, FLOW[1]!]);
    expect(merged.map((e) => e.id)).toEqual(["id-000", "id-001", "id-002"]);
  });
});

describe("cenários da demonstração", () => {
  it("são os três pedidos, com eventos em ordem e só em salas conhecidas", () => {
    expect(DEMO_SCENARIOS.map((s) => s.id)).toEqual(["rag", "status", "escalonamento"]);
    for (const { id } of DEMO_SCENARIOS) {
      const events = demoEvents(id, new Date("2026-11-06T14:00:00Z"));
      expect(events.length, id).toBeGreaterThan(2);
      expect(events.every((e) => isRoomKey(e.room)), id).toBe(true);
      expect(new Set(events.map((e) => e.id)).size, id).toBe(events.length);
      const times = events.map((e) => e.created_at);
      expect([...times].sort(), id).toEqual(times);
    }
  });

  it("a dúvida resolvida passa pela base, e a consulta de status pelo banco, sem tocar em técnicos", () => {
    const rooms = (id: string) => demoEvents(id).map((e) => e.room);
    expect(rooms("rag")).toContain("rag");
    expect(rooms("rag")).not.toContain("tecnicos");
    expect(rooms("status")).toContain("banco");
    expect(rooms("status")).not.toContain("tecnicos");
  });

  it("o escalonamento percorre todas as seis salas e termina respondendo ao usuário", () => {
    const events = demoEvents("escalonamento");
    expect(new Set(events.map((e) => e.room))).toEqual(new Set(ROOM_KEYS));
    expect(events.at(-1)?.action).toBe("resposta_enviada");
    expect(sceneAt(events, events.length - 1).visited.length).toBe(5);
  });

  it("cenário desconhecido não gera eventos", () => {
    expect(demoEvents("nao-existe")).toEqual([]);
  });
});
