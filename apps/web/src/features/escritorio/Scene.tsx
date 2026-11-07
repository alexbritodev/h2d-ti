import "./escritorio.css";

import { ROOM_BY_KEY, ROOMS, type RoomKey, type SceneState } from "./engine";
import { mix, PALETTES, PaletteContext, usePalette, useSceneTheme } from "./palette";

/**
 * Cena isométrica em SVG, desenhada só com polígonos (sem imagens). A projeção é a clássica 2:1:
 * cada tile tem 48x24 e a altura (z) sobe em pixels.
 */
const TW = 48;
const TH = 24;
const OX = 352;
const OY = 74;
const VIEW_W = 640;
const VIEW_H = 372;

type Pt = [number, number];

const project = (x: number, y: number, z = 0): Pt => [
  OX + ((x - y) * TW) / 2,
  OY + ((x + y) * TH) / 2 - z,
];

const points = (list: Pt[]) => list.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

function shade(hex: string, factor: number): string {
  const n = Number.parseInt(hex.slice(1), 16);
  const channel = (shift: number) => Math.round(((n >> shift) & 255) * factor);
  return `rgb(${channel(16)},${channel(8)},${channel(0)})`;
}

interface BoxProps {
  x: number;
  y: number;
  z?: number;
  w: number;
  d: number;
  h: number;
  color: string;
  className?: string;
}

function Box({ x, y, z = 0, w, d, h, color, className }: BoxProps) {
  const stroke = "rgba(0,0,0,.4)";
  return (
    <g className={className}>
      <polygon
        points={points([
          project(x, y, z + h),
          project(x + w, y, z + h),
          project(x + w, y + d, z + h),
          project(x, y + d, z + h),
        ])}
        fill={color}
        stroke={stroke}
        strokeWidth={0.6}
        strokeLinejoin="round"
      />
      <polygon
        points={points([
          project(x, y + d, z + h),
          project(x + w, y + d, z + h),
          project(x + w, y + d, z),
          project(x, y + d, z),
        ])}
        fill={shade(color, 0.74)}
        stroke={stroke}
        strokeWidth={0.6}
        strokeLinejoin="round"
      />
      <polygon
        points={points([
          project(x + w, y, z + h),
          project(x + w, y + d, z + h),
          project(x + w, y + d, z),
          project(x + w, y, z),
        ])}
        fill={shade(color, 0.52)}
        stroke={stroke}
        strokeWidth={0.6}
        strokeLinejoin="round"
      />
    </g>
  );
}

/** Origem de cada sala na grade de tiles (4x4 por sala, 1 tile de corredor entre elas). */
const ORIGIN: Record<RoomKey, { x: number; y: number }> = {
  recepcao: { x: 0, y: 0 },
  triagem: { x: 5, y: 0 },
  rag: { x: 0, y: 5 },
  banco: { x: 5, y: 5 },
  tecnicos: { x: 0, y: 10 },
  auditoria: { x: 5, y: 10 },
};

/** Onde o funcionário principal de cada sala fica, em tiles dentro da sala. */
const WORKER: Record<RoomKey, { x: number; y: number }> = {
  recepcao: { x: 1.9, y: 2.0 },
  triagem: { x: 2.0, y: 2.3 },
  rag: { x: 2.0, y: 2.1 },
  banco: { x: 2.5, y: 2.5 },
  tecnicos: { x: 1.2, y: 2.2 },
  auditoria: { x: 2.4, y: 2.2 },
};

/** [x, y, z, largura, profundidade, altura, cor, pisca?] dentro da sala. "accent" = cor da sala. */
type Piece = [number, number, number, number, number, number, string, boolean?];

const DESK = "#6a6a72";
const STOOL = "#55555c";
const SCREEN_BASE = "#18181b";

