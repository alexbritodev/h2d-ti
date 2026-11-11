import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Markdown } from "./Markdown";

afterEach(cleanup);

describe("Markdown", () => {
  it("bloco de código ganha botão que copia só o comando", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<Markdown>{"Rode:\n\n```bash\nsudo adduser NOME_DO_USUARIO\n```\n"}</Markdown>);

    await userEvent.click(screen.getByRole("button", { name: "Copiar comando" }));

    expect(writeText).toHaveBeenCalledWith("sudo adduser NOME_DO_USUARIO");
    expect(await screen.findByRole("button", { name: "Comando copiado" })).toBeTruthy();
  });

  it("código dentro da frase não ganha botão", () => {
    render(<Markdown>{"Use o `adduser` para isso."}</Markdown>);

    expect(screen.queryByRole("button")).toBeNull();
  });
});
