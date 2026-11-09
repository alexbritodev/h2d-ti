import { describe, expect, it } from "vitest";

import { homeFor, navGroupsFor, navItemsFor, safeRedirect } from "./navigation";

describe("navGroupsFor", () => {
  it("usuário comum só vê o grupo de atendimento", () => {
    expect(navGroupsFor("user").map((group) => group.name)).toEqual(["Atendimento"]);
  });

  it("admin vê os três grupos, na ordem", () => {
    expect(navGroupsFor("admin").map((group) => group.name)).toEqual([
      "Atendimento",
      "Operação de TI",
      "Administração",
    ]);
  });
});

describe("navItemsFor", () => {
  it("usuário comum não vê telas de técnico nem de admin", () => {
    const paths = navItemsFor("user").map((item) => item.path);
    expect(paths).toEqual(["/chat", "/meus-chamados", "/base"]);
  });

  it("técnico vê a fila, mas não a ingestão", () => {
    const paths = navItemsFor("tech").map((item) => item.path);
    expect(paths).toContain("/chamados");
    expect(paths).not.toContain("/admin/ingestao");
  });

  it("admin vê a ingestão", () => {
    expect(navItemsFor("admin").map((item) => item.path)).toContain("/admin/ingestao");
  });

  it("o fluxo do RAG é só do admin", () => {
    expect(navItemsFor("admin").map((item) => item.path)).toContain("/admin/rag");
    expect(navItemsFor("tech").map((item) => item.path)).not.toContain("/admin/rag");
    expect(navItemsFor("user").map((item) => item.path)).not.toContain("/admin/rag");
  });

  it.each(["user", "tech", "admin"] as const)("a tela inicial de %s está no menu", (role) => {
    expect(navItemsFor(role).map((item) => item.path)).toContain(homeFor(role));
  });
});

describe("safeRedirect", () => {
  it("aceita caminho interno", () => {
    expect(safeRedirect("/chamados")).toBe("/chamados");
  });

  it.each(["//evil.example", "/\\evil.example", "https://evil.example", "chat", "", null, 42])(
    "recusa %s",
    (target) => {
      expect(safeRedirect(target)).toBeNull();
    },
  );
});
