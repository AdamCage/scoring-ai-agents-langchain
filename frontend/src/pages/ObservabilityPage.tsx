import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Health, Trace, api } from "../api";
import { PageTitle, TechPill } from "../ui";

function formatMs(value: number | null | undefined) {
  if (value == null) return "—";
  if (value < 1000) return `${Math.round(value)} мс`;
  return `${(value / 1000).toFixed(1)} с`;
}

export function ObservabilityPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  const traces = useQuery({
    queryKey: ["traces"],
    queryFn: () => api<{ traces: Trace[] }>("/api/traces"),
  });
  const items = traces.data?.traces || [];
  const [selected, setSelected] = useState("");
  const current = useMemo(() => {
    return items.find((item) => item.trace_id === selected) || items[0] || null;
  }, [items, selected]);
  const spans = current?.spans || [];
  const totalMs = spans.reduce((sum, span) => sum + (span.duration_ms || 0), 0);
  const langfuse = health.data?.langfuse === "enabled" ? "enabled" : "missing";
  const langsmith = health.data?.langsmith ?? "ready_no_key";

  return (
    <div>
      <PageTitle
        kicker="Observability"
        title="Что произошло в этом прогоне"
        text="Локальные spans в SQLite — демо-лента. Langfuse OSS — on-prem traces и datasets. LangSmith — native evaluation, если задан ключ."
      />

      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Провайдер" value={health.data?.observability ?? "—"} />
        <Metric label="Langfuse" value={langfuse} />
        <Metric label="LangSmith" value={langsmith} />
        <Metric label="Сумма таймингов" value={formatMs(current ? totalMs : null)} />
      </div>

      <div className="mt-4 flex flex-wrap gap-3 text-sm">
        {health.data?.langfuse_url ? (
          <a className="underline" href={health.data.langfuse_url} target="_blank" rel="noreferrer">
            Open Langfuse
          </a>
        ) : (
          <span className="text-muted">Langfuse URL появится, когда заданы HOST и ключи проекта.</span>
        )}
        {health.data?.langsmith_experiment?.url ? (
          <a className="underline" href={health.data.langsmith_experiment.url} target="_blank" rel="noreferrer">
            Open LangSmith Experiment ↗
          </a>
        ) : health.data?.langsmith_url ? (
          <a className="underline" href={health.data.langsmith_url} target="_blank" rel="noreferrer">
            Open LangSmith
          </a>
        ) : (
          <span className="text-muted">LangSmith Evaluation готов, ключ не задан — status ready_no_key.</span>
        )}
      </div>

      <section className="tile mt-6 p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-[17px] font-semibold">История операций</h2>
            <p className="mt-1 text-sm text-muted">Duration считается по стене: span стартует до тела node.</p>
          </div>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted">Прогон</span>
            <select
              className="min-w-[240px]"
              value={current?.trace_id || ""}
              onChange={(e) => setSelected(e.target.value)}
            >
              {items.length === 0 ? <option value="">Пока пусто</option> : null}
              {items.map((item) => (
                <option key={item.trace_id} value={item.trace_id}>
                  {item.name} · {formatMs(item.duration_ms)} · {item.status}
                </option>
              ))}
            </select>
          </label>
        </div>

        {traces.isError ? <p className="mt-4 text-sm text-bad">Не удалось загрузить traces</p> : null}

        {spans.length === 0 ? (
          <p className="mt-8 text-sm text-muted">Прогоните заявку на вкладке «Заявка» — здесь появится trace.</p>
        ) : (
          <ol className="mt-6 space-y-3">
            {spans.map((span, index) => (
              <li key={span.span_id} className="flex items-start gap-4 rounded-2xl bg-canvas px-4 py-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-sm font-semibold shadow-tile">
                  {index + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold">{span.name}</p>
                    <p className="text-sm text-muted">{formatMs(span.duration_ms)}</p>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
                    <TechPill>{span.kind}</TechPill>
                    {span.mmd_node ? <TechPill>{span.mmd_node}</TechPill> : null}
                    {span.events.length ? (
                      <span className="rounded-full bg-white px-2.5 py-1">{span.events.map((event) => event.name).join(" → ")}</span>
                    ) : null}
                    {span.error ? <span className="rounded-full bg-red-50 px-2.5 py-1 text-bad">{span.error}</span> : null}
                  </div>
                  {span.events.some((event) => event.payload && Object.keys(event.payload).length) ? (
                    <p className="mt-2 font-mono text-[11px] text-muted">
                      {span.events
                        .filter((event) => event.payload?.ids)
                        .map((event) => `${event.name}: ${Array.isArray(event.payload?.ids) ? event.payload?.ids.slice(0, 3).join(", ") : ""}`)
                        .join(" · ")}
                    </p>
                  ) : null}
                  {span.code_path ? <p className="mt-2 font-mono text-[11px] text-muted">{span.code_path}</p> : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <article className="tile p-5">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </article>
  );
}
