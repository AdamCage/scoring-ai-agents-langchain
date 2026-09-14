import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import mermaid from "mermaid";
import { api, GraphDefinition, Trace } from "../api";
import { LiveGraph } from "../components/LiveGraph";
import { statusesFromSpans } from "../graphModel";
import { PageTitle, TechPill } from "../ui";

mermaid.initialize({
  startOnLoad: false,
  theme: "neutral",
  securityLevel: "loose",
});

const STORY = [
  {
    n: "1",
    title: "LangChain / LangGraph",
    text: "Оркестратор — StateGraph. Узлы вызывают инструменты, а не «думают» вместо модели.",
  },
  {
    n: "2",
    title: "Tools",
    text: "score_application, shap_explain, rag_retrieve — детерминированные функции с typed-контрактами.",
  },
  {
    n: "3",
    title: "Observability",
    text: "Каждый узел пишет span в SQLite: тайминги, события, retrieval. Без SaaS.",
  },
  {
    n: "4",
    title: "Evaluation",
    text: "Локальный runner и quality gate: faithfulness, citation, score-integrity.",
  },
];

const TABS = [
  { id: "graph", label: "Граф", file: "langgraph-credit-flow.mmd", caption: "После скоринга SHAP и RAG идут параллельно. Critic может запросить ещё документы." },
  { id: "runtime", label: "Runtime", file: "langchain-runtime.mmd", caption: "FastAPI → StateGraph → tools / LLM / callbacks → локальный tracer и SSE." },
  { id: "obs", label: "Observability", file: "observability-pipeline.mmd", caption: "Callback пишет spans в SQLite. UI читает GET /api/traces." },
  { id: "eval", label: "Evaluation", file: "evaluation-pipeline.mmd", caption: "Датасеты → runner → метрики → quality gate. Без LangSmith." },
];

const NODES = [
  { name: "validate", role: "проверка заявки" },
  { name: "score", role: "CatBoost, неизменяемый" },
  { name: "explain", role: "SHAP + RAG параллельно" },
  { name: "risk_analysis", role: "LLM-агент" },
  { name: "critic", role: "проверка цитат" },
  { name: "synthesize", role: "черновик для человека" },
];

export function ArchitecturePage() {
  const [tab, setTab] = useState(TABS[0]);
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");
  const traces = useQuery({
    queryKey: ["traces-mini"],
    queryFn: () => api<{ traces: Trace[] }>("/api/traces"),
  });
  const definition = useQuery({
    queryKey: ["graph-definition"],
    queryFn: () => api<GraphDefinition>("/api/graph/definition"),
  });
  const last = traces.data?.traces?.[0];
  const lastStatuses = useMemo(
    () => statusesFromSpans(last?.spans || [], definition.data),
    [last, definition.data],
  );

  useEffect(() => {
    let cancelled = false;
    setSvg("");
    setError("");
    fetch(`/api/docs/file/architecture/${tab.file}`, { credentials: "include" })
      .then((response) => {
        if (!response.ok) throw new Error("Схема недоступна");
        return response.text();
      })
      .then((text) => mermaid.render(`creditlens-${tab.id}-${Date.now()}`, text))
      .then((out) => {
        if (!cancelled) setSvg(out.svg);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [tab]);

  return (
    <div>
      <PageTitle
        kicker="LangChain"
        title="Как устроен граф"
        text="Скоринг считает CatBoost. Агенты только объясняют. Это то, что нужно показать на собеседовании."
      />

      <div className="grid gap-3 md:grid-cols-4">
        {STORY.map((item) => (
          <article key={item.n} className="tile p-5">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-yellow text-sm font-bold">
              {item.n}
            </div>
            <h2 className="mt-4 text-[16px] font-semibold">{item.title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted">{item.text}</p>
          </article>
        ))}
      </div>

      <section className="tile mt-6 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[17px] font-semibold">Схема из репозитория</h2>
          <TechPill>те же .mmd, что в docs/</TechPill>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {TABS.map((item) => (
            <button
              key={item.id}
              className={item.id === tab.id ? "btn !rounded-full !px-4 !py-2 text-sm" : "btn-ghost !rounded-full !px-4 !py-2 text-sm"}
              onClick={() => setTab(item)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
        <p className="mt-4 max-w-2xl text-sm text-muted">{tab.caption}</p>
        <div className="mt-5 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {NODES.map((node) => (
            <div key={node.name} className="rounded-2xl bg-canvas px-3 py-3">
              <p className="font-mono text-xs font-semibold">{node.name}</p>
              <p className="mt-1 text-[12px] text-muted">{node.role}</p>
            </div>
          ))}
        </div>
        {error ? <p className="mt-4 text-sm text-bad">{error}</p> : null}
        {svg ? (
          <div className="mermaid-wrap mt-5 overflow-x-auto rounded-2xl bg-canvas p-4" dangerouslySetInnerHTML={{ __html: svg }} />
        ) : (
          <p className="mt-5 text-sm text-muted">Рисую схему…</p>
        )}
      </section>

      <section className="tile mt-6 p-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-[17px] font-semibold">Последний прогон на графе</h2>
            <p className="mt-1 text-sm text-muted">Та же mermaid-схема, что на заявке: узлы из последнего trace подсвечены.</p>
          </div>
          <TechPill>live graph</TechPill>
        </div>
        <LiveGraph definition={definition.data} statuses={lastStatuses} />
      </section>

      <section className="tile mt-6 p-6">
        <h2 className="text-[17px] font-semibold">Последний run</h2>
        <p className="mt-1 text-sm text-muted">Spans с code path — доказательство, что граф реально отработал.</p>
        {last ? (
          <ol className="mt-4 grid gap-2 md:grid-cols-2">
            {last.spans.map((span, index) => (
              <li key={span.span_id} className="rounded-2xl bg-canvas px-4 py-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">
                    {index + 1}. {span.name}
                  </p>
                  <span className="text-xs text-muted">{Math.round(span.duration_ms || 0)} мс</span>
                </div>
                <p className="mt-1 font-mono text-[11px] text-muted">{span.code_path || span.kind}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-4 text-sm text-muted">Прогоните заявку — сюда подтянутся spans.</p>
        )}
      </section>

      <section className="mt-6 rounded-tile bg-ink px-6 py-6 text-white shadow-tile">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-yellow">Главное правило</p>
        <p className="mt-3 max-w-3xl text-xl font-semibold leading-8">
          LLM не пересчитывает PD и не меняет решение. ScoringResult пишет только CatBoost.
        </p>
      </section>
    </div>
  );
}
