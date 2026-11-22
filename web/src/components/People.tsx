import { useState, type FormEvent } from "react";
import { addPerson, deletePerson, sync } from "../api";
import { errText, type LoadState } from "../hooks";
import { fmtDateTime, plural, PLAYS, STATUS_LABEL } from "../format";
import type { Person, SyncResult } from "../types";
import { Async, Empty, Loading } from "./ui";

const USERNAME_RE = /^[\w-]{1,64}$/; // как на сервере

function AddFriendForm({ onAdded }: { onAdded: () => void }) {
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const name = username.trim();
    if (!USERNAME_RE.test(name)) {
      setError("A Last.fm username has letters, digits, hyphen and underscore, no spaces.");
      return;
    }
    setBusy(true);
    setError(null);
    setAdded(null);
    try {
      const p = await addPerson({ username: name, display_name: displayName.trim() });
      setAdded(p.username);
      setUsername("");
      setDisplayName("");
      onAdded();
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h3>Add a friend</h3>
      <p className="privacy">
        We collect artists, track titles and listening times. The data can be deleted at any time.
      </p>
      <label htmlFor="uname">Last.fm username</label>
      <input id="uname" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />
      <label htmlFor="dname">Display name (optional)</label>
      <input id="dname" value={displayName} maxLength={60} onChange={(e) => setDisplayName(e.target.value)} autoComplete="off" />
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {added && (
        <p className="form-ok" role="status">
          Added {added}. Now press Sync to load their plays.
        </p>
      )}
      <div className="row">
        <button type="submit" className="btn primary" disabled={busy || !username.trim()}>
          {busy ? "Checking username…" : "Add"}
        </button>
      </div>
    </form>
  );
}

function PersonRow(props: {
  p: Person;
  locked: boolean;
  onSync: () => void;
  onDeleted: () => void;
}) {
  const { p, locked, onSync, onDeleted } = props;
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setDeleting(true);
    setError(null);
    try {
      await deletePerson(p.username);
      onDeleted();
    } catch (err) {
      setError(errText(err));
      setDeleting(false);
    }
  }

  const waiting = p.status === "ok" && p.plays === 0;
  return (
    <li className="person">
      <div className="person-main">
        <div className="person-name">
          <strong>{p.display_name}</strong>
          {p.display_name !== p.username && <span className="mono"> {p.username}</span>}
        </div>
        <div className="meta">
          {plural(p.plays, PLAYS)} · {p.last_synced_at ? `updated ${fmtDateTime(p.last_synced_at)}` : "not loaded yet"}
        </div>
        {waiting ? (
          <span className="badge wait">waiting for data</span>
        ) : (
          <span className={`badge ${p.status}`}>{STATUS_LABEL[p.status]}</span>
        )}
        {p.status !== "ok" && p.error && <p className="person-error">{p.error}</p>}
      </div>

      {confirming ? (
        <div className="confirm" role="alertdialog" aria-label="Confirm deletion">
          <p>
            Delete {p.display_name} and all their plays? This cannot be undone.
          </p>
          <div className="row">
            <button type="button" className="btn danger" onClick={remove} disabled={deleting}>
              {deleting ? "Deleting…" : "Yes, delete"}
            </button>
            <button type="button" className="btn" onClick={() => setConfirming(false)} disabled={deleting}>
              Cancel
            </button>
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </div>
      ) : (
        <div className="row">
          <button type="button" className="btn small" onClick={onSync} disabled={locked}>
            Update
          </button>
          <button type="button" className="btn small" onClick={() => setConfirming(true)} disabled={locked}>
            Delete
          </button>
        </div>
      )}
    </li>
  );
}

function SyncResults({ results }: { results: SyncResult[] }) {
  return (
    <ul className="results" aria-label="Sync result">
      {results.map((r) => (
        <li key={r.username} className={r.status === "ok" ? "ok" : "bad"}>
          <strong>{r.username}</strong>: {r.status === "ok" ? `added ${r.added}` : STATUS_LABEL[r.status]}
          {r.error && <span className="person-error"> {r.error}</span>}
        </li>
      ))}
    </ul>
  );
}

export function People({ state, onChanged }: { state: LoadState<Person[]>; onChanged: () => void }) {
  // "all" или ник того, кого обновляем. Пока не null, все кнопки загрузки заблокированы:
  // /api/sync блокирующий и повторное нажатие запустило бы второй такой же запрос.
  const [syncing, setSyncing] = useState<string | null>(null);
  const [results, setResults] = useState<SyncResult[] | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  async function runSync(username?: string) {
    if (syncing) return;
    setSyncing(username ?? "all");
    setResults(null);
    setSyncError(null);
    try {
      const res = await sync(username);
      setResults(res.results);
      onChanged();
    } catch (err) {
      setSyncError(errText(err));
    } finally {
      setSyncing(null);
    }
  }

  return (
    <>
      <AddFriendForm onAdded={onChanged} />

      <Async
        state={state}
        isEmpty={(people) => people.length === 0}
        empty={
          <Empty title="Nobody here yet">Add a friend by their Last.fm username using the form above.</Empty>
        }
      >
        {(people) => (
          <section>
            <div className="sync-bar">
              <button type="button" className="btn primary" onClick={() => runSync()} disabled={syncing !== null}>
                {syncing === "all" ? "Loading…" : "Sync everyone"}
              </button>
            </div>
            {syncing && <Loading text="Loading plays from Last.fm. This can take up to a minute, please keep the page open." />}
            {syncError && (
              <p className="form-error" role="alert">
                {syncError}
              </p>
            )}
            {results && <SyncResults results={results} />}
            <ul className="people">
              {people.map((p) => (
                <PersonRow
                  key={p.username}
                  p={p}
                  locked={syncing !== null}
                  onSync={() => runSync(p.username)}
                  onDeleted={onChanged}
                />
              ))}
            </ul>
          </section>
        )}
      </Async>
    </>
  );
}
