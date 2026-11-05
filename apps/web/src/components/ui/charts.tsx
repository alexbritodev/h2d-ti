import { type CSSProperties, useId } from "react";

/**
 * Gráficos de série única, feitos à mão para ficarem leves: uma cor em degradê, entrada
 * animada, grade discreta, rótulos seletivos, dica ao passar o mouse e versão em tabela.
 * As animações ficam em app.css e respeitam prefers-reduced-motion.
 */
function delay(seconds: number): CSSProperties {
  return { "--delay": `${seconds}s` } as CSSProperties;
}

export function Sparkline({ values, label }: { values: number[]; label: string }) {
  const gradientId = useId();
  const width = 120;
  const height = 36;
  const padding = 4;
  const min = Math.min(...values);
  const range = Math.max(...values) - min || 1;
  const step = (width - padding * 2) / Math.max(1, values.length - 1);
  const points = values.map((value, index) => ({
    x: padding + index * step,
    y: height - padding - ((value - min) / range) * (height - padding * 2),
    value,
  }));
  const first = points[0];
  const last = points[points.length - 1];
  const line = points.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} className="h-9 w-28">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {first && last && (
        <polygon
          className="chart-fade"
          points={`${first.x},${height} ${line} ${last.x},${height}`}
          fill={`url(#${gradientId})`}
        />
      )}
      <polyline
        className="chart-line"
        pathLength={1}
        points={line}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {last && (
        <circle
          className="chart-fade"
          style={delay(0.9)}
          cx={last.x}
          cy={last.y}
          r="3"
          fill="var(--accent)"
        />
      )}
      {points.map((point) => (
        <rect
          key={point.x}
          x={point.x - step / 2}
          y="0"
          width={Math.max(step, 4)}
          height={height}
          fill="transparent"
        >
          <title>{point.value}</title>
        </rect>
      ))}
    </svg>
  );
}

export interface BarDatum {
  label: string;
  value: number;
}

export function BarChart({ data, label, unit }: { data: BarDatum[]; label: string; unit: string }) {
  const max = Math.max(...data.map((datum) => datum.value), 1);
  const peak = data.reduce((best, datum) => (datum.value > best.value ? datum : best), data[0]!);
  const everyNth = Math.ceil(data.length / 7);

  return (
    <figure>
      <figcaption className="sr-only">{label}</figcaption>
      <div className="relative h-52 border-b border-border" aria-hidden>
        {[0.5, 1].map((level) => (
          <div
            key={level}
            className="absolute inset-x-0 flex items-end border-t border-dashed border-border"
            style={{ bottom: `${(level * 100) / 1.15}%` }}
          >
            <span className="absolute -top-4 left-0 text-[11px] text-muted">
              {Math.round(max * level)}
            </span>
          </div>
        ))}
        <div className="absolute inset-y-0 right-0 left-7 flex items-end gap-0.5 sm:gap-1">
          {data.map((datum, index) => (
            <div key={datum.label} className="group relative flex h-full min-w-0 flex-1 items-end">
              <div
                className="chart-bar w-full rounded-t bg-linear-to-t from-accent/25 to-accent transition-[filter] group-hover:brightness-125"
                style={{
                  ...delay(index * 0.03),
                  height: `${(datum.value / max / 1.15) * 100}%`,
                }}
              />
              {datum === peak && (
                <span
                  className="chart-fade absolute left-1/2 -translate-x-1/2 text-[11px] font-medium group-hover:invisible"
                  style={{ bottom: `calc(${(datum.value / max / 1.15) * 100}% + 2px)` }}
                >
                  {datum.value}
                </span>
              )}
              <span className="pointer-events-none absolute bottom-full left-1/2 z-10 hidden -translate-x-1/2 rounded-md border border-border bg-surface px-2 py-1 text-xs whitespace-nowrap shadow-card group-hover:block">
                {datum.label}: <strong>{datum.value}</strong> {unit}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div aria-hidden className="mt-1.5 ml-7 flex gap-0.5 text-[11px] text-muted sm:gap-1">
        {data.map((datum, index) => (
          <span key={datum.label} className="min-w-0 flex-1 text-center whitespace-nowrap">
            {index % everyNth === 0 ? datum.label : ""}
          </span>
        ))}
      </div>
      <details className="mt-3 text-xs text-muted">
        <summary className="cursor-pointer hover:text-text">Ver como tabela</summary>
        <table className="mt-2 w-full max-w-xs text-left">
          <thead>
            <tr>
              <th scope="col" className="py-1 font-medium">
                Dia
              </th>
              <th scope="col" className="py-1 font-medium">
                {unit}
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((datum) => (
              <tr key={datum.label} className="border-t border-border">
                <td className="py-1">{datum.label}</td>
                <td className="py-1">{datum.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

export function RankedBars({ data, unit }: { data: BarDatum[]; unit: string }) {
  const max = Math.max(...data.map((datum) => datum.value), 1);
  return (
    <ul className="space-y-3">
      {data.map((datum, index) => (
        <li key={datum.label}>
          <div className="mb-1 flex justify-between gap-3">
            <span className="truncate">{datum.label}</span>
            <span className="font-medium">
              {datum.value} <span className="sr-only">{unit}</span>
            </span>
          </div>
          <div aria-hidden className="h-2 overflow-hidden rounded-full bg-surface-2">
            <div
              className="chart-bar-h h-full rounded-full bg-linear-to-r from-accent/40 to-accent"
              style={{ ...delay(index * 0.07), width: `${(datum.value / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
