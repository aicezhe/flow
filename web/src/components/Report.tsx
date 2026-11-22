import type { LoadState } from "../hooks";
import type { ArtistMatrix, Report as ReportData, Similarity, UserStats } from "../types";
import { fmtDate, heatStyle, plural, PLAYS } from "../format";
import { Async, Empty } from "./ui";

function BarList({ items }: { items: UserStats["top_artists"] }) {
  const max = Math.max(0, ...items.map((i) => i.plays));
  return (
    <ul className="bars">
      {items.map((i) => (
        <li key={i.artist}>
          <span className="bl" title={i.artist}>
            {i.artist}
          </span>
          <span className="bt">
            <i style={{ width: `${max ? (100 * i.plays) / max : 0}%` }} />
          </span>
          <span className="bv">{i.plays}</span>
        </li>
      ))}
    </ul>
  );
}

function HoursChart({ hours }: { hours: number[] }) {
  const max = Math.max(0, ...hours);
  return (
    <div role="img" aria-label="Прослушивания по часам суток">
      <div className="hours">
        {hours.map((n, h) => (
          <div key={h} className="hc" title={`${String(h).padStart(2, "0")}:00, ${plural(n, PLAYS)}`}>
            <i style={{ height: `${max ? (100 * n) / max : 0}%` }} />
          </div>
        ))}
      </div>
      <div className="hours-axis" aria-hidden="true">
        <span>0</span>
        <span>6</span>
        <span>12</span>
        <span>18</span>
        <span>23</span>
      </div>
    </div>
  );
}

function UserCard({ u }: { u: UserStats }) {
  return (
    <section className="user">
      <h3>{u.name}</h3>
      <p className="meta">
        {plural(u.plays, PLAYS)} · {u.artists} артистов · {u.heard_once} слушал по одному разу · {fmtDate(u.first_ts)} – {fmtDate(u.last_ts)}
      </p>
      <div className="two">
        <div>
          <h4>Топ артистов</h4>
          <BarList items={u.top_artists} />
        </div>
        <div>
          <h4>Прослушивания по часам</h4>
          <HoursChart hours={u.hours} />
        </div>
      </div>
    </section>
  );
}

function SimilarityTable({ sim }: { sim: Similarity }) {
  if (sim.users.length < 2) {
    return <p className="meta">Добавьте второго человека, чтобы увидеть, насколько совпадают вкусы.</p>;
  }
  return (
    <>
      <div className="scroll">
        <table className="mx">
          <thead>
            <tr>
              <th />
              {sim.users.map((u) => (
                <th key={u}>{u}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sim.users.map((a, i) => (
              <tr key={a}>
                <th className="l" title={a}>
                  {a}
                </th>
                {sim.users.map((b, j) => {
                  const v = sim.matrix[i]?.[j] ?? 0;
                  return (
                    <td key={b} style={heatStyle(v * 100, 100)}>
                      {Math.round(v * 100)}%
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="meta">Доля артистов, которых слушают оба человека (сходство Жаккара).</p>
    </>
  );
}

function ArtistMatrixTable({ m }: { m: ArtistMatrix }) {
  const max = Math.max(0, ...m.plays.flat());
  return (
    <div className="scroll">
      <table className="mx">
        <thead>
          <tr>
            <th />
            {m.users.map((u) => (
              <th key={u}>{u}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {m.artists.map((artist, j) => (
            <tr key={artist}>
              <th className="l" title={artist}>
                {artist}
              </th>
              {m.users.map((u, i) => {
                const v = m.plays[i]?.[j] ?? 0;
                return (
                  <td key={u} style={heatStyle(v, max)}>
                    {v || ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Report({ state }: { state: LoadState<ReportData> }) {
  return (
    <Async
      state={state}
      isEmpty={(r) => r.users.length === 0}
      empty={
        <Empty title="Отчёт пока пуст">
          Нет ни одного прослушивания. Добавьте друга на вкладке «Люди» и нажмите «Синхронизировать».
        </Empty>
      }
    >
      {(r) => (
        <>
          <h2>Люди</h2>
          {r.users.map((u) => (
            <UserCard key={u.name} u={u} />
          ))}
          <h2>Насколько похожи вкусы</h2>
          <SimilarityTable sim={r.similarity} />
          <h2>Матрица: люди и топ-{r.matrix.artists.length} артистов</h2>
          <p className="meta">В ячейке число прослушиваний, пустая ячейка значит «ни разу». Время суток указано по часовому поясу сервера.</p>
          <ArtistMatrixTable m={r.matrix} />
        </>
      )}
    </Async>
  );
}
