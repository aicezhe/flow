import { useState, type FormEvent } from "react";
import { login } from "../api";
import { setToken } from "../auth";
import { errText } from "../hooks";
import { GUEST_PATH, isPlainClick, navigate } from "../router";
import { FlowBackground } from "./FlowBackground";

interface Props {
  notice: string | null;
  onLoggedIn: () => void;
}

export function Landing({ notice, onLoggedIn }: Props) {
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
    <main className="landing">
      <FlowBackground />
      <div className="landing-inner">
        <p className="landing-mark">Flow</p>
        {notice && <p className="notice">{notice}</p>}

        {!askPin ? (
          <div className="choice">
            <button type="button" className="flow-btn primary" onClick={() => setAskPin(true)}>
              I am Anna
            </button>
            <a
              className="flow-btn"
              href={GUEST_PATH}
              onClick={(e) => {
                if (!isPlainClick(e)) return; // Ctrl/Cmd-клик и «в новой вкладке» работают как у обычной ссылки
                e.preventDefault();
                navigate(GUEST_PATH);
              }}
            >
              I am a guest
            </a>
          </div>
        ) : (
          <form className="panel pin-form" onSubmit={submit}>
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
                {busy ? "Signing in…" : "Sign in"}
              </button>
              <button type="button" className="btn" onClick={() => setAskPin(false)} disabled={busy}>
                Back
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