function books(): Piece[] {
  const colors = ["#E5484D", "#4F9CF0", "#E8A33D", "#8B7FE8", "#46b86a", "#EC6B3A", "#F0F0F0"];
  const list: Piece[] = [];
  for (let shelf = 0; shelf < 2; shelf += 1) {
    for (let book = 0; book < 8; book += 1) {
      list.push([
        0.62 + book * 0.34,
        0.8,
        6 + shelf * 17,
        0.26,
        0.05,
        12,
        colors[(book + shelf * 3) % colors.length]!,
      ]);
    }
  }
  return list;
}

function racks(): Piece[] {
  const list: Piece[] = [];
  for (let rack = 0; rack < 3; rack += 1) {
    list.push([0.6 + rack * 1.15, 0.4, 0, 0.95, 0.95, 44, "#34343e"]);
    for (let led = 0; led < 4; led += 1) {
      list.push([0.72 + rack * 1.15, 1.35, 8 + led * 9, 0.1, 0.03, 3, "#46e08a", true]);
      list.push([1.15 + rack * 1.15, 1.35, 8 + led * 9, 0.1, 0.03, 3, "#46e08a", true]);
    }
  }
  return list;
}

function cabinets(): Piece[] {
  const list: Piece[] = [];
  for (let cabinet = 0; cabinet < 3; cabinet += 1) {
    list.push([0.6 + cabinet * 1.05, 0.35, 0, 0.9, 0.9, 28, "#74746e"]);
    for (let drawer = 0; drawer < 3; drawer += 1) {
      list.push([0.7 + cabinet * 1.05, 1.25, 3 + drawer * 8, 0.7, 0.03, 6, "#4a4a46"]);
    }
  }
  return list;
}

const FURNITURE: Record<RoomKey, (accent: string) => Piece[]> = {
  recepcao: (c) => [
    [1, 0.7, 0, 2, 0.8, 12, DESK],
    [1.7, 0.85, 12, 0.5, 0.07, 12, SCREEN_BASE],
    [1.76, 0.92, 15, 0.38, 0.03, 7, c, true],
    [3.2, 0.35, 0, 0.4, 0.4, 8, "#7a5a3a"],
    [3.25, 0.4, 8, 0.3, 0.3, 14, "#2FB58A"],
    [0.5, 2.9, 0, 0.9, 0.6, 8, STOOL],
  ],
  triagem: () => [
    [0.5, 2.9, 0, 3, 0.5, 6, "#4b4b52"],
    [0.7, 0.8, 0, 0.8, 0.9, 16, "#E5484D"],
    [1.8, 0.8, 0, 0.8, 0.9, 16, "#E8A33D"],
    [2.9, 0.8, 0, 0.8, 0.9, 16, "#46b86a"],
    [0.5, 0.3, 0, 0.8, 0.3, 6, STOOL],
  ],
  rag: () => [[0.5, 0.25, 0, 3, 0.55, 38, "#5a4636"], ...books(), [2.9, 2.3, 0, 0.9, 0.7, 11, DESK]],
  banco: () => [...racks(), [3.2, 3, 0, 0.6, 0.6, 8, STOOL]],
  tecnicos: (c) => [
    [0.5, 0.9, 0, 1.5, 0.8, 12, DESK],
    [1.1, 1.0, 12, 0.5, 0.07, 12, SCREEN_BASE],
    [1.16, 1.07, 15, 0.38, 0.03, 7, c, true],
    [2.3, 0.9, 0, 1.5, 0.8, 12, DESK],
    [2.9, 1.0, 12, 0.5, 0.07, 12, SCREEN_BASE],
    [2.96, 1.07, 15, 0.38, 0.03, 7, "#9a9aa2", true],
    [3.1, 3.1, 0, 0.5, 0.5, 10, STOOL],
  ],
  auditoria: () => [...cabinets(), [2.9, 2.9, 0, 0.8, 0.6, 10, DESK]],
};

