import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { type AgentEvent, sceneAt } from "./engine";
import { OfficeScene } from "./Scene";

function event(room: string, action: string, order: number): AgentEvent {
  return {
    id: `id-${order}`,
    conversation_id: "c1",
    ticket_id: null,
    room,
    action,
    summary: "passo",
    agent_name: "Agente",
    metadata: {},
    created_at: new Date(Date.UTC(2026, 10, 6, 14, 0, order)).toISOString(),
  };
}

const FLOW = [
  event("recepcao", "mensagem_recebida", 0),
  event("triagem", "classificado", 1),
  event("rag", "rag_busca", 2),
];

afterEach(cleanup);

const statusOf = (container: HTMLElement, room: string) =>
  container.querySelector(`[data-room="${room}"]`)?.getAttribute("data-status");

describe("OfficeScene: transição de salas", () => {
  it("sem eventos nenhuma sala está ativa", () => {
    const { getByTestId, container } = render(<OfficeScene state={sceneAt(FLOW, -1)} />);
    expect(getByTestId("office-scene").getAttribute("data-active-room")).toBe("");
    expect(getByTestId("office-scene").getAttribute("aria-label")).toContain("Nenhum passo");
    expect(statusOf(container, "recepcao")).toBe("idle");
  });

  it("acende a sala do evento e marca as já percorridas a cada passo", () => {
    const { getByTestId, container, rerender, getByText } = render(
      <OfficeScene state={sceneAt(FLOW, 0)} />,
    );
    expect(getByTestId("office-scene").getAttribute("data-active-room")).toBe("recepcao");
    expect(statusOf(container, "recepcao")).toBe("active");
    expect(getByText("Recebendo mensagem")).toBeTruthy();

    rerender(<OfficeScene state={sceneAt(FLOW, 1)} />);
    expect(getByTestId("office-scene").getAttribute("data-active-room")).toBe("triagem");
    expect(statusOf(container, "triagem")).toBe("active");
    expect(statusOf(container, "recepcao")).toBe("visited");
    expect(statusOf(container, "rag")).toBe("idle");
    expect(getByText("Classificando...")).toBeTruthy();
    expect(getByTestId("office-scene").getAttribute("aria-label")).toContain(
      "Sala ativa: Triagem",
    );

    rerender(<OfficeScene state={sceneAt(FLOW, 2)} />);
    expect(statusOf(container, "rag")).toBe("active");
    expect(statusOf(container, "triagem")).toBe("visited");
    expect(statusOf(container, "recepcao")).toBe("visited");
    // Só uma sala fica ativa por vez.
    expect(container.querySelectorAll('[data-status="active"]').length).toBe(1);
  });

  it("desenha as seis salas", () => {
    const { container } = render(<OfficeScene state={sceneAt(FLOW, 0)} />);
    expect(container.querySelectorAll("[data-room]").length).toBe(6);
  });
});
