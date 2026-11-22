import { useEffect, useState } from "react";
import { setUnauthorizedHandler } from "./api";
import { clearToken, getToken } from "./auth";
import { Dashboard } from "./components/Dashboard";
import { FriendPage } from "./components/FriendPage";
import { Landing } from "./components/Landing";

type View = "landing" | "friend" | "dashboard";

export function App() {
  const [view, setView] = useState<View>(() => (getToken() ? "dashboard" : "landing"));
  const [notice, setNotice] = useState<string | null>(null);

  // Если сервер ответил 401 (токен истёк или сервер перезапущен), возвращаем на вход.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setNotice("Сессия закончилась. Войдите снова.");
      setView("landing");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  function logout() {
    clearToken();
    setNotice(null);
    setView("landing");
  }

  if (view === "friend") return <FriendPage onBack={() => setView("landing")} />;
  if (view === "dashboard") return <Dashboard onLogout={logout} />;
  return (
    <Landing
      notice={notice}
      onFriend={() => setView("friend")}
      onLoggedIn={() => {
        setNotice(null);
        setView("dashboard");
      }}
    />
  );
}
