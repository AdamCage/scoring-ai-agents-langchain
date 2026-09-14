import { FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { EvalsResponse, Experiment, api } from "../api";
import { PageTitle, TechPill } from "../ui";

const METRIC_HELP: Record<string, string> = {
  overall: "Среднее по метрикам последнего прогона",
  faithfulness: "Цитаты ответа есть среди найденных чанков",
  citation_precision: "Доля релевантных документов в выдаче RAG",
  recall_at_5: "Сколько нужных документов попало в top-5",
  mrr: "На какой позиции первый релевантный документ",
  scoring_consistency: "Повторный вызов CatBoost даёт тот же score",
  structured_output: "Решение и risk band в допустимых значениях",
  required_tool_usage: "Граф вызвал scoring tool",
  trajectory_superset: "Траектория содержит обязательные узлы",
  numeric_consistency: "LLM не переписал PD и решение модели",
  expected_decision: "Решение совпало с эталоном кейса",
};

const HIDDEN = new Set(["experiments", "latency_p50", "latency_p95"]);

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
        kicker="Evaluation"
        title="Качество ответа"
        text="Локальный runner и quality gate. Интервьюеру сразу видно: цитаты, верность скору, hit-rate RAG."
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
          Ещё нет прогона. Нажмите «Прогнать eval» — smoke занимает меньше минуты и не ходит в SaaS.
        </div>
      )}

      {evals.data?.gate ? (
        <div className={`tile mt-4 px-5 py-4 text-sm font-medium ${evals.data.gate.passed ? "text-ok" : "bg-red-50 text-bad"}`}>
          Quality gate: {evals.data.gate.passed ? "пройден" : "не пройден"}
          {evals.data.gate.failed.length ? ` · ${evals.data.gate.failed.join("; ")}` : " · scoring, citations, numeric integrity"}
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <form className="tile p-6" onSubmit={onRun}>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-[17px] font-semibold">Новый эксперимент</h2>
            <TechPill>локальный runner</TechPill>
          </div>
          <label className="mt-4 block text-sm">
            <span className="mb-1 block text-xs text-muted">Имя</span>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="mt-4 flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={smoke}
              onChange={(e) => setSmoke(e.target.checked)}
            />
            Быстрый smoke: scoring, RAG и 2 агентных кейса
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
