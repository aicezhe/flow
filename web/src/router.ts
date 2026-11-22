// Минимальная маршрутизация без библиотеки: два клиентских пути, всё через History API.
// Ссылки только относительные: домен подставится сам (туннель, flow.com, AWS).
import { useEffect, useState } from "react";

export const HOME_PATH = "/";
export const GUEST_PATH = "/guestform";

function normalize(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, "");
  return trimmed === "" ? HOME_PATH : trimmed;
}

export function currentPath(): string {
  return normalize(window.location.pathname);
}

// Переход без перезагрузки страницы. replace=true не добавляет запись в историю (для редиректов).
export function navigate(to: string, replace = false): void {
  if (replace) window.history.replaceState(null, "", to);
  else window.history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate")); // сообщаем usePath
}

export function usePath(): string {
  const [path, setPath] = useState(currentPath);
  useEffect(() => {
    const sync = () => setPath(currentPath());
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  return path;
}

// Обычный клик по ссылке обрабатываем сами; с Ctrl/Cmd/Shift, средней кнопкой
// и «открыть в новой вкладке» оставляем браузеру.
export function isPlainClick(e: { button: number; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean }): boolean {
  return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
}

// Код приглашения из адреса: /guestform?invite=КОД. Пустое значение считаем отсутствующим.
export function inviteFromUrl(): string | null {
  const code = new URLSearchParams(window.location.search).get("invite")?.trim();
  return code ? code : null;
}