function Person({
  x,
  y,
  shirt,
  working,
}: {
  x: number;
  y: number;
  shirt: string;
  working: boolean;
}) {
  const [sx, sy] = project(x, y, 0);
  return (
    <g>
      <ellipse cx={sx} cy={sy} rx={9} ry={4.5} fill="#000" opacity={0.35} />
      <g className={working ? "eo-bob" : undefined}>
        <Box x={x - 0.15} y={y - 0.1} w={0.12} d={0.12} h={9} color="#26262c" />
        <Box x={x + 0.03} y={y - 0.1} w={0.12} d={0.12} h={9} color="#26262c" />
        <Box x={x - 0.17} y={y - 0.13} z={9} w={0.36} d={0.26} h={14} color={shirt} />
        <Box x={x - 0.13} y={y - 0.11} z={23} w={0.28} d={0.22} h={11} color="#F0B48F" />
        <Box x={x - 0.14} y={y - 0.12} z={32} w={0.3} d={0.24} h={4} color="#2a2a30" />
      </g>
    </g>
  );
}

type RoomStatus = "active" | "visited" | "idle";

function Room({ roomKey, status }: { roomKey: RoomKey; status: RoomStatus }) {
  const palette = usePalette();
  const room = ROOM_BY_KEY[roomKey];
  const { x: rx, y: ry } = ORIGIN[roomKey];
  const worker = WORKER[roomKey];
  const pieces = FURNITURE[roomKey](room.color)
    .map(([x, y, z, w, d, h, color, blink]) => ({ x: rx + x, y: ry + y, z, w, d, h, color, blink }))
    .sort((a, b) => a.x + a.y - (b.x + b.y) || a.z - b.z);
  const active = status === "active";
  const [labelX, labelY] = project(rx, ry, 40);

  const tiles = [];
  for (let i = 0; i < 4; i += 1) {
    for (let j = 0; j < 4; j += 1) {
      const odd = (i + j) % 2 === 1;
      const fill = active
        ? mix(room.color, palette.mixBase, palette.activeMix[odd ? 0 : 1])
        : status === "visited"
          ? mix(room.color, palette.mixBase, palette.visitedMix[odd ? 0 : 1])
          : odd
            ? palette.tileB
            : palette.tileA;
      tiles.push(
        <polygon
          key={`${i}-${j}`}
          points={points([
            project(rx + i, ry + j),
            project(rx + i + 1, ry + j),
            project(rx + i + 1, ry + j + 1),
            project(rx + i, ry + j + 1),
          ])}
          fill={fill}
          stroke={palette.tileLine}
          strokeWidth={0.6}
        />,
      );
    }
  }

  return (
    <g data-room={roomKey} data-status={status}>
      {tiles}
      <polygon
        points={points([
          project(rx, ry),
          project(rx + 4, ry),
          project(rx + 4, ry + 4),
          project(rx, ry + 4),
        ])}
        fill="none"
        stroke={room.color}
        strokeWidth={2.5}
        strokeLinejoin="round"
        opacity={active ? 1 : 0}
      />
      <Box x={rx - 0.14} y={ry} w={0.14} d={4} h={26} color={palette.wallLeft} />
      <Box x={rx} y={ry - 0.14} w={4} d={0.14} h={26} color={palette.wallBack} />
      <Box x={rx - 0.14} y={ry - 0.14} w={0.14} d={0.14} h={26} color={room.color} />
      {pieces.map((piece, index) => (
        <Box
          key={index}
          x={piece.x}
          y={piece.y}
          z={piece.z}
          w={piece.w}
          d={piece.d}
          h={piece.h}
          color={piece.color}
          className={piece.blink && active ? "eo-blink" : undefined}
        />
      ))}
      <Person x={rx + worker.x} y={ry + worker.y} shirt={room.color} working={active} />
      {roomKey === "tecnicos" && <Person x={rx + 3} y={ry + 2.3} shirt="#7c7c84" working={false} />}
      <text
        x={labelX}
        y={labelY - 9}
        textAnchor="middle"
        fontSize={11}
        fontWeight={500}
        fontFamily="'JetBrains Mono Variable', ui-monospace, monospace"
        fill={active ? palette.labelActive : palette.labelIdle}
      >
        {room.name}
        {status === "visited" ? " ✓" : ""}
      </text>
    </g>
  );
}

