import { useState, type FormEvent } from "react";
import { login } from "../api";
import { setToken } from "../auth";
import { errText } from "../hooks";

interface Props {
  notice: string | null;
  onFriend: () => void;
  onLoggedIn: () => void;
}

export function Landing({ notice, onFriend, onLoggedIn }: Props) {
  const [askPin, setAskPin] = useState(false);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !pin) return;
    setBusy(true);
    setError(null);
    try {
      const { token } = await login(pin);
      setToken(token);
      onLoggedIn();
    } catch (err) {
      setError(errText(err));
      setBusy(false);
    }
  }

  return (
    <main className="page narrow landing">
      <p className="mono">Flow · музыкальные рекомендации</p>
      <h1>Кто что слушает</h1>
      <p className="lead">Общий отчёт о музыке для небольшой компании друзей.</p>
      {notice && <p className="notice">{notice}</p>}

      {!askPin ? (
        <div className="choice">
          <button type="button" className="btn big primary" onClick={() => setAskPin(true)}>
            Я Анна
          </button>
          <button type="button" className="btn big" onClick={onFriend}>
            Я друг
          </button>
        </div>
      ) : (
        <form className="panel" onSubmit={submit}>
          <label htmlFor="pin">PIN</label>
          <input
            id="pin"
            type="password"
            autoFocus
            autoComplete="off"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
          />
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="row">
            <button type="submit" className="btn primary" disabled={busy || !pin}>
              {busy ? "Входим…" : "Войти"}
            </button>
            <button type="button" className="btn" onClick={() => setAskPin(false)} disabled={busy}>
              Назад
            </button>
          </div>
        </form>
      )}
    </main>
  );
}
