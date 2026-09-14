import { FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { EvalsResponse, EvalVariant, Experiment, api } from "../api";
import { PageTitle, TechPill } from "../ui";

const METRIC_HELP: Record<string, string> = {
  overall: "Среднее по метрикам последнего прогона",
  citation_grounding: "Цитаты ответа есть среди найденных чанков",
  faithfulness: "LLM-as-a-Judge: факты опираются на score, SHAP или политику",
  citation_precision: "Доля релевантных документов в выдаче RAG",
  recall_at_5: "Сколько нужных документов попало в top-5",
  mrr: "На какой позиции первый релевантный документ",
  scoring_consistency: "Повторный вызов CatBoost даёт тот же score",
  structured_output: "Решение и risk band в допустимых значениях",
  scoring_tool_called: "LangGraph прошёл calculate_score",
  agent_tool_usage: "Risk Analyst вызвал get_score_explanation и search_credit_policy",
  trajectory_superset: "Траектория содержит обязательные узлы",
  numeric_consistency: "LLM не переписал PD и решение модели",
  expected_decision: "Решение совпало с эталоном кейса",
};

const HIDDEN = new Set(["experiments", "latency_p50", "latency_p95", "experiment"]);

const DEFAULT_VARIANTS: EvalVariant[] = [
  { name: "vector-only", retrieval: "vector", reranker: false, prompt: "risk-v1", expected_gate: "fail" },
  { name: "hybrid", retrieval: "hybrid", reranker: false, prompt: "risk-v1", expected_gate: "pass" },
  { name: "hybrid-rerank", retrieval: "hybrid-rerank", reranker: true, prompt: "risk-v1", expected_gate: "pass" },
  { name: "bad-prompt", retrieval: "hybrid-rerank", reranker: true, prompt: "bad-prompt-demo", expected_gate: "fail" },
];

function formatMetric(key: string, value: unknown) {
  if (typeof value !== "number") return "—";
  if (key.startsWith("latency")) return `${value.toFixed(1)} с`;
  return `${Math.round(value * 100)}%`;
}

export function QualityPage() {
  const evals = useQuery({
    queryKey: ["evals"],
    queryFn: () => api<EvalsResponse>("/api/evals"),
  });
  const [name, setName] = useState("hybrid-rerank");
  const [smoke, setSmoke] = useState(true);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const summary = evals.data?.summary || {};
  const experiments = evals.data?.experiments || [];
  const variants = evals.data?.variants || DEFAULT_VARIANTS;
  const byVariant = evals.data?.latest_by_variant || {};
  const metrics = Object.entries(summary).filter(([key, value]) => typeof value === "number" && !HIDDEN.has(key));
  const leftExp = experiments.find((item) => item.run_id === (left || experiments[0]?.run_id));
  const rightExp = experiments.find((item) => item.run_id === (right || experiments[1]?.run_id));
  const compareKeys = useMemo(() => {
    if (!leftExp || !rightExp) return [];
    return Array.from(new Set([...Object.keys(leftExp.summary || {}), ...Object.keys(rightExp.summary || {})]));
  }, [leftExp, rightExp]);

  async function onRun(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api<EvalsResponse>("/api/evals", {
        method: "POST",
        body: JSON.stringify({ experiment: name, smoke }),
      });
      await evals.refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось прогнать eval");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageTitle
        kicker="Experiment Lab"
        title="Сломать retrieval и увидеть quality gate"
        text="Фиксированные pipeline variants. Production gate: scoring=1, numeric=1, grounding≥0.95, Recall@5≥0.75, MRR≥0.65. Нет метрики — FAIL."
      />

      {metrics.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-5">
          {metrics.map(([key, value]) => (
            <article key={key} className={`tile p-5 ${key === "overall" || key === "numeric_consistency" ? "bg-yellow" : ""}`}>
              <p className="text-xs text-muted">{METRIC_HELP[key] ?? key}</p>
              <p className="mt-3 text-3xl font-semibold">{formatMetric(key, value)}</p>
              <p className="mt-1 font-mono text-[11px] text-muted">{key}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="tile px-6 py-10 text-sm text-muted">
          Ещё нет прогона production-варианта. Выберите hybrid-rerank и нажмите «Прогнать eval».
        </div>
      )}

      {evals.data?.gate ? (
        <div className={`tile mt-4 px-5 py-4 text-sm font-medium ${evals.data.gate.passed ? "text-ok" : "bg-red-50 text-bad"}`}>
          Quality gate · hybrid-rerank: {evals.data.gate.passed ? "PASS" : "FAIL"}
          {evals.data.gate.failed.length ? ` · ${evals.data.gate.failed.join("; ")}` : ""}
        </div>
      ) : null}

      {Object.keys(byVariant).length > 0 ? (
        <section className="tile mt-4 overflow-x-auto p-6">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[17px] font-semibold">Сравнение вариантов</h2>
            <div className="flex gap-3">
              {evals.data?.langfuse_url ? (
                <a className="text-sm underline" href={evals.data.langfuse_url} target="_blank" rel="noreferrer">
                  Open in Langfuse
                </a>
              ) : null}
              {evals.data?.langsmith_experiment?.url ? (
                <a className="text-sm underline" href={evals.data.langsmith_experiment.url} target="_blank" rel="noreferrer">
                  Open LangSmith Experiment ↗
                </a>
              ) : (
                <span className="text-xs text-muted">
                  LangSmith Evaluation · {evals.data?.langsmith_experiment?.status || "ready_no_key"}
                </span>
              )}
            </div>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="pb-2 font-medium">Experiment</th>
                <th className="pb-2 font-medium">Recall@5</th>
                <th className="pb-2 font-medium">Grounding</th>
                <th className="pb-2 font-medium">Faithfulness</th>
                <th className="pb-2 font-medium">Integrity</th>
                <th className="pb-2 font-medium">Gate</th>
              </tr>
            </thead>
            <tbody>
              {variants.map((variant) => {
                const row = byVariant[variant.name];
                const summaryRow = row?.summary || {};
                return (
                  <tr key={variant.name} className="border-t border-line">
                    <td className="py-2 font-medium">{variant.name}</td>
                    <td className="py-2">{formatMetric("recall_at_5", summaryRow.recall_at_5)}</td>
                    <td className="py-2">{formatMetric("citation_grounding", summaryRow.citation_grounding)}</td>
                    <td className="py-2">{formatMetric("faithfulness", summaryRow.faithfulness)}</td>
                    <td className="py-2">{formatMetric("numeric_consistency", summaryRow.numeric_consistency)}</td>
                    <td className={`py-2 font-semibold ${row?.gate.passed ? "text-ok" : "text-bad"}`}>
                      {row ? (row.gate.passed ? "PASS" : "FAIL") : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ) : null}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <form className="tile p-6" onSubmit={onRun}>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-[17px] font-semibold">Запустить вариант</h2>
            <TechPill>меняет pipeline</TechPill>
          </div>
          <fieldset className="mt-4 space-y-2">
            {variants.map((variant) => (
              <label key={variant.name} className="flex items-start gap-3 rounded-2xl bg-canvas px-3 py-3 text-sm">
                <input type="radio" name="variant" checked={name === variant.name} onChange={() => setName(variant.name)} />
                <span>
                  <span className="font-medium">{variant.name}</span>
                  <span className="mt-0.5 block text-xs text-muted">
                    retrieval={variant.retrieval} · prompt={variant.prompt} · expected {variant.expected_gate.toUpperCase()}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
          <label className="mt-4 flex items-center gap-3 text-sm">
            <input type="checkbox" checked={smoke} onChange={(e) => setSmoke(e.target.checked)} />
            Быстрый smoke
          </label>
          <button className="btn mt-5" disabled={busy} type="submit">
            {busy ? "Считаю…" : "Прогнать eval"}
          </button>
        </form>

        <section className="tile p-6">
          <h2 className="text-[17px] font-semibold">Сравнить A / B</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <ExperimentSelect items={experiments} value={left || experiments[0]?.run_id || ""} onChange={setLeft} />
            <ExperimentSelect items={experiments} value={right || experiments[1]?.run_id || ""} onChange={setRight} />
          </div>
          {leftExp && rightExp ? (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-muted">
                  <tr>
                    <th className="pb-2 font-medium">Метрика</th>
                    <th className="pb-2 font-medium">{leftExp.experiment}</th>
                    <th className="pb-2 font-medium">{rightExp.experiment}</th>
                  </tr>
                </thead>
                <tbody>
                  {compareKeys.map((key) => (
                    <tr key={key} className="border-t border-line">
                      <td className="py-2">{METRIC_HELP[key] ?? key}</td>
                      <td className="py-2 font-semibold">{formatMetric(key, leftExp.summary[key])}</td>
                      <td className="py-2 font-semibold">{formatMetric(key, rightExp.summary[key])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-5 text-sm text-muted">Нужны два прогона, чтобы сравнить эксперименты.</p>
          )}
        </section>
      </div>

      {experiments.length > 0 ? (
        <section className="tile mt-4 p-6">
          <h2 className="text-[17px] font-semibold">История экспериментов</h2>
          <ul className="mt-3 divide-y divide-line">
            {experiments.map((item) => (
              <li key={item.run_id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <div>
                  <p className="font-medium">{item.experiment}</p>
                  <p className="text-xs text-muted">{new Date(item.started_at).toLocaleString("ru-RU")}</p>
                </div>
                <p className="font-semibold">{formatMetric("overall", average(item.summary))}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {error ? <p className="mt-4 text-sm text-bad">{error}</p> : null}
    </div>
  );
}

function ExperimentSelect({
  items,
  value,
  onChange,
}: {
  items: Experiment[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {items.length === 0 ? <option value="">Нет прогонов</option> : null}
      {items.map((item) => (
        <option key={item.run_id} value={item.run_id}>
          {item.experiment}
        </option>
      ))}
    </select>
  );
}

function average(summary: Record<string, number>) {
  const values = Object.values(summary || {});
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}
