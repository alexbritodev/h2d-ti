import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const tokensCss = readFileSync(resolve(process.cwd(), "src/styles/tokens.css"), "utf-8");

const MIN_CONTRAST = 4.5;

function readBlock(selectorStart: string): Record<string, string> {
  const start = tokensCss.indexOf(selectorStart);
  if (start < 0) throw new Error(`Bloco não encontrado: ${selectorStart}`);
  const block = tokensCss.slice(start, tokensCss.indexOf("}", start));
  return Object.fromEntries(
    [...block.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/g)].map((m) => [m[1], m[2]]),
  ) as Record<string, string>;
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => {
    const value = parseInt(hex.slice(i, i + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

describe.each([
  ["claro", readBlock('[data-theme="light"]')],
  ["escuro", readBlock('[data-theme="dark"]')],
])("tema %s", (_name, theme) => {
  const pairs = ["text", "muted", "accent", "warn", "danger", "info"].flatMap((fg) =>
    ["bg", "surface", "surface-2"].map((bg) => [fg, bg] as const),
  );

  it.each(pairs)("%s sobre %s atinge 4,5:1", (fg, bg) => {
    expect(contrast(theme[fg]!, theme[bg]!)).toBeGreaterThanOrEqual(MIN_CONTRAST);
  });

  it("texto do botão principal atinge 4,5:1", () => {
    expect(contrast(theme["accent-fg"]!, theme.accent!)).toBeGreaterThanOrEqual(MIN_CONTRAST);
  });
});

describe("barra lateral", () => {
  const sidebar = readBlock(":root {");

  it.each([
    ["sidebar-text", "sidebar"],
    ["sidebar-text", "sidebar-hover"],
    ["sidebar-muted", "sidebar"],
    ["sidebar-accent", "sidebar"],
  ])("%s sobre %s atinge 4,5:1", (fg, bg) => {
    expect(contrast(sidebar[fg]!, sidebar[bg]!)).toBeGreaterThanOrEqual(MIN_CONTRAST);
  });
});
