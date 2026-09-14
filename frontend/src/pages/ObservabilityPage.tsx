import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Health, Span, Trace, api } from "../api";
import { PageTitle, TechPill } from "../ui";

const KINDS = ["all", "graph", "chain", "retriever", "tool", "llm"] as const;

function formatMs(value: number | null | undefined) {
  if (value == null) return "—";
  if (value < 1000) return `${Math.round(value)} мс`;
  return `${(value / 1000).toFixed(1)} с`;
}

function spanStart(span: Span): number {
  return span.started_at ? new Date(span.started_at).getTime() : 0;
}

function spanEnd(span: Span): number {
  if (span.ended_at) return new Date(span.ended_at).getTime();
  if (span.started_at && span.duration_ms) return new Date(span.started_at).getTime() + span.duration_ms;
  return spanStart(span);
}

function depthOf(span: Span, byId: Map<string, Span>): number {
  let depth = 0;
  let current = span;
  const guard = new Set<string>();
  while (current.parent_span_id && !guard.has(current.span_id)) {
    guard.add(current.span_id);
    const parent = byId.get(current.parent_span_id);
    if (!parent) break;
    depth += 1;
    current = parent;
  }
  return depth;
}

export function ObservabilityPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  const traces = useQuery({
    queryKey: ["traces"],
    queryFn: () => api<{ traces: Trace[] }>("/api/traces"),
  });
  const items = traces.data?.traces || [];
  const [selected, setSelected] = useState("");
  const [kind, setKind] = useState<(typeof KINDS)[number]>("all");
  const [open, setOpen] = useState<string>("");
  const current = useMemo(() => {
    return items.find((item) => item.trace_id === selected) || items[0] || null;
  }, [items, selected]);
  const spans = current?.spans || [];
  const visible = spans.filter((span) => kind === "all" || span.kind === kind);
  const totalMs = spans.reduce((sum, span) => sum + (span.duration_ms || 0), 0);
  const byId = useMemo(() => new Map(spans.map((span) => [span.span_id, span])), [spans]);
  const t0 = Math.min(...spans.map(spanStart), Date.now());
  const t1 = Math.max(...spans.map(spanEnd), t0 + 1);
  const windowMs = Math.max(t1 - t0, 1);
  const generations = spans.flatMap((span) => span.generations || []);

  return (
    <div>
      <PageTitle
        kicker="Observability"
        title="Что произошло в этом прогоне"
        text="Локальный waterfall в SQLite: дерево spans, RAG payload, LLM generations. Без LangSmith и Langfuse."
      />

      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Провайдер" value={health.data?.observability ?? "—"} />
        <Metric label="LangSmith / Langfuse" value="выключены" />
        <Metric label="Прогонов" value={String(items.length)} />
        <Metric label="LLM generations" value={String(generations.length)} />
      </div>

      <section className="tile mt-6 p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-[17px] font-semibold">Waterfall</h2>
            <p className="mt-1 text-sm text-muted">
              {current ? `${current.name} · ${formatMs(current.duration_ms)} · сумма узлов ${formatMs(totalMs)}` : "Нет прогона"}
            </p>
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

        <div className="mt-4 flex flex-wrap gap-2">
          {KINDS.map((item) => (
            <button
              key={item}
              type="button"
              className={item === kind ? "btn !rounded-full !px-4 !py-2 text-sm" : "btn-ghost !rounded-full !px-4 !py-2 text-sm"}
              onClick={() => setKind(item)}
            >
              {item}
            </button>
          ))}
        </div>

        {traces.isError ? <p className="mt-4 text-sm text-bad">Не удалось загрузить traces</p> : null}

        {visible.length === 0 ? (
          <p className="mt-8 text-sm text-muted">Прогоните заявку на вкладке «Заявка» — здесь появится waterfall.</p>
        ) : (
          <ol className="mt-6 space-y-2">
            {visible.map((span) => {
              const left = ((spanStart(span) - t0) / windowMs) * 100;
              const width = Math.max(((spanEnd(span) - spanStart(span)) / windowMs) * 100, 1.5);
              const depth = depthOf(span, byId);
              const expanded = open === span.span_id;
              return (
                <li key={span.span_id}>
                  <button
                    type="button"
                    className="w-full rounded-2xl bg-canvas px-4 py-3 text-left"
                    style={{ marginLeft: depth * 12 }}
                    onClick={() => setOpen(expanded ? "" : span.span_id)}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold">{span.name}</p>
                      <p className="text-sm text-muted">{formatMs(span.duration_ms)}</p>
                    </div>
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
                      <div
                        className={`h-full rounded-full ${span.kind === "tool" ? "bg-yellow" : "bg-ink"}`}
                        style={{ marginLeft: `${left}%`, width: `${width}%` }}
                      />
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
                      <TechPill>{span.kind}</TechPill>
                      {span.mmd_node ? <TechPill>{span.mmd_node}</TechPill> : null}
                      {span.events.length ? (
                        <span className="rounded-full bg-white px-2.5 py-1">
                          {span.events.map((event) => event.name).join(" → ")}
                        </span>
                      ) : null}
                      {(span.generations || []).length ? <span className="rounded-full bg-white px-2.5 py-1">llm</span> : null}
                    </div>
                  </button>
                  {expanded ? <SpanDetails span={span} /> : null}
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}

function SpanDetails({ span }: { span: Span }) {
  return (
    <div className="mt-2 rounded-2xl bg-white px-4 py-4 shadow-tile">
      {span.code_path ? <p className="font-mono text-[11px] text-muted">{span.code_path}</p> : null}
      {span.error ? <p className="mt-2 text-sm text-bad">{span.error}</p> : null}
      {span.events.map((event, index) => (
        <div key={`${event.name}-${index}`} className="mt-3 rounded-2xl bg-canvas px-3 py-3">
          <p className="text-sm font-semibold">{event.name}</p>
          {event.payload && Object.keys(event.payload).length ? (
            <pre className="mt-2 overflow-x-auto text-[11px] leading-5 text-muted">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          ) : null}
        </div>
      ))}
      {(span.generations || []).map((generation, index) => (
        <div key={`${generation.span_id}-${index}`} className="mt-3 rounded-2xl bg-yellow/40 px-3 py-3">
          <p className="text-sm font-semibold">generation · {generation.model}</p>
          <p className="mt-1 text-xs text-muted">
            prompt {generation.prompt_tokens} · completion {generation.completion_tokens}
          </p>
          {generation.input_preview ? (
            <p className="mt-2 line-clamp-4 text-[12px] text-muted">{generation.input_preview}</p>
          ) : null}
          {generation.output_preview ? (
            <p className="mt-2 line-clamp-6 text-sm leading-6">{generation.output_preview}</p>
          ) : null}
        </div>
      ))}
      {!span.events.length && !(span.generations || []).length ? (
        <p className="mt-2 text-sm text-muted">Нет payload — узел без retrieval/LLM.</p>
      ) : null}
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
