import { useState } from "react";
import { getPeople, getReport, getSignups } from "../api";
import { useLoad } from "../hooks";
import { Overview } from "./Overview";
import { People } from "./People";
import { Report } from "./Report";
import { Signups } from "./Signups";

type Tab = "overview" | "people" | "signups" | "report";
const TABS: [Tab, string][] = [
  ["overview", "Overview"],
  ["people", "People"],
  ["signups", "Requests"],
  ["report", "Report"],
];

export function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>("overview");
  const people = useLoad(getPeople);
  const report = useLoad(getReport);
  const signups = useLoad(getSignups);

  // После любого изменения (добавили, удалили, синхронизировали) обновляем оба списка.
  const refresh = () => {
    people.reload();
    report.reload();
    signups.reload();
  };

  return (
    <main className="page">
      <header className="top">
        <span className="logo">Flow</span>
        <nav aria-label="Sections">
          {TABS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`tab${tab === id ? " active" : ""}`}
              aria-current={tab === id ? "page" : undefined}
              onClick={() => setTab(id)}
            >
              {label}
              {id === "signups" && signups.data && signups.data.length > 0 ? ` (${signups.data.length})` : ""}
            </button>
          ))}
        </nav>
        <button type="button" className="btn small" onClick={onLogout}>
          Sign out
        </button>
      </header>

      {tab === "overview" && <Overview state={report} />}
      {tab === "people" && <People state={people} onChanged={refresh} />}
      {tab === "signups" && <Signups state={signups} onChanged={refresh} />}
      {tab === "report" && <Report state={report} />}

      <p className="note">This page contains personal listening data. Keep it on your computer and do not commit it to git.</p>
    </main>
  );
}
