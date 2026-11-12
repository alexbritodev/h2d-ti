import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RagFlowStrip } from "./RagFlowStrip";

afterEach(cleanup);

describe("RagFlowStrip", () => {
  it("antes da primeira pergunta mostra as oito etapas sem execução", () => {
    render(<RagFlowStrip steps={null} />);

    const items = within(screen.getByRole("list", { name: "Etapas do RAG" })).getAllByRole("listitem");
    expect(items).toHaveLength(8);
    expect(items.every((item) => item.dataset.status === "skip")).toBe(true);
    expect(screen.getByText(/aparece depois da primeira pergunta/)).toBeTruthy();
  });

  it("marca cada etapa com o resultado do turno e o desfecho em português", () => {
    render(
      <RagFlowStrip
        action="clarify"
        steps={[
          { id: "masking", status: "ok", detail: "" },
          { id: "triage", status: "ok", detail: "tema comum" },
          { id: "rewrite", status: "skip", detail: "primeira mensagem" },
          { id: "search", status: "ok", detail: "8 trecho(s) de 2 manual(is): Servidor Linux" },
          { id: "model", status: "warn", detail: "disse que não achou nos trechos" },
          { id: "outcome", status: "warn", detail: "model_declined" },
        ]}
      />,
    );

    const status = (label: string) => screen.getByText(label).closest("li")?.dataset.status;
    expect(status("Busca nos manuais")).toBe("ok");
    expect(status("Modelo")).toBe("warn");
    expect(status("Conferir")).toBe("skip"); // não rodou neste turno
    expect(screen.getByText("ok: 8 trecho(s) de 2 manual(is): Servidor Linux")).toBeTruthy();
    expect(screen.getByText(/Pediu detalhes/)).toBeTruthy();
  });
});
