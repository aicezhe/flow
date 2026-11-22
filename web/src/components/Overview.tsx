import type { LoadState } from "../hooks";
import type { Report } from "../types";
import { fmtDate, fmtDateTime } from "../format";
import { Async, Empty } from "./ui";

export function Overview({ state }: { state: LoadState<Report> }) {
  return (
    <Async
      state={state}
      isEmpty={(r) => r.summary.plays === 0}
      empty={
        <Empty title="Пока нет данных">
          Добавьте друга на вкладке «Люди» и нажмите «Синхронизировать».
        </Empty>
      }
    >
      {(r) => {
        const s = r.summary;
        const cards: [string, string][] = [
          ["Люди", String(s.people)],
          ["Прослушивания", String(s.plays)],
          ["Артисты", String(s.artists)],
          ["Плотность матрицы", `${s.density_percent.toFixed(1)}%`],
        ];
        return (
          <section>
            <div className="cards">
              {cards.map(([k, v]) => (
                <div className="card" key={k}>
                  <div className="k">{k}</div>
                  <div className="v">{v}</div>
                </div>
              ))}
            </div>
            <p className="meta">
              Прослушивания с {fmtDate(s.first_ts)} по {fmtDate(s.last_ts)} · отчёт собран {fmtDateTime(r.generated_at)}
            </p>
            <p className="meta">
              Плотность показывает, какая доля пар «человек и артист» не пуста. Чем она выше, тем больше у друзей общей музыки.
            </p>
          </section>
        );
      }}
    </Async>
  );
}
