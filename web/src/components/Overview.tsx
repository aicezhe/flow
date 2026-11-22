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
        <Empty title="No data yet">
          Add a friend on the People tab and press Sync.
        </Empty>
      }
    >
      {(r) => {
        const s = r.summary;
        const cards: [string, string][] = [
          ["People", String(s.people)],
          ["Plays", String(s.plays)],
          ["Artists", String(s.artists)],
          ["Matrix density", `${s.density_percent.toFixed(1)}%`],
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
              Plays from {fmtDate(s.first_ts)} to {fmtDate(s.last_ts)} · report generated {fmtDateTime(r.generated_at)}
            </p>
            <p className="meta">
              Density is the share of person–artist pairs that are not empty. The higher it is, the more music friends have in common.
            </p>
          </section>
        );
      }}
    </Async>
  );
}
