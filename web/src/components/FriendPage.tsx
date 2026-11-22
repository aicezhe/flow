// Страница для друзей: инструкция статичная; единственный запрос к API это отправка заявки (SignupForm).
import { SignupForm } from "./SignupForm";

const STEPS: { title: string; text: string }[] = [
  {
    title: "Зарегистрируйся на last.fm",
    text: "Это бесплатно и занимает две минуты. Last.fm записывает, какую музыку ты слушаешь.",
  },
  {
    title: "Подключи Spotify",
    text: "В настройках Last.fm открой раздел «Applications» (адрес last.fm/settings/applications) и подключи Spotify. Дальше всё, что ты слушаешь, записывается само.",
  },
  {
    title: "Не скрывай недавние прослушивания",
    text: "Открой в настройках Last.fm раздел приватности и проверь, что недавние прослушивания не скрыты. Если они скрыты, Анна ничего не увидит.",
  },
  {
    title: "Отправь Анне свой ник",
    text: "Ник виден в адресе твоего профиля: last.fm/user/ТВОЙ_НИК. Скопируй его и отправь Анне.",
  },
  {
    title: "Слушай музыку как обычно",
    text: "Данные копятся несколько дней, поэтому сразу много не появится. Это нормально.",
  },
];

const INFO: { title: string; text: string }[] = [
  { title: "Что берётся", text: "Имена артистов, названия треков и время прослушивания. Больше ничего." },
  { title: "Кому показывается", text: "Только Анне." },
  { title: "Как удалить", text: "Напиши Анне, и твои данные удалят." },
  {
    title: "Если что-то не работает",
    text: "Ник виден в адресе профиля на last.fm. Если профиль закрыт, Анна не сможет увидеть данные.",
  },
];

export function FriendPage({ onBack }: { onBack: () => void }) {
  return (
    <main className="page narrow friend">
      <button type="button" className="btn small" onClick={onBack}>
        ← Назад
      </button>
      <p className="mono">Flow · для друзей</p>
      <h1>Как подключить музыку</h1>
      <p className="lead">Пять простых шагов. Всё делается один раз.</p>

      <ol className="steps">
        {STEPS.map((s, i) => (
          <li key={s.title}>
            <span className="num" aria-hidden="true">
              {i + 1}
            </span>
            <div>
              <h2>{s.title}</h2>
              <p>{s.text}</p>
            </div>
          </li>
        ))}
      </ol>

      <h2>Готов? Отправь заявку</h2>
      <SignupForm />

      <div className="info-grid">
        {INFO.map((b) => (
          <section key={b.title} className="panel">
            <h3>{b.title}</h3>
            <p>{b.text}</p>
          </section>
        ))}
      </div>
    </main>
  );
}
