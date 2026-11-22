import type { CSSProperties } from "react";
import type { PersonStatus } from "./types";

export function fmtDate(ts: number | null): string {
  return ts === null ? "-" : new Date(ts * 1000).toLocaleDateString("en-GB");
}

export function fmtDateTime(ts: number | null): string {
  return ts === null
    ? "-"
    : new Date(ts * 1000).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" });
}

// 1 play, 2 plays
export function plural(n: number, forms: [string, string]): string {
  return `${n} ${n === 1 ? forms[0] : forms[1]}`;
}

export const PLAYS: [string, string] = ["play", "plays"];

export const STATUS_LABEL: Record<PersonStatus, string> = {
  ok: "Ready",
  private: "Profile is private",
  not_found: "Username not found",
  error: "Error",
};

// Цвет ячейки тепловой таблицы: логарифмическая шкала, чтобы один любимый артист
// не обесцвечивал остальных. Пустая ячейка без заливки.
export function heatStyle(value: number, max: number): CSSProperties {
  if (value <= 0 || max <= 0) return {};
  const a = Math.log1p(value) / Math.log1p(max);
  return {
    background: `rgba(26,58,107,${(0.08 + 0.92 * a).toFixed(2)})`,
    color: a > 0.55 ? "#fff" : "#1a1a2e",
  };
}
