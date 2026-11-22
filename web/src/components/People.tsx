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
      setError("Ник Last.fm состоит из букв, цифр, дефиса и подчёркивания, без пробелов.");
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
      <h3>Добавить друга</h3>
      <p className="privacy">
        Берём артистов, названия треков и время прослушивания. Данные можно удалить в любой момент.
      </p>
      <label htmlFor="uname">Ник на Last.fm</label>
      <input id="uname" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />
      <label htmlFor="dname">Как показывать (необязательно)</label>
      <input id="dname" value={displayName} maxLength={60} onChange={(e) => setDisplayName(e.target.value)} autoComplete="off" />
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {added && (
        <p className="form-ok" role="status">
          Добавили {added}. Теперь нажмите «Синхронизировать», чтобы загрузить прослушивания.
        </p>
      )}
      <div className="row">
        <button type="submit" className="btn primary" disabled={busy || !username.trim()}>
          {busy ? "Проверяем ник…" : "Добавить"}
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
          {plural(p.plays, PLAYS)} · {p.last_synced_at ? `обновлено ${fmtDateTime(p.last_synced_at)}` : "ещё не загружали"}
        </div>
        {waiting ? (
          <span className="badge wait">ждём данные</span>
        ) : (
          <span className={`badge ${p.status}`}>{STATUS_LABEL[p.status]}</span>
        )}
        {p.status !== "ok" && p.error && <p className="person-error">{p.error}</p>}
      </div>

      {confirming ? (
        <div className="confirm" role="alertdialog" aria-label="Подтверждение удаления">
          <p>
            Удалить {p.display_name} и все прослушивания? Это нельзя отменить.
          </p>
          <div className="row">
            <button type="button" className="btn danger" onClick={remove} disabled={deleting}>
              {deleting ? "Удаляем…" : "Да, удалить"}
            </button>
            <button type="button" className="btn" onClick={() => setConfirming(false)} disabled={deleting}>
              Отмена
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
            Обновить
          </button>
          <button type="button" className="btn small" onClick={() => setConfirming(true)} disabled={locked}>
            Удалить
          </button>
        </div>
      )}
    </li>
  );
}

function SyncResults({ results }: { results: SyncResult[] }) {
  return (
    <ul className="results" aria-label="Результат синхронизации">
      {results.map((r) => (
        <li key={r.username} className={r.status === "ok" ? "ok" : "bad"}>
          <strong>{r.username}</strong>: {r.status === "ok" ? `добавлено ${r.added}` : STATUS_LABEL[r.status]}
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
          <Empty title="Пока никого нет">Добавьте друга по нику Last.fm в форме выше.</Empty>
        }
      >
        {(people) => (
          <section>
            <div className="sync-bar">
              <button type="button" className="btn primary" onClick={() => runSync()} disabled={syncing !== null}>
                {syncing === "all" ? "Загружаем…" : "Синхронизировать всех"}
              </button>
            </div>
            {syncing && <Loading text="Загружаем прослушивания с Last.fm. Это может занять до минуты, не закрывайте страницу." />}
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
