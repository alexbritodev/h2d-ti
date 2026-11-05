import { describe, expect, it } from "vitest";

import { initials } from "./utils";

describe("initials", () => {
  it.each([
    ["Ana Maria Souza", "AS"],
    ["Túlio", "T"],
    ["  fátima   lima ", "FL"],
    ["", "?"],
  ])("%s vira %s", (name, expected) => {
    expect(initials(name)).toBe(expected);
  });
});
