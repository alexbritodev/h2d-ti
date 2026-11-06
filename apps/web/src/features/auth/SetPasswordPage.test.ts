import { describe, expect, it } from "vitest";

import { passwordProblem } from "./SetPasswordPage";

describe("passwordProblem", () => {
  it("aceita 6 ou mais caracteres com letras e números", () => {
    expect(passwordProblem("senha123", "senha123")).toBeNull();
    expect(passwordProblem("abc123", "abc123")).toBeNull();
  });

  it("recusa senha curta, sem número, sem letra ou diferente da confirmação", () => {
    expect(passwordProblem("ab12", "ab12")).toMatch(/6 caracteres/);
    expect(passwordProblem("somenteletras", "somenteletras")).toMatch(/letras e números/);
    expect(passwordProblem("123456", "123456")).toMatch(/letras e números/);
    expect(passwordProblem("senha123", "senha124")).toMatch(/não são iguais/);
  });
});
