import { useState, type FormEvent } from "react";
import { ApiError, signup } from "../api";

const USERNAME_RE = /^[\w-]{1,64}$/;

// Сервер уже присылает понятный текст; здесь только случаи, где можно сказать понятнее.
function friendlyError(e: unknown): string {
  if (e instanceof ApiError) {
    // 404 с текстом «Not Found» значит, что приём выключен (SIGNUP_ENABLED); другой 404 это «ник не найден».
    if (e.status === 404 && e.message === "Not Found") return "Sign-ups are closed right now. Just send your username to Anna.";
    if (e.status === 0) return "Can't reach the server. Please try again later.";
    return e.message;
  }
  return "Couldn't send the request. Please try again.";
}

interface Props {
  compact?: boolean; // плотная вёрстка для страницы друга
  onSubmitted?: () => void; // вызывается после успешной отправки
  invite?: string | null; // код из ссылки /guestform?invite=...; если есть, поле в форме не показываем
}

export function SignupForm({ compact = false, onSubmitted, invite = null }: Props) {
  const [username, setUsername] = useState("");
  const [contact, setContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState(""); // honeypot
  const [inviteInput, setInviteInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const name = username.trim();
    if (!USERNAME_RE.test(name)) {
      setError("Username: letters, digits, hyphen and underscore, no spaces. It's in your profile address: last.fm/user/username.");
      return;
    }
    if (!consent) {
      setError("Please tick the consent box, otherwise the request can't be accepted.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const code = invite ?? inviteInput.trim();
      await signup({ username: name, consent, contact: contact.trim(), website, ...(code ? { invite_code: code } : {}) });
      setDone(true);
      onSubmitted?.();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  const cls = `panel signup${compact ? " compact" : ""}`;

  if (done) {
    return (
      <section className={cls} role="status">
        <h3>Request sent</h3>
        <p>Thanks! Anna will review it and add you. If something goes wrong, she'll get in touch.</p>
      </section>
    );
  }

  return (
    <form className={cls} onSubmit={submit} noValidate>
      <h3>Request</h3>
      <div className="fr-fields">
        <div>
          <label htmlFor="su-name">Last.fm username</label>
          <input id="su-name" value={username} maxLength={64} autoComplete="off" onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div>
          <label htmlFor="su-contact">Contact (optional)</label>
          <input id="su-contact" value={contact} maxLength={100} autoComplete="off" onChange={(e) => setContact(e.target.value)} />
        </div>
      </div>

      {invite === null && (
        <details className="fr-invite">
          <summary>I have an invite code</summary>
          <label htmlFor="su-invite">Invite code</label>
          <input id="su-invite" value={inviteInput} maxLength={200} autoComplete="off" autoCapitalize="none" onChange={(e) => setInviteInput(e.target.value)} />
        </details>
      )}

      {/* Приманка для ботов: человек её не видит и не доходит до неё Tab-ом. */}
      <div className="hp" aria-hidden="true">
        <label htmlFor="su-site">Leave this field empty</label>
        <input id="su-site" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
      </div>

      <label className="check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>I agree: Anna will see my artists, track titles and listening times. I can ask her to delete them.</span>
      </label>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? "Checking username…" : "Send request"}
        </button>
      </div>
    </form>
  );
}
