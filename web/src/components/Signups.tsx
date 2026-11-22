import { useState } from "react";
import { approveSignup, rejectSignup } from "../api";
import { fmtDateTime } from "../format";
import { errText, type LoadState } from "../hooks";
import type { SignupRequest } from "../types";
import { Async, Empty } from "./ui";

function Row({ s, locked, onAct }: { s: SignupRequest; locked: boolean; onAct: (id: number, ok: boolean) => void }) {
  return (
    <li className="person">
      <div className="person-main">
        <strong>{s.username}</strong>
        <div className="meta">
          заявка {fmtDateTime(s.created_at)} · согласие {fmtDateTime(s.consent_at)}
          {s.contact ? ` · контакт: ${s.contact}` : ""}
        </div>
      </div>
      <div className="row">
        <button type="button" className="btn small primary" disabled={locked} onClick={() => onAct(s.id, true)}>
          Принять
        </button>
        <button type="button" className="btn small" disabled={locked} onClick={() => onAct(s.id, false)}>
          Отклонить
        </button>
      </div>
    </li>
  );
}

export function Signups({ state, onChanged }: { state: LoadState<SignupRequest[]>; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(id: number, ok: boolean) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await (ok ? approveSignup(id) : rejectSignup(id));
      onChanged();
    } catch (e) {
      setError(errText(e));
      state.reload(); // возможно, заявку уже обработали
    } finally {
      setBusy(false);
    }
  }

  return (
    <Async
      state={state}
      isEmpty={(l) => l.length === 0}
      empty={<Empty title="Новых заявок нет">Когда друг отправит заявку со страницы «Я друг», она появится здесь.</Empty>}
    >
      {(list) => (
        <section>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <p className="meta">После принятия человек появится на вкладке «Люди». Прослушивания загрузите кнопкой «Синхронизировать».</p>
          <ul className="people">
            {list.map((s) => (
              <Row key={s.id} s={s} locked={busy} onAct={act} />
            ))}
          </ul>
        </section>
      )}
    </Async>
  );
}
