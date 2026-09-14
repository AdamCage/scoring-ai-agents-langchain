import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

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
      setError("Неверный demo-пароль");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,#16324a,transparent_45%),#0b1220] p-6">
      <form onSubmit={onSubmit} className="card w-full max-w-md p-8">
        <p className="text-xs uppercase tracking-[0.3em] text-accent">CreditLens</p>
        <h1 className="mt-3 text-3xl font-semibold">Agentic Credit Intelligence</h1>
        <p className="mt-2 text-sm text-slate-400">
          ML считает score. Агенты объясняют. Evals держат качество.
        </p>
        <label className="mt-8 block text-sm text-slate-300">Demo access</label>
        <input
          className="mt-2"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Пароль демо"
        />
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        <button className="btn mt-6 w-full" type="submit">
          Войти в лабораторию
        </button>
      </form>
    </div>
  );
}
