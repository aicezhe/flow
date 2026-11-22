import type { CSSProperties } from "react";
import type { PersonStatus } from "./types";

export function fmtDate(ts: number | null): string {
  return ts === null ? "-" : new Date(ts * 1000).toLocaleDateString("ru-RU");
}

export function fmtDateTime(ts: number | null): string {
  return ts === null
    ? "-"
    : new Date(ts * 1000).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

// 1 прослушивание, 2 прослушивания, 5 прослушиваний
export function plural(n: number, forms: [string, string, string]): string {
  const m10 = n % 10;
  const m100 = n % 100;
  const form = m10 === 1 && m100 !== 11 ? forms[0] : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? forms[1] : forms[2];
  return `${n} ${form}`;
}

export const PLAYS: [string, string, string] = ["прослушивание", "прослушивания", "прослушиваний"];

export const STATUS_LABEL: Record<PersonStatus, string> = {
  ok: "Готово",
  private: "Профиль закрыт",
  not_found: "Ник не найден",
  error: "Ошибка",
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
