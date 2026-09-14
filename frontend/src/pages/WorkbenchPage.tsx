import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Application, Preset, SSEEvent, api } from "../api";

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

const NODE_LABELS: Record<string, string> = {
  validate_application: "Validation",
  calculate_score: "Scoring",
  explain_score: "SHAP",
  retrieve_policy: "Policy search",
  retrieve_more: "Retrieve more",
  risk_analysis: "Risk Analyst",
  policy_critic: "Critic",
  synthesize: "Final",
  human_review: "Human review",
  request_information: "Need data",
};

type Tab = "app" | "ai" | "risk" | "kb";

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
  const [tab, setTab] = useState<Tab>("app");
  const [amount, setAmount] = useState(10_000_000);
  const [whatIf, setWhatIf] = useState<Record<string, unknown> | null>(null);

  const timeline = useMemo(() => {
    const seen: Record<string, { status: string; ms?: number }> = {};
    for (const event of events) {
      if (!event.node) continue;
      if (event.type === "node_start") seen[event.node] = { status: "running" };
      if (event.type === "node_end") seen[event.node] = { status: "done" };
    }
    return Object.keys(NODE_LABELS).map((node) => ({
      node,
      label: NODE_LABELS[node],
      status: seen[node]?.status || "idle",
    }));
  }, [events]);

  async function analyze() {
    setBusy(true);
    setEvents([]);
    setDone(null);
    setWhatIf(null);
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

  const scoring = (done?.scoring || {}) as Record<string, unknown>;
  const rec = (done?.recommendation || {}) as Record<string, unknown>;
  const shap = ((done?.shap as Record<string, unknown>)?.features || []) as {
    label: string;
    shap_value: number;
  }[];
  const docs = (done?.documents || []) as { citation: string; text: string; section: string }[];

  return (
    <div className="grid min-h-[calc(100vh-61px)] lg:grid-cols-[320px_1fr_320px]">
      <aside className={`border-r border-line p-4 ${tab !== "app" ? "hidden lg:block" : ""}`}>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Заявка</h2>
        <div className="mt-3 grid gap-2">
          {(presets.data?.presets || []).map((preset) => (
            <button
              key={preset.id}
              className="btn-ghost text-left"
              onClick={() => {
                setApp(preset.application);
                setAmount(preset.application.requested_amount);
              }}
            >
              <div className="font-medium">{preset.title}</div>
              <div className="text-xs text-slate-400">{preset.subtitle}</div>
            </button>
          ))}
        </div>
        <div className="mt-4 grid gap-2 text-sm">
          <input
            value={app.company_name}
            onChange={(e) => setApp({ ...app, company_name: e.target.value })}
            placeholder="Название"
          />
          <label className="text-xs text-slate-400">Выручка, ₽</label>
          <input
            type="number"
            value={app.annual_revenue}
            onChange={(e) => setApp({ ...app, annual_revenue: Number(e.target.value) })}
          />
          <label className="text-xs text-slate-400">Сумма кредита, ₽</label>
          <input
            type="number"
            value={app.requested_amount}
            onChange={(e) => {
              const value = Number(e.target.value);
              setApp({ ...app, requested_amount: value });
              setAmount(value);
            }}
          />
          <label className="text-xs text-slate-400">Долговая нагрузка</label>
          <input
            type="number"
            step="0.01"
            value={app.debt_to_revenue}
            onChange={(e) => setApp({ ...app, debt_to_revenue: Number(e.target.value) })}
          />
        </div>
        <button className="btn mt-4 w-full" disabled={busy} onClick={analyze}>
          {busy ? "Анализ..." : "Проанализировать заявку"}
        </button>
      </aside>

      <main className={`min-w-0 p-4 ${tab !== "ai" ? "hidden lg:block" : ""}`}>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400">Applicant</div>
            <h1 className="text-2xl font-semibold">{app.company_name || "Новая заявка"}</h1>
          </div>
          <div className="text-right text-xs text-slate-400">RUN {runId?.slice(0, 8) || "—"}</div>
        </div>
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-slate-300">Agent workspace</h3>
          <ol className="mt-3 space-y-2">
            {timeline.map((item) => (
              <li key={item.node} className="flex items-center justify-between text-sm">
                <span>
                  {item.status === "done" ? "✓" : item.status === "running" ? "●" : "○"} {item.label}
                </span>
                <span className="font-mono text-xs text-slate-500">{item.node}</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="card mt-4 p-4">
          <h3 className="text-sm font-semibold">Диалог по заявке</h3>
          <div className="mt-3 max-h-56 space-y-3 overflow-auto text-sm">
            {chatLog.map((item, idx) => (
              <div key={idx}>
                <p className="text-accent">{item.q}</p>
                <p className="text-slate-300">{item.a}</p>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <input value={chat} onChange={(e) => setChat(e.target.value)} placeholder="Почему такая долговая нагрузка?" />
            <button className="btn" onClick={sendChat} disabled={!runId}>
              Спросить
            </button>
          </div>
        </div>
      </main>

      <aside className={`border-l border-line p-4 ${tab !== "risk" && tab !== "kb" ? "hidden lg:block" : ""}`}>
        <div className={tab === "kb" ? "hidden lg:block" : ""}>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Risk</h2>
          <div className="mt-3">
            <div className="text-4xl font-semibold">{String(scoring.score ?? "—")}</div>
            <div className="text-sm text-accent">{String(rec.title || scoring.risk_band || "ожидание")}</div>
            <p className="mt-2 text-sm text-slate-400">{String(rec.summary || "")}</p>
          </div>
          {shap.length > 0 && (
            <div className="mt-4 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={shap.slice(0, 6)} layout="vertical">
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="label" width={110} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="shap_value" fill="#3dd6c6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="mt-4">
            <div className="text-xs text-slate-400">What if: сумма кредита</div>
            <input
              type="range"
              min={1_000_000}
              max={80_000_000}
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
            />
            <div className="flex items-center justify-between text-xs">
              <span>{(amount / 1_000_000).toFixed(1)} млн</span>
              <button className="btn-ghost" onClick={runWhatIf}>
                Пересчитать
              </button>
            </div>
            {whatIf && (
              <p className="mt-2 text-sm">
                Score {(whatIf.before as { score: number }).score} → {(whatIf.after as { score: number }).score}
              </p>
            )}
          </div>
        </div>
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-slate-300">Sources</h3>
          <ul className="mt-2 space-y-2 text-xs text-slate-400">
            {docs.map((doc) => (
              <li key={doc.citation} className="rounded-lg border border-line p-2">
                <div className="text-accent">{doc.citation}</div>
                <div className="line-clamp-4">{doc.text}</div>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <nav className="fixed inset-x-0 bottom-0 grid grid-cols-4 border-t border-line bg-ink lg:hidden">
        {[
          ["app", "Заявка"],
          ["ai", "AI"],
          ["risk", "Risk"],
          ["kb", "KB"],
        ].map(([id, label]) => (
          <button key={id} className={`py-3 text-sm ${tab === id ? "text-accent" : "text-slate-400"}`} onClick={() => setTab(id as Tab)}>
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}
