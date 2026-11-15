import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AgentProgressPanel } from "./AgentProgressPanel";
import type { AgentProgressEvent } from "./api";

afterEach(cleanup);

describe("AgentProgressPanel", () => {
  it("não renderiza nada se não houver eventos e não estiver em streaming", () => {
    const { container } = render(<AgentProgressPanel events={[]} isStreaming={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("renderiza as 4 etapas da timeline durante o streaming", () => {
    const events: AgentProgressEvent[] = [
      {
        agente: "guardiao",
        status: "aprovado",
        mensagem: "Mensagem aprovada pelo Guardião de Entrada.",
        timestamp: "2026-11-15T18:00:00Z",
      },
      {
        agente: "rag",
        status: "em_andamento",
        mensagem: "Buscando nos manuais de instrução...",
        timestamp: "2026-11-15T18:00:01Z",
      },
    ];

    render(<AgentProgressPanel events={events} isStreaming={true} />);

    expect(screen.getByText("Pipeline de Agentes")).toBeTruthy();
    expect(screen.getByText("Guardião de Entrada")).toBeTruthy();
    expect(screen.getByText("Busca nos Manuais")).toBeTruthy();
    expect(screen.getByText("Geração da Resposta")).toBeTruthy();
    expect(screen.getByText("Validador de Resposta")).toBeTruthy();

    expect(screen.getByText("Aprovado")).toBeTruthy();
    expect(screen.getByText("Em andamento")).toBeTruthy();
    expect(screen.getByText("Buscando nos manuais de instrução...")).toBeTruthy();
  });

  it("exibe alerta destacado com motivo quando o validador ou guardião reprova", () => {
    const events: AgentProgressEvent[] = [
      {
        agente: "guardiao",
        status: "aprovado",
        mensagem: "Aprovado.",
        timestamp: "2026-11-15T18:00:00Z",
      },
      {
        agente: "rag",
        status: "aprovado",
        mensagem: "2 trechos encontrados.",
        timestamp: "2026-11-15T18:00:01Z",
      },
      {
        agente: "llm",
        status: "aprovado",
        mensagem: "Resposta gerada.",
        timestamp: "2026-11-15T18:00:02Z",
      },
      {
        agente: "validador",
        status: "reprovado",
        mensagem: "Afirmações sem respaldo encontradas.",
        detalhes: {
          confianca: 0.25,
          motivo: "Comando inventado não presente no manual.",
          afirmacoes_sem_respaldo: ["rm -rf /etc/fake"],
        },
        timestamp: "2026-11-15T18:00:03Z",
      },
    ];

    render(<AgentProgressPanel events={events} isStreaming={false} />);

    expect(screen.getByText("Reprovado")).toBeTruthy();
    expect(screen.getByText(/Comando inventado não presente no manual/)).toBeTruthy();

    // Expande os detalhes técnicos
    const toggleBtn = screen.getByText("Ver detalhes técnicos");
    fireEvent.click(toggleBtn);

    expect(screen.getByText("25%")).toBeTruthy();
    expect(screen.getByText("rm -rf /etc/fake")).toBeTruthy();
  });

  it("permite recolher e expandir o painel de agentes", () => {
    const events: AgentProgressEvent[] = [
      {
        agente: "guardiao",
        status: "aprovado",
        mensagem: "Tudo limpo",
        timestamp: "2026-11-15T18:00:00Z",
      },
    ];

    render(<AgentProgressPanel events={events} isStreaming={false} />);

    expect(screen.getByText("Tudo limpo")).toBeTruthy();

    // Clica no cabeçalho para recolher
    const headerBtn = screen.getByRole("button", { name: /Pipeline de Agentes/ });
    fireEvent.click(headerBtn);

    // O texto da etapa fica recolhido
    expect(screen.queryByText("Tudo limpo")).toBeNull();

    // Clica novamente para expandir
    fireEvent.click(headerBtn);
    expect(screen.getByText("Tudo limpo")).toBeTruthy();
  });
});
