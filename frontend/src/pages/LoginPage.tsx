import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Logo } from "../ui";

export function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/auth/login", { method: "POST", body: JSON.stringify({ password }) });
      navigate("/");
    } catch {
      setError("Неверный пароль");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas p-6">
      <form onSubmit={onSubmit} className="tile w-full max-w-md p-8">
        <Logo />
        <h1 className="mt-6 text-[32px] font-semibold leading-tight">Демо лаборатории</h1>
        <p className="mt-3 text-[16px] leading-6 text-muted">
          Как в банковском приложении: заявка слева, решение крупно. Под капотом — LangChain, локальная
          observability и evaluation.
        </p>
        <div className="mt-6 grid grid-cols-3 gap-2 text-center text-xs">
          {["LangChain", "Observability", "Evaluation"].map((item) => (
            <div key={item} className="rounded-2xl bg-canvas px-2 py-3 font-medium">
              {item}
            </div>
          ))}
        </div>
        <input
          className="mt-6"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Пароль демо"
        />
        <p className="mt-2 text-xs text-muted">Для демо: creditlens-demo</p>
        {error && <p className="mt-3 text-sm text-bad">{error}</p>}
        <button className="btn-yellow mt-5 w-full" type="submit">
          Войти
        </button>
      </form>
    </div>
  );
}
