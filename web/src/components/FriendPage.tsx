// Страница для друзей: чеклист-таймлайн и компактная форма заявки на одном экране.
// Состояние чеклиста живёт только в компоненте и никуда не отправляется.
// Единственный запрос к API это отправка заявки (SignupForm).
import { useState } from "react";
import { SignupForm } from "./SignupForm";

interface Step {
  title: string;
  text: string;
}

const STEPS: Step[] = [
  {
    title: "Sign up on last.fm",
    text: "Free, two minutes. Last.fm records what you listen to.",
  },
  {
    title: "Connect Spotify",
    text: "In Last.fm settings open “Applications” (last.fm/settings/applications) and connect Spotify. After that everything you play is recorded automatically.",
  },
  {
    title: "Don't hide your listening",
    text: "In Last.fm privacy settings, don't hide your recent listening. Otherwise Anna can't see anything.",
  },
  {
    title: "Enter your username and send the form",
    text: "Your username is in your profile address: last.fm/user/YOUR_USERNAME. Type it into the form.",
  },
  {
    title: "Listen as usual",
    text: "Data builds up over a few days, so don't expect much at first. That's normal.",
  },
];
const SUBMIT_STEP = 3; // шаг, который отмечается сам после отправки заявки

const INFO: { title: string; text: string }[] = [
  { title: "What we collect", text: "Artist names, track titles and listening times. Nothing else." },
  { title: "Who sees it", text: "Only Anna." },
  { title: "How to delete", text: "Message Anna and your data will be deleted." },
  { title: "If something doesn't work", text: "Your username is in your profile address. If your profile is private, Anna can't see your data." },
];

function Check() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8.5l3.2 3.2L13 4.8" />
    </svg>
  );
}

function Chevron() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3.5 6l4.5 4.5L12.5 6" />
    </svg>
  );
}

export function FriendPage({ onBack, invite }: { onBack: () => void; invite: string | null }) {
  const [checked, setChecked] = useState<boolean[]>(() => STEPS.map(() => false));
  const [open, setOpen] = useState<number | null>(1); // раскрыт один шаг за раз

  const toggle = (i: number) => setChecked((c) => c.map((v, j) => (j === i ? !v : v)));
  const markSubmitted = () => setChecked((c) => c.map((v, j) => (j === SUBMIT_STEP ? true : v)));
  const done = checked.filter(Boolean).length;

  return (
    <main className="fr">
      <div className="fr-wrap">
        <header className="fr-head">
          <div className="fr-top">
            <button type="button" className="btn small" onClick={onBack}>
              ← Back
            </button>
            <span className="mono" aria-label={`Steps done: ${done} of ${STEPS.length}`}>
              {done}/{STEPS.length}
            </span>
          </div>
          <h1>How to connect your music</h1>
          <p className="fr-sub">Five steps, once.</p>
        </header>

        <ol className="fr-steps" aria-label="Connection steps">
          {STEPS.map((s, i) => (
            <li
              key={s.title}
              className={`fr-step${checked[i] ? " done" : ""}${checked[i + 1] ? " next-done" : ""}${open === i ? " open" : ""}`}
            >
              <div className="fr-row">
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={checked[i] === true}
                  className="fr-check"
                  onClick={() => toggle(i)}
                >
                  <span className="fr-dot" aria-hidden="true">
                    <Check />
                  </span>
                  <span className="fr-title">{s.title}</span>
                </button>
                <button
                  type="button"
                  className="fr-more"
                  aria-expanded={open === i}
                  aria-controls={`fr-desc-${i}`}
                  aria-label={`More: ${s.title}`}
                  onClick={() => setOpen(open === i ? null : i)}
                >
                  <Chevron />
                </button>
              </div>
              <div id={`fr-desc-${i}`} className="fr-desc" aria-hidden={open !== i}>
                <div className="fr-desc-in">
                  <p>{s.text}</p>
                </div>
              </div>
            </li>
          ))}
        </ol>

        <div className="fr-side">
          <SignupForm compact invite={invite} onSubmitted={markSubmitted} />
          <details className="fr-info">
            <summary>What we collect and how to delete</summary>
            <dl>
              {INFO.map((b) => (
                <div key={b.title}>
                  <dt>{b.title}</dt>
                  <dd>{b.text}</dd>
                </div>
              ))}
            </dl>
          </details>
        </div>
      </div>
    </main>
  );
}