const ENTRANCE = { x: ORIGIN.recepcao.x + 0.3, y: ORIGIN.recepcao.y + 0.3 };

function TicketIcon() {
  return (
    <g>
      <Box x={-0.17} y={-0.17} w={0.34} d={0.34} h={11} color="#F5C14B" />
      <Box x={-0.1} y={-0.1} z={11} w={0.2} d={0.2} h={2} color="#B8861B" />
    </g>
  );
}

function Ticket({ state }: { state: SceneState }) {
  const target = state.active
    ? { x: ORIGIN[state.active].x + 2.1, y: ORIGIN[state.active].y + 2.2, z: 15 }
    : { ...ENTRANCE, z: 12 };
  const [ox, oy] = project(0, 0, 0);
  const [px, py] = project(target.x, target.y, target.z);
  const [gx, gy] = project(target.x, target.y, 0);
  // Reinicia o salto só quando o chamado muda de sala (e não a cada evento na mesma sala).
  const hopKey = `${state.active ?? "-"}:${state.visited.length}`;
  return (
    <g aria-hidden>
      <ellipse
        className="eo-ticket"
        cx={0}
        cy={0}
        rx={9}
        ry={4.5}
        fill="#000"
        opacity={0.4}
        style={{ transform: `translate(${gx}px, ${gy}px)` }}
      />
      <g className="eo-ticket" style={{ transform: `translate(${px - ox}px, ${py - oy}px)` }}>
        <g key={hopKey} className="eo-hop">
          <TicketIcon />
        </g>
      </g>
    </g>
  );
}

function Bubble({ state }: { state: SceneState }) {
  if (!state.active || !state.bubble) return null;
  const { x: rx, y: ry } = ORIGIN[state.active];
  const worker = WORKER[state.active];
  const [cx, cy] = project(rx + worker.x, ry + worker.y, 58);
  const width = state.bubble.length * 6.7 + 16;
  const left = Math.min(Math.max(cx - width / 2, 4), VIEW_W - width - 4);
  const top = Math.max(cy - 24, 4);
  const tail = Math.min(Math.max(cx - left, 10), width - 10);
  return (
    <g key={`${state.index}`} className="eo-bubble" transform={`translate(${left} ${top})`} aria-hidden>
      <rect width={width} height={22} rx={3} fill="#f4f4f2" stroke="#121214" strokeWidth={2} />
      <polygon points={`${tail - 5},21 ${tail + 5},21 ${tail},28`} fill="#f4f4f2" stroke="#121214" strokeWidth={2} />
      <rect x={tail - 4} y={19} width={8} height={4} fill="#f4f4f2" />
      <text
        x={8}
        y={15}
        fontSize={11}
        fill="#121214"
        fontFamily="'JetBrains Mono Variable', ui-monospace, monospace"
      >
        {state.bubble}
      </text>
    </g>
  );
}

export function describeScene(state: SceneState): string {
  if (!state.active) return "Escritório virtual. Nenhum passo executado ainda.";
  const room = ROOM_BY_KEY[state.active];
  return `Escritório virtual. Sala ativa: ${room.name}, com ${room.agent}. Passo ${state.index + 1} de ${state.total}.`;
}

export function OfficeScene({ state }: { state: SceneState }) {
  const theme = useSceneTheme();
  const palette = PALETTES[theme];
  const statusOf = (key: RoomKey): RoomStatus =>
    state.active === key ? "active" : state.visited.includes(key) ? "visited" : "idle";
  return (
    <PaletteContext.Provider value={palette}>
      <svg
        data-testid="office-scene"
        data-theme={theme}
        data-active-room={state.active ?? ""}
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role="img"
        aria-label={describeScene(state)}
        className="block h-auto w-full"
        style={{ background: palette.background }}
      >
        {ROOMS.map((room) => (
          <Room key={room.key} roomKey={room.key} status={statusOf(room.key)} />
        ))}
        <Ticket state={state} />
        <Bubble state={state} />
      </svg>
    </PaletteContext.Provider>
  );
}
