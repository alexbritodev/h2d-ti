import { describe, expect, it } from "vitest";

import { navGroupsFor, navItemsFor } from "./navigation";

describe("item do Escritório (experimental)", () => {
  it("fica fora do menu por padrão, para todos os perfis", () => {
    for (const role of ["user", "tech", "admin"] as const) {
      expect(navItemsFor(role).map((item) => item.path)).not.toContain("/escritorio");
      expect(navItemsFor(role, { escritorio: false }).map((item) => item.path)).not.toContain(
        "/escritorio",
      );
    }
  });

  it("aparece para todos os perfis quando a flag está ligada", () => {
    for (const role of ["user", "tech", "admin"] as const) {
      expect(navItemsFor(role, { escritorio: true }).map((item) => item.path)).toContain(
        "/escritorio",
      );
    }
  });

  it("não altera os grupos de menu de hoje", () => {
    expect(navGroupsFor("user").map((group) => group.name)).toEqual(["Atendimento"]);
    expect(navGroupsFor("user", { escritorio: true }).map((group) => group.name)).toEqual([
      "Atendimento",
    ]);
  });
});
