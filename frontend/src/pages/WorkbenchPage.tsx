import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Application, Health, Preset, SSEEvent, api } from "../api";
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
  { node: "explain_score", label: "SHAP", tech: "parallel" },
  { node: "retrieve_policy", label: "Hybrid RAG", tech: "vector+BM25" },
  { node: "risk_analysis", label: "Risk Analyst", tech: "LangChain agent" },
  { node: "policy_critic", label: "Policy Critic", tech: "LangChain agent" },
  { node: "synthesize", label: "Synthesis", tech: "deterministic" },
  { node: "human_review", label: "Human review", tech: "interrupt" },
];

function money(value: number) {
  return new Intl.NumberFormat("ru-RU").format(Math.round(value));
}

function fmtScore(value: unknown) {
  if (value == null || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3) : String(value);
}

function formatMs(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return number < 1000 ? `${Math.round(number)} мс` : `${(number / 1000).toFixed(2)} с`;
}

async function readSSE(
  response: Response,
  onEvent: (event: SSEEvent) => void,
) {
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
      onEvent(JSON.parse(dataLine.slice(5)) as SSEEvent);
    }
  }
}

export function WorkbenchPage() {
  const presets = useQuery({
    queryKey: ["presets"],
    queryFn: () => api<{ presets: Preset[] }>("/api/applications/presets"),
  });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  const [searchParams] = useSearchParams();
  const [app, setApp] = useState<Application>(emptyApp);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [chat, setChat] = useState("");
  const [chatLog, setChatLog] = useState<{ q: string; a: string }[]>([]);
  const [amount, setAmount] = useState(10_000_000);
  const [whatIf, setWhatIf] = useState<Record<string, unknown> | null>(null);
  const [interrupt, setInterrupt] = useState<Record<string, unknown> | null>(null);
  const [inspect, setInspect] = useState<string | null>(null);
  const showcaseStarted = useRef(false);

  const timeline = useMemo(() => {
    const seen: Record<string, { status: string; duration?: number }> = {};
    for (const event of events) {
      if (!event.node) continue;
      if (event.type === "node_start") seen[event.node] = { status: "running" };
      if (event.type === "node_end") {
        seen[event.node] = { status: "done", duration: Number(event.data.duration_ms) || 0 };
      }
    }
    return STEPS.map((step) => ({ ...step, ...(seen[step.node] || { status: "idle" }) }));
  }, [events]);

  const retrieval = useMemo(() => {
    const event = [...events].reverse().find((item) => item.type === "retrieval");
    return (event?.data || done?.retrieval_debug || null) as Record<string, unknown> | null;
  }, [events, done]);

  const tools = events.filter((event) => event.type === "tool" && event.node === "risk_analysis");

  function applyEvent(event: SSEEvent) {
    setEvents((prev) => [...prev, event]);
    if (event.run_id) setRunId(event.run_id);
    if (event.type === "done") {
      setDone(event.data);
      setInterrupt(null);
    }
    if (event.type === "interrupt") setInterrupt(event.data);
  }

  async function analyze(nextApp = app) {
    setBusy(true);
    setEvents([]);
    setDone(null);
    setWhatIf(null);
    setChatLog([]);
    setInterrupt(null);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ application: nextApp }),
      });
      await readSSE(response, applyEvent);
    } finally {
      setBusy(false);
    }
  }

  async function resume(decision: string) {
    if (!runId) return;
    setBusy(true);
    try {
      const response = await fetch(`/api/runs/${runId}/resume`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      await readSSE(response, applyEvent);
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

  useEffect(() => {
    if (searchParams.get("showcase") !== "1" || showcaseStarted.current) return;
    const preset = presets.data?.presets.find((item) => item.id === "zeta-manual");
    if (!preset) return;
    showcaseStarted.current = true;
    setApp(preset.application);
    setAmount(preset.application.requested_amount);
    void analyze(preset.application);
  }, [searchParams, presets.data]);

  const scoring = (done?.scoring || {}) as Record<string, string | number>;
  const rec = (done?.recommendation || {}) as Record<string, string>;
  const shap = ((done?.shap as Record<string, unknown>)?.features || []) as {
    label: string;
    shap_value: number;
  }[];
  const docs = (done?.documents || []) as { citation: string; text: string }[];
  const analysis = (done?.analysis || {}) as Record<string, unknown>;
  const decision = String(scoring.decision || rec.title || "").toUpperCase();
  const approved = decision === "APPROVE" || decision.includes("ОДОБР");
  const maxShap = Math.max(...shap.slice(0, 5).map((item) => Math.abs(item.shap_value)), 0.01);
  const langfuseUrl = (done?.langfuse_url as string) || health.data?.langfuse_url || "";

  return (
    <div>
      <PageTitle
        kicker="Workbench"
        title="Разбор кредитной заявки"
        text="CatBoost пишет score. LangGraph оркестрирует. LangChain-агенты вызывают tools и отдают structured output. HITL — настоящий interrupt/resume."
      />

      <div className="mb-5 grid gap-3 md:grid-cols-3">
        <Link className="tile p-4" to="/architecture">
          <p className="text-xs text-muted">1 · LangChain / LangGraph</p>
          <p className="mt-1 text-[16px] font-semibold">Граф и agent runtime</p>
          <p className="mt-1 text-sm text-muted">StateGraph снаружи, create_agent внутри узлов.</p>
        </Link>
        <Link className="tile p-4" to="/observability">
          <p className="text-xs text-muted">2 · Observability</p>
          <p className="mt-1 text-[16px] font-semibold">Langfuse + SQLite</p>
          <p className="mt-1 text-sm text-muted">Тот же run в локальных spans и OSS Langfuse.</p>
        </Link>
        <Link className="tile p-4" to="/quality">
          <p className="text-xs text-muted">3 · Evaluation</p>
          <p className="mt-1 text-[16px] font-semibold">Experiment Lab</p>
          <p className="mt-1 text-sm text-muted">vector-only ломает recall, bad-prompt — grounding.</p>
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
          <button className="btn-yellow mt-5 w-full" disabled={busy} onClick={() => analyze()}>
            {busy ? "Считаем…" : "Проанализировать"}
          </button>
        </section>

        <div className="grid gap-4">
          <section className={`rounded-tile p-6 shadow-tile ${approved ? "bg-yellow" : "bg-white"}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm text-muted">{app.company_name || "Выберите клиента"}</p>
                <h2 className="mt-1 text-[34px] font-semibold leading-none">
                  {rec.title || (interrupt ? "Нужно решение аналитика" : busy ? "Анализ" : "Ждём заявку")}
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
                <div className="text-[28px] font-semibold">{String(scoring.risk_band ?? interrupt?.risk_band ?? "—")}</div>
              </div>
              <div>
                <div className="text-sm text-muted">PD</div>
                <div className="text-[28px] font-semibold">{fmtScore(scoring.pd ?? interrupt?.pd)}</div>
              </div>
            </div>
            {rec.summary && <p className="mt-4 max-w-3xl text-[15px] leading-6">{rec.summary}</p>}
            {interrupt && !done ? (
              <div className="mt-5 rounded-2xl bg-canvas p-4">
                <p className="text-sm font-semibold">LangGraph interrupt · решение кредитного аналитика</p>
                <p className="mt-1 text-sm text-muted">Граф стоит на checkpoint. Resume того же thread_id.</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="btn-yellow !py-2 text-sm" disabled={busy} onClick={() => resume("approve")}>
                    Одобрить
                  </button>
                  <button className="btn !py-2 text-sm" disabled={busy} onClick={() => resume("reject")}>
                    Отклонить
                  </button>
                  <button className="btn-ghost !py-2 text-sm" disabled={busy} onClick={() => resume("request_documents")}>
                    Запросить документы
                  </button>
                </div>
              </div>
            ) : null}
          </section>

          <section className="tile p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[17px] font-semibold">Как идёт LangGraph</h3>
              <TechPill>live stream</TechPill>
            </div>
            <ol className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {timeline.map((step) => (
                <li key={step.node}>
                  <button
                    className={`w-full rounded-2xl px-3 py-3 text-left ${
                      step.status === "done"
                        ? "bg-ink text-white"
                        : step.status === "running"
                          ? "bg-yellow"
                          : "bg-canvas"
                    }`}
                    onClick={() => setInspect(step.node)}
                    type="button"
                  >
                    <div className="text-[13px] font-semibold">{step.label}</div>
                    <div className={`mt-1 text-[11px] ${step.status === "done" ? "text-white/70" : "text-muted"}`}>
                      {step.status === "running" ? "● running" : step.status === "done" ? `✓ ${formatMs(step.duration)}` : step.tech}
                    </div>
                  </button>
                </li>
              ))}
            </ol>
            {langfuseUrl ? (
              <a className="mt-4 inline-block text-sm underline" href={langfuseUrl} target="_blank" rel="noreferrer">
                Open Langfuse trace
              </a>
            ) : null}
          </section>
        </div>
      </div>

      {inspect === "retrieve_policy" || inspect === "retrieve_more" || retrieval ? (
        <section className="tile mt-4 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-[17px] font-semibold">Hybrid RAG · стадии</h3>
            <TechPill>{String(retrieval?.mode || "hybrid-rerank")}</TechPill>
          </div>
          {retrieval ? (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
              <Stage title="QUERY" items={[String(retrieval.query || "")]} />
              <Stage title="FILTER" items={[JSON.stringify(retrieval.filters || retrieval.filters || { segment: app.segment })]} />
              <Stage title="VECTOR" items={asIds(retrieval.vector || retrieval.vector_ids)} />
              <Stage title="BM25" items={asIds(retrieval.bm25 || retrieval.bm25_ids)} />
              <Stage title="RRF / RERANK" items={[...asIds(retrieval.rrf || retrieval.fused_ids), ...asIds(retrieval.rerank || retrieval.reranked_ids)]} />
            </div>
          ) : (
            <p className="text-sm text-muted">Запустите разбор — здесь появятся id документов по стадиям.</p>
          )}
        </section>
      ) : null}

      {inspect === "risk_analysis" || analysis.summary ? (
        <section className="tile mt-4 p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-[17px] font-semibold">Risk Analyst</h3>
            <div className="flex gap-2">
              <TechPill>LangChain create_agent</TechPill>
              <TechPill>schema: RiskAnalysis</TechPill>
              <TechPill>{`tools: ${tools.length || 4}`}</TechPill>
            </div>
          </div>
          <p className="text-sm leading-6">{String(analysis.summary || rec.summary || "Агент ещё не отработал.")}</p>
        </section>
      ) : null}

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

function asIds(value: unknown) {
  return Array.isArray(value) ? value.map(String).slice(0, 5) : [];
}

function Stage({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl bg-canvas p-3">
      <p className="text-xs font-semibold text-muted">{title}</p>
      <ol className="mt-2 space-y-1 text-sm">
        {items.length === 0 ? <li className="text-muted">—</li> : items.map((item) => <li key={item} className="truncate">{item}</li>)}
      </ol>
    </div>
  );
}
