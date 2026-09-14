import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

type Trace = {
  trace_id: string;
  run_id: string;
  name: string;
  duration_ms?: number;
  status: string;
  metadata: Record<string, string>;
  spans: { span_id: string; name: string; kind: string; duration_ms?: number; code_path?: string; mmd_node?: string; events: { name: string }[] }[];
};

export function ObservabilityPage() {
  const traces = useQuery({
    queryKey: ["traces"],
    queryFn: () => api<{ traces: Trace[] }>("/api/traces"),
  });

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-3xl font-semibold">Observability Lab</h1>
      <p className="mt-2 text-sm text-slate-400">
        Локальный tracer на LangChain callbacks + span-дерево LangGraph. Без LangSmith и Langfuse.
      </p>
      <div className="mt-6 space-y-4">
        {(traces.data?.traces || []).map((trace) => (
          <section key={trace.trace_id} className="card p-4">
            <div className="flex flex-wrap justify-between gap-2">
              <div>
                <div className="font-semibold">{trace.name}</div>
                <div className="text-xs text-slate-400">run {trace.run_id}</div>
              </div>
              <div className="text-sm text-accent">{Math.round(trace.duration_ms || 0)} ms · {trace.status}</div>
            </div>
            <div className="mt-2 text-xs text-slate-500">
              {Object.entries(trace.metadata || {}).map(([k, v]) => `${k}=${v}`).join(" · ")}
            </div>
            <ol className="mt-3 space-y-1 text-sm">
              {trace.spans.map((span) => (
                <li key={span.span_id} className="grid grid-cols-[120px_1fr_80px] gap-2">
                  <span className="text-slate-500">{span.kind}</span>
                  <span>
                    {span.name}
                    <span className="ml-2 font-mono text-xs text-slate-500">{span.code_path}</span>
                    {span.events.length > 0 && (
                      <span className="ml-2 text-xs text-accent">{span.events.map((e) => e.name).join(" → ")}</span>
                    )}
                  </span>
                  <span className="text-right text-slate-400">{Math.round(span.duration_ms || 0)} ms</span>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}
