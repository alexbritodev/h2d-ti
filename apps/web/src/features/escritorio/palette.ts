import { createContext, useContext, useSyncExternalStore } from "react";

export type SceneTheme = "light" | "dark";

/** Cores da cena que mudam com o tema. Móveis, bonecos e o balão ficam iguais nos dois. */
export interface Palette {
  background: string;
  /** Pisos sem atividade (xadrez). */
  tileA: string;
  tileB: string;
  tileLine: string;
  wallLeft: string;
  wallBack: string;
  labelIdle: string;
  labelActive: string;
  /** Cor com que a da sala é misturada para pintar o piso (preto no escuro, branco no claro). */
  mixBase: string;
  /** Quanto da cor da sala entra no piso: [casa clara, casa escura] do xadrez. */
  activeMix: readonly [number, number];
  visitedMix: readonly [number, number];
}

export const PALETTES: Record<SceneTheme, Palette> = {
  dark: {
    background: "#121214",
    tileA: "#25252a",
    tileB: "#2b2b30",
    tileLine: "rgba(0,0,0,.25)",
    wallLeft: "#3d3d44",
    wallBack: "#46464e",
    labelIdle: "#9a9aa2",
    labelActive: "#ffffff",
    mixBase: "#000000",
    activeMix: [0.34, 0.28],
    visitedMix: [0.2, 0.16],
  },
  light: {
    background: "#e7e7ec",
    tileA: "#d4d4db",
    tileB: "#dedee4",
    tileLine: "rgba(0,0,0,.1)",
    wallLeft: "#b3b3be",
    wallBack: "#c3c3cd",
    labelIdle: "#4f4f58",
    labelActive: "#0f0f12",
    mixBase: "#ffffff",
    activeMix: [0.42, 0.34],
    visitedMix: [0.26, 0.2],
  },
};

/** Mistura `color` com `base` (hex): `amount` é a parte de `color`, de 0 a 1. */
export function mix(color: string, base: string, amount: number): string {
  const a = Number.parseInt(color.slice(1), 16);
  const b = Number.parseInt(base.slice(1), 16);
  const channel = (shift: number) =>
    Math.round(((a >> shift) & 255) * amount + ((b >> shift) & 255) * (1 - amount));
  return `rgb(${channel(16)},${channel(8)},${channel(0)})`;
}

/** O app guarda o tema em `data-theme` no <html> (claro é o padrão). */
function currentTheme(): SceneTheme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

/** Segue o tema do app ao vivo: trocar claro/escuro redesenha a cena sem recarregar. */
export function useSceneTheme(): SceneTheme {
  return useSyncExternalStore(subscribe, currentTheme, () => "light" as SceneTheme);
}

export const PaletteContext = createContext<Palette>(PALETTES.light);

export function usePalette(): Palette {
  return useContext(PaletteContext);
}
