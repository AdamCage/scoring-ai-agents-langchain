import { FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EvalCase, EvalsResponse, Experiment, api, takeSseEvents } from "../api";
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
  const [phase, setPhase] = useState("");
  const [liveResults, setLiveResults] = useState<EvalCase[]>([]);
  const [error, setError] = useState("");

  const summary = evals.data?.summary || {};
  const experiments = evals.data?.experiments || [];
  const thresholds = evals.data?.thresholds || {};
  const results = liveResults.length && busy ? liveResults : evals.data?.results || liveResults;
  const metrics = Object.entries(summary).filter(([key, value]) => typeof value === "number" && !HIDDEN.has(key));
  const leftExp = experiments.find((item) => item.run_id === (left || experiments[0]?.run_id));
  const rightExp = experiments.find((item) => item.run_id === (right || experiments[1]?.run_id));
  const compareKeys = useMemo(() => {
    if (!leftExp || !rightExp) return [];
    return Array.from(new Set([...Object.keys(leftExp.summary || {}), ...Object.keys(rightExp.summary || {})]));
  }, [leftExp, rightExp]);
  const compareData = compareKeys.map((key) => ({
    metric: key,
    A: Number(leftExp?.summary[key] ?? 0),
    B: Number(rightExp?.summary[key] ?? 0),
  }));
  const failedMetrics = new Set(
    results.filter((item) => !item.passed).map((item) => `${item.case_id}:${item.metric}`),
  );

  async function onRun(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setLiveResults([]);
    setPhase("start");
    try {
      const response = await fetch("/api/evals/stream", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ experiment: name, smoke }),
      });
      if (!response.ok || !response.body) {
        await api<EvalsResponse>("/api/evals", {
          method: "POST",
          body: JSON.stringify({ experiment: name, smoke }),
        });
      } else {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parsed = takeSseEvents<Record<string, unknown>>(buffer);
          buffer = parsed.rest;
          for (const data of parsed.events) {
            const type = String(data.type || "");
            if (type === "eval_phase" || type === "eval_start") {
              setPhase(String(data.phase || type));
            }
            if (type === "eval_case") {
              setLiveResults((prev) => [
                ...prev,
                {
                  case_id: String(data.case_id || ""),
                  dataset: String(data.dataset || ""),
                  metric: String(data.metric || ""),
                  score: Number(data.score || 0),
                  passed: Boolean(data.passed),
                  comment: String(data.comment || ""),
                  details: (data.details as Record<string, unknown>) || {},
                },
              ]);
            }
            if (type === "eval_error") {
              setError(String(data.message || "eval failed"));
            }
          }
        }
      }
      await evals.refetch();
      setPhase("done");
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
        text="Локальный runner и quality gate. Видно каждый кейс, порог метрики и сравнение экспериментов."
      />

      {metrics.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {metrics.map(([key, value]) => {
            const score = Number(value);
            const threshold = thresholds[key];
            return (
              <article key={key} className={`tile p-5 ${key === "overall" || key === "numeric_consistency" ? "bg-yellow" : ""}`}>
                <p className="text-xs text-muted">{METRIC_HELP[key] ?? key}</p>
                <p className="mt-3 text-3xl font-semibold">{formatMetric(key, value)}</p>
                <p className="mt-1 font-mono text-[11px] text-muted">{key}</p>
                <div className="relative mt-3 h-2 rounded-full bg-canvas">
                  <div className="h-full rounded-full bg-ink" style={{ width: `${Math.min(score, 1) * 100}%` }} />
                  {threshold != null ? (
                    <span
                      className="absolute top-[-3px] h-3.5 w-0.5 bg-bad"
                      style={{ left: `${Math.min(threshold, 1) * 100}%` }}
                      title={`порог ${threshold}`}
                    />
                  ) : null}
                </div>
                {threshold != null ? (
                  <p className="mt-2 text-[11px] text-muted">порог {Math.round(threshold * 100)}%</p>
                ) : null}
              </article>
            );
          })}
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
            <input type="checkbox" checked={smoke} onChange={(e) => setSmoke(e.target.checked)} />
            Быстрый smoke: scoring, RAG и 2 агентных кейса
          </label>
          {busy ? (
            <div className="mt-4">
              <div className="mb-2 flex justify-between text-sm">
                <span>Фаза: {phase || "run"}</span>
                <span>{liveResults.length} кейсов</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-canvas">
                <div
                  className="h-full rounded-full bg-yellow transition-all"
                  style={{ width: `${Math.min(100, 8 + liveResults.length * 4)}%` }}
                />
              </div>
            </div>
          ) : null}
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
          {leftExp && rightExp && compareData.length ? (
            <div className="mt-5 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={compareData}>
                  <CartesianGrid stroke="#E4E5EA" vertical={false} />
                  <XAxis dataKey="metric" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(value) => `${Math.round(Number(value) * 100)}%`} />
                  <Bar dataKey="A" name={leftExp.experiment} fill="#000000" radius={6} />
                  <Bar dataKey="B" name={rightExp.experiment} fill="#FFCC00" radius={6} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="mt-5 text-sm text-muted">Нужны два прогона, чтобы сравнить эксперименты.</p>
          )}
        </section>
      </div>

      <section className="tile mt-4 overflow-x-auto p-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-[17px] font-semibold">Кейсы</h2>
          <TechPill>{results.length} EvalResult</TechPill>
        </div>
        {results.length === 0 ? (
          <p className="text-sm text-muted">После прогона здесь будет таблица pass/fail по каждому кейсу.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="pb-2 font-medium">Датасет</th>
                <th className="pb-2 font-medium">Кейс</th>
                <th className="pb-2 font-medium">Метрика</th>
                <th className="pb-2 font-medium">Score</th>
                <th className="pb-2 font-medium">Статус</th>
              </tr>
            </thead>
            <tbody>
              {results.map((item, index) => (
                <tr key={`${item.case_id}-${item.metric}-${index}`} className="border-t border-line">
                  <td className="py-2 text-muted">{item.dataset}</td>
                  <td className="py-2">{item.case_id}</td>
                  <td className="py-2">{item.metric}</td>
                  <td className="py-2 font-semibold">{formatMetric(item.metric, item.score)}</td>
                  <td className={`py-2 font-medium ${item.passed ? "text-ok" : "text-bad"}`}>
                    {item.passed ? "pass" : "fail"}
                    {!item.passed && item.comment ? ` · ${item.comment}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {failedMetrics.size ? (
          <p className="mt-3 text-sm text-bad">Упало метрик: {failedMetrics.size}</p>
        ) : null}
      </section>

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
