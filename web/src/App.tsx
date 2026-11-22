import { useEffect, useMemo, useState } from "react";
import { setUnauthorizedHandler } from "./api";
import { clearToken, getToken } from "./auth";
import { Dashboard } from "./components/Dashboard";
import { FriendPage } from "./components/FriendPage";
import { Landing } from "./components/Landing";
import { GUEST_PATH, HOME_PATH, inviteFromUrl, navigate, usePath } from "./router";

export function App() {
  const path = usePath();
  const [loggedIn, setLoggedIn] = useState<boolean>(() => getToken() !== null);
  const [notice, setNotice] = useState<string | null>(null);
  // Код приглашения читаем один раз при входе на страницу: он нужен форме, а не маршрутизатору.
  const invite = useMemo(() => inviteFromUrl(), []);

  // Если сервер ответил 401 (токен истёк или сервер перезапущен), возвращаем на вход.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setNotice("Your session has ended. Please sign in again.");
      setLoggedIn(false);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  // Неизвестный путь ведёт на главную, не оставляя битого адреса в строке браузера.
  useEffect(() => {
    if (path !== HOME_PATH && path !== GUEST_PATH) navigate(HOME_PATH, true);
  }, [path]);

  function logout() {
    clearToken();
    setNotice(null);
    setLoggedIn(false);
  }

  if (path === GUEST_PATH) return <FriendPage invite={invite} onBack={() => navigate(HOME_PATH)} />;
  if (loggedIn) return <Dashboard onLogout={logout} />;
  return (
    <Landing
      notice={notice}
      onLoggedIn={() => {
        setNotice(null);
        setLoggedIn(true);
      }}
    />
  );
}
