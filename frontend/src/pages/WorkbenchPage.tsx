import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Application, Preset, SSEEvent, api } from "../api";
import { PageTitle, TechPill } from "../ui";

const emptyApp: Application = {
  application_id: "CUSTOM",
  company_name: "",
  segment: "sme",
  industry: "wholesale",
  region: "moscow",
  company_age_months: 36,
  annual_revenue: 50_000_000,
  revenue_growth: 0.08,
  ebitda_margin: 0.12,
  debt_to_revenue: 0.4,
  requested_amount: 10_000_000,
  requested_term: 24,
  credit_history_months: 24,
  overdue_30d_count: 0,
  overdue_90d_count: 0,
  bureau_score: 720,
  existing_loans_count: 1,
  industry_risk: 0.3,
  region_risk: 0.2,
};

const STEPS: { node: string; label: string; tech: string }[] = [
  { node: "validate_application", label: "Проверка", tech: "LangGraph" },
  { node: "calculate_score", label: "Скоринг", tech: "CatBoost" },
  { node: "explain_score", label: "SHAP", tech: "Tool" },
  { node: "retrieve_policy", label: "Политика", tech: "RAG" },
  { node: "risk_analysis", label: "Аналитик", tech: "LLM" },
  { node: "policy_critic", label: "Критик", tech: "LLM" },
  { node: "synthesize", label: "Решение", tech: "LangGraph" },
];

function money(value: number) {
  return new Intl.NumberFormat("ru-RU").format(Math.round(value));
}

function fmtScore(value: unknown) {
  if (value == null || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3) : String(value);
}

