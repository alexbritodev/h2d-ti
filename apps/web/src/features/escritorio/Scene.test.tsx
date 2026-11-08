import { act, cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { type AgentEvent, sceneAt } from "./engine";
import { mix, PALETTES } from "./palette";
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

afterEach(() => {
  cleanup();
  delete document.documentElement.dataset.theme;
});

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

describe("OfficeScene: tema claro e escuro", () => {
  const tileFill = (container: HTMLElement, room: string) =>
    container.querySelector(`[data-room="${room}"] polygon`)?.getAttribute("fill");

  it("sem tema definido usa o claro, que é o padrão do app", () => {
    const { getByTestId, container } = render(<OfficeScene state={sceneAt(FLOW, -1)} />);

    expect(getByTestId("office-scene").getAttribute("data-theme")).toBe("light");
    expect((getByTestId("office-scene") as unknown as SVGElement).style.background).not.toBe("");
    expect(tileFill(container, "recepcao")).toBe(PALETTES.light.tileA);
  });

  it("com data-theme=dark usa a paleta escura", () => {
    document.documentElement.dataset.theme = "dark";
    const { getByTestId, container } = render(<OfficeScene state={sceneAt(FLOW, -1)} />);

    expect(getByTestId("office-scene").getAttribute("data-theme")).toBe("dark");
    expect(tileFill(container, "recepcao")).toBe(PALETTES.dark.tileA);
  });

  it("trocar o tema redesenha a cena na hora, sem recarregar", async () => {
    const { getByTestId, container } = render(<OfficeScene state={sceneAt(FLOW, 0)} />);
    expect(getByTestId("office-scene").getAttribute("data-theme")).toBe("light");
    const light = tileFill(container, "recepcao");

    await act(async () => {
      document.documentElement.dataset.theme = "dark";
      await Promise.resolve();
    });

    expect(getByTestId("office-scene").getAttribute("data-theme")).toBe("dark");
    expect(tileFill(container, "recepcao")).not.toBe(light);
  });

  it("o piso da sala ativa mistura a cor da sala com branco no claro e com preto no escuro", () => {
    const light = render(<OfficeScene state={sceneAt(FLOW, 0)} />);
    const lightFill = tileFill(light.container, "recepcao");
    light.unmount();
    document.documentElement.dataset.theme = "dark";
    const dark = render(<OfficeScene state={sceneAt(FLOW, 0)} />);
    const darkFill = tileFill(dark.container, "recepcao");

    expect(lightFill).toBe(mix("#4F9CF0", "#ffffff", PALETTES.light.activeMix[1]));
    expect(darkFill).toBe(mix("#4F9CF0", "#000000", PALETTES.dark.activeMix[1]));
    expect(lightFill).not.toBe(darkFill);
  });

  it("mix devolve a própria cor com 100% e a base com 0%", () => {
    expect(mix("#4F9CF0", "#000000", 1)).toBe("rgb(79,156,240)");
    expect(mix("#4F9CF0", "#ffffff", 0)).toBe("rgb(255,255,255)");
  });
});
