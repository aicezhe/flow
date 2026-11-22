// Токен входа: в памяти страницы и в sessionStorage (не localStorage: он закрывается
// вместе с вкладкой). Любой доступ к хранилищу может бросить исключение
// (приватное окно, заблокированные данные сайта), поэтому всё в try/catch.
const KEY = "flow_token";
let memoryToken: string | null = null;

export function getToken(): string | null {
  if (memoryToken) return memoryToken;
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  memoryToken = token;
  try {
    sessionStorage.setItem(KEY, token);
  } catch {
    /* работаем только с токеном в памяти */
  }
}

export function clearToken(): void {
  memoryToken = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* нечего чистить */
  }
}
