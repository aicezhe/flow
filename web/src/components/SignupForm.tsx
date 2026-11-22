import { useState, type FormEvent } from "react";
import { ApiError, signup } from "../api";

const USERNAME_RE = /^[\w-]{1,64}$/;

// Сервер уже присылает понятный текст; здесь только случаи, где можно сказать понятнее.
function friendlyError(e: unknown): string {
  if (e instanceof ApiError) {
    // 404 с текстом «Not Found» значит, что приём выключен (SIGNUP_ENABLED); другой 404 это «ник не найден».
    if (e.status === 404 && e.message === "Not Found") return "Приём заявок сейчас закрыт. Просто отправьте свой ник Анне.";
    if (e.status === 0) return "Нет связи с сервером. Попробуйте чуть позже.";
    return e.message;
  }
  return "Не удалось отправить заявку. Попробуйте ещё раз.";
}

export function SignupForm() {
  const [username, setUsername] = useState("");
  const [contact, setContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState(""); // honeypot
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const name = username.trim();
    if (!USERNAME_RE.test(name)) {
      setError("Ник состоит из букв, цифр, дефиса и подчёркивания, без пробелов. Он виден в адресе профиля: last.fm/user/ник.");
      return;
    }
    if (!consent) {
      setError("Отметьте галочку согласия, иначе мы не сможем принять заявку.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signup({ username: name, consent, contact: contact.trim(), website });
      setDone(true);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <section className="panel" role="status">
        <h3>Заявка отправлена</h3>
        <p>Спасибо! Анна посмотрит заявку и добавит тебя. Если что-то пойдёт не так, она напишет.</p>
      </section>
    );
  }

  return (
    <form className="panel signup" onSubmit={submit} noValidate>
      <h3>Отправить заявку</h3>
      <label htmlFor="su-name">Ник на Last.fm</label>
      <input id="su-name" value={username} maxLength={64} autoComplete="off" onChange={(e) => setUsername(e.target.value)} />
      <label htmlFor="su-contact">Как с тобой связаться (необязательно)</label>
      <input id="su-contact" value={contact} maxLength={100} autoComplete="off" onChange={(e) => setContact(e.target.value)} />

      {/* Приманка для ботов: человек её не видит и не доходит до неё Tab-ом. */}
      <div className="hp" aria-hidden="true">
        <label htmlFor="su-site">Не заполняйте это поле</label>
        <input id="su-site" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
      </div>

      <label className="check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          Я согласен(на), чтобы Анна видела мои прослушивания: имена артистов, названия треков и время. Их видит только
          она, и я могу попросить удалить их в любой момент.
        </span>
      </label>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? "Проверяем ник…" : "Отправить заявку"}
        </button>
      </div>
    </form>
  );
}
