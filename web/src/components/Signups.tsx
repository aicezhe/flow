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
          requested {fmtDateTime(s.created_at)} · consent {fmtDateTime(s.consent_at)}
          {s.contact ? ` · contact: ${s.contact}` : ""}
        </div>
      </div>
      <div className="row">
        <button type="button" className="btn small primary" disabled={locked} onClick={() => onAct(s.id, true)}>
          Approve
        </button>
        <button type="button" className="btn small" disabled={locked} onClick={() => onAct(s.id, false)}>
          Reject
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
      empty={<Empty title="No new requests">When a friend submits the form on the guest page, it will appear here.</Empty>}
    >
      {(list) => (
        <section>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <p className="meta">Once approved, the person appears on the People tab. Load their plays with Sync.</p>
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