export function WorkbenchPage() {
  const presets = useQuery({
    queryKey: ["presets"],
    queryFn: () => api<{ presets: Preset[] }>("/api/applications/presets"),
  });
  const [app, setApp] = useState<Application>(emptyApp);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [chat, setChat] = useState("");
  const [chatLog, setChatLog] = useState<{ q: string; a: string }[]>([]);
  const [amount, setAmount] = useState(10_000_000);
  const [whatIf, setWhatIf] = useState<Record<string, unknown> | null>(null);

  const timeline = useMemo(() => {
    const seen: Record<string, string> = {};
    for (const event of events) {
      if (!event.node) continue;
      if (event.type === "node_start") seen[event.node] = "running";
      if (event.type === "node_end") seen[event.node] = "done";
    }
    return STEPS.map((step) => ({ ...step, status: seen[step.node] || "idle" }));
  }, [events]);

  async function analyze() {
    setBusy(true);
    setEvents([]);
    setDone(null);
    setWhatIf(null);
    setChatLog([]);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ application: app }),
      });
      if (!response.ok || !response.body) throw new Error("analyze failed");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done: finished } = await reader.read();
        if (finished) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";
        for (const chunk of chunks) {
          const dataLine = chunk.split("\n").find((line) => line.startsWith("data:"));
          if (!dataLine) continue;
          const event = JSON.parse(dataLine.slice(5)) as SSEEvent;
          setEvents((prev) => [...prev, event]);
          if (event.run_id) setRunId(event.run_id);
          if (event.type === "done") setDone(event.data);
        }
      }
    } finally {
      setBusy(false);
    }
  }

  async function sendChat() {
    if (!runId || !chat.trim()) return;
    const result = await api<{ answer: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ run_id: runId, message: chat }),
    });
    setChatLog((prev) => [...prev, { q: chat, a: result.answer }]);
    setChat("");
  }

  async function runWhatIf() {
    const result = await api<Record<string, unknown>>("/api/what-if", {
      method: "POST",
      body: JSON.stringify({ application: app, overrides: { requested_amount: amount } }),
    });
    setWhatIf(result);
  }

  const scoring = (done?.scoring || {}) as Record<string, string | number>;
  const rec = (done?.recommendation || {}) as Record<string, string>;
  const shap = ((done?.shap as Record<string, unknown>)?.features || []) as {
    label: string;
    shap_value: number;
  }[];
  const docs = (done?.documents || []) as { citation: string; text: string }[];
  const decision = String(scoring.decision || rec.title || "").toUpperCase();
  const approved = decision === "APPROVE" || decision.includes("ОДОБР");
  const maxShap = Math.max(...shap.slice(0, 5).map((item) => Math.abs(item.shap_value)), 0.01);

  return (
    <div>
      <PageTitle
        kicker="Демо для интервью"
        title="Разбор кредитной заявки"
        text="Модель считает score. Агенты LangGraph объясняют и цитируют политику. Каждый шаг пишется в trace и проверяется evals."
      />

      <div className="mb-5 grid gap-3 md:grid-cols-3">
        <Link className="tile p-4" to="/architecture">
          <p className="text-xs text-muted">1 · LangChain</p>
          <p className="mt-1 text-[16px] font-semibold">Граф и tools</p>
          <p className="mt-1 text-sm text-muted">CatBoost пишет score. LLM только объясняет.</p>
        </Link>
        <Link className="tile p-4" to="/observability">
          <p className="text-xs text-muted">2 · Observability</p>
          <p className="mt-1 text-[16px] font-semibold">Локальные spans</p>
          <p className="mt-1 text-sm text-muted">SQLite-трейсы без LangSmith и Langfuse.</p>
        </Link>
        <Link className="tile p-4" to="/quality">
          <p className="text-xs text-muted">3 · Evaluation</p>
          <p className="mt-1 text-[16px] font-semibold">Quality gate</p>
          <p className="mt-1 text-sm text-muted">Цитаты, RAG hit-rate и целостность скора.</p>
        </Link>
      </div>

      <div className="-mx-1 flex gap-2 overflow-x-auto pb-3">
        {(presets.data?.presets || []).map((preset) => {
          const active = app.application_id === preset.application.application_id;
          return (
            <button
              key={preset.id}
              className={`min-w-[168px] rounded-tile px-4 py-3 text-left ${
                active ? "bg-yellow" : "bg-white shadow-tile"
              }`}
              onClick={() => {
                setApp(preset.application);
                setAmount(preset.application.requested_amount);
              }}
            >
              <div className="text-[15px] font-semibold">{preset.title}</div>
              <div className="mt-1 text-xs text-muted">{preset.subtitle}</div>
            </button>
          );
        })}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[280px_1fr]">
        <section className="tile p-5">
          <h2 className="text-[17px] font-semibold">Заявка</h2>
          <label className="mt-4 block text-sm text-muted">Компания</label>
          <input
            className="mt-1"
            value={app.company_name}
            onChange={(e) => setApp({ ...app, company_name: e.target.value })}
          />
          <label className="mt-3 block text-sm text-muted">Выручка, ₽</label>
          <input
            className="mt-1"
            type="number"
            value={app.annual_revenue}
            onChange={(e) => setApp({ ...app, annual_revenue: Number(e.target.value) })}
          />
          <label className="mt-3 block text-sm text-muted">Сумма кредита, ₽</label>
          <input
            className="mt-1"
            type="number"
            value={app.requested_amount}
            onChange={(e) => {
              const value = Number(e.target.value);
              setApp({ ...app, requested_amount: value });
              setAmount(value);
            }}
          />
          <label className="mt-3 block text-sm text-muted">Долговая нагрузка</label>
          <input
            className="mt-1"
            type="number"
            step="0.01"
            value={app.debt_to_revenue}
            onChange={(e) => setApp({ ...app, debt_to_revenue: Number(e.target.value) })}
          />
          <button className="btn-yellow mt-5 w-full" disabled={busy} onClick={analyze}>
            {busy ? "Считаем…" : "Проанализировать"}
          </button>
        </section>

        <div className="grid gap-4">
          <section
            className={`rounded-tile p-6 shadow-tile ${
              approved ? "bg-yellow" : "bg-white"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm text-muted">{app.company_name || "Выберите клиента"}</p>
                <h2 className="mt-1 text-[34px] font-semibold leading-none">
                  {rec.title || (busy ? "Анализ" : "Ждём заявку")}
                </h2>
              </div>
              <TechPill>score пишет только CatBoost</TechPill>
            </div>
            <div className="mt-6 grid grid-cols-3 gap-3">
              <div>
                <div className="text-sm text-muted">Score</div>
                <div className="text-[28px] font-semibold">{fmtScore(scoring.score)}</div>
              </div>
              <div>
                <div className="text-sm text-muted">Риск</div>
                <div className="text-[28px] font-semibold">{scoring.risk_band ?? "—"}</div>
              </div>
              <div>
                <div className="text-sm text-muted">PD</div>
                <div className="text-[28px] font-semibold">{fmtScore(scoring.pd)}</div>
              </div>
            </div>
            {rec.summary && <p className="mt-4 max-w-3xl text-[15px] leading-6">{rec.summary}</p>}
          </section>

          <section className="tile p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[17px] font-semibold">Как идёт LangGraph</h3>
              <TechPill>live stream</TechPill>
            </div>
            <ol className="grid grid-cols-2 gap-2 md:grid-cols-7">
              {timeline.map((step) => (
                <li
                  key={step.node}
                  className={`rounded-2xl px-3 py-3 ${
                    step.status === "done"
                      ? "bg-ink text-white"
                      : step.status === "running"
                        ? "bg-yellow"
                        : "bg-canvas"
                  }`}
                >
                  <div className="text-[13px] font-semibold">{step.label}</div>
                  <div className={`mt-1 text-[11px] ${step.status === "done" ? "text-white/70" : "text-muted"}`}>
                    {step.tech}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section className="tile p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-[17px] font-semibold">Почему такой score</h3>
            <TechPill>SHAP</TechPill>
          </div>
          {shap.length === 0 ? (
            <p className="text-sm text-muted">После анализа здесь будут факторы модели.</p>
          ) : (
            <ul className="space-y-3">
              {shap.slice(0, 5).map((item) => (
                <li key={item.label}>
                  <div className="flex justify-between text-sm">
                    <span>{item.label}</span>
                    <span className={item.shap_value > 0 ? "text-bad" : "text-ok"}>
                      {item.shap_value > 0 ? "+" : ""}
                      {item.shap_value.toFixed(3)}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-canvas">
                    <div
                      className={`h-full rounded-full ${item.shap_value > 0 ? "bg-bad" : "bg-ok"}`}
                      style={{ width: `${(Math.abs(item.shap_value) / maxShap) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-6">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted">What-if: сумма {money(amount)} ₽</span>
              <button className="btn-ghost !py-2 text-sm" onClick={runWhatIf}>
                Пересчитать
              </button>
            </div>
            <input
              className="mt-2"
              type="range"
              min={1_000_000}
              max={80_000_000}
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
            />
            {whatIf && (
              <p className="mt-2 text-sm">
                Score {(whatIf.before as { score: number }).score} → {(whatIf.after as { score: number }).score}
              </p>
            )}
          </div>
        </section>

        <section className="tile p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-[17px] font-semibold">Основания из политики</h3>
            <TechPill>Hybrid RAG</TechPill>
          </div>
          {docs.length === 0 ? (
            <p className="text-sm text-muted">Цитаты появятся после retrieval.</p>
          ) : (
            <ul className="space-y-3">
              {docs.map((doc) => (
                <li key={doc.citation} className="rounded-2xl bg-canvas p-3">
                  <div className="text-sm font-medium">{doc.citation}</div>
                  <p className="mt-1 line-clamp-3 text-sm text-muted">{doc.text}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="tile mt-4 p-5">
        <h3 className="text-[17px] font-semibold">Спросить про решение</h3>
        <div className="mt-4 max-h-56 space-y-3 overflow-auto">
          {chatLog.map((item, idx) => (
            <div key={idx}>
              <div className="ml-auto max-w-[80%] rounded-2xl bg-ink px-4 py-2 text-sm text-white">{item.q}</div>
              <div className="mt-2 max-w-[90%] rounded-2xl bg-canvas px-4 py-2 text-sm leading-6">{item.a}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <input value={chat} onChange={(e) => setChat(e.target.value)} placeholder="Почему прошла такая нагрузка?" />
          <button className="btn" onClick={sendChat} disabled={!runId}>
            Спросить
          </button>
        </div>
      </section>
    </div>
  );
}
