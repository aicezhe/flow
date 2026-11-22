// Все запросы к бэкенду живут здесь, больше нигде нет fetch.
import { clearToken, getToken } from "./auth";
import type { AuthResponse, DecisionResponse, NewPerson, Person, Report, SignupIn, SignupRequest, SyncResponse } from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

// detail приходит строкой (наши ошибки) или списком объектов {msg} (422 от валидации).
function messageFrom(status: number, body: unknown): string {
  const detail =
    typeof body === "object" && body !== null && "detail" in body
      ? (body as { detail: unknown }).detail
      : undefined;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d: unknown) =>
      typeof d === "object" && d !== null && "msg" in d ? String((d as { msg: unknown }).msg) : String(d),
    );
    return `Проверьте введённые данные: ${parts.join("; ")}`;
  }
  // 502/503/504 без JSON-тела приходят от прокси, когда бэкенд не запущен
  if (status === 502 || status === 503 || status === 504) {
    return "Нет связи с сервером. Запущен ли бэкенд на 127.0.0.1:8000?";
  }
  return `Ошибка сервера (${status})`;
}

async function request<T>(
  method: "GET" | "POST" | "DELETE",
  path: string,
  body?: unknown,
  withAuth = true,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = withAuth ? getToken() : null;
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    const init: RequestInit = { method, headers };
    if (body !== undefined) init.body = JSON.stringify(body);
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Нет связи с сервером. Запущен ли бэкенд на 127.0.0.1:8000?");
  }

  if (res.status === 204) return undefined as T; // DELETE отвечает без тела

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* тела нет или оно не JSON */
  }
  if (!res.ok) {
    if (res.status === 401 && withAuth) {
      clearToken();
      onUnauthorized?.();
    }
    throw new ApiError(res.status, messageFrom(res.status, data));
  }
  return data as T;
}

export const login = (pin: string) => request<AuthResponse>("POST", "/api/auth", { pin }, false);
export const getPeople = () => request<Person[]>("GET", "/api/people");
export const addPerson = (p: NewPerson) => request<Person>("POST", "/api/people", p);
export const deletePerson = (username: string) =>
  request<void>("DELETE", `/api/people/${encodeURIComponent(username)}`);
// /api/sync блокирующий: ответ приходит, когда загрузка закончилась.
export const sync = (username?: string) =>
  request<SyncResponse>("POST", "/api/sync", username ? { username } : {});
export const getReport = () => request<Report>("GET", "/api/report");

// Публичная заявка друга: без токена.
export const signup = (b: SignupIn) => request<{ status: string }>("POST", "/api/signup", b, false);
export const getSignups = () => request<SignupRequest[]>("GET", "/api/signups");
export const approveSignup = (id: number) => request<DecisionResponse>("POST", `/api/signups/${id}/approve`, {});
export const rejectSignup = (id: number) => request<DecisionResponse>("POST", `/api/signups/${id}/reject`, {});
