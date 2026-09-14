import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function QualityPage() {
  const evals = useQuery({
    queryKey: ["evals"],
    queryFn: () => api<{ summary: Record<string, unknown>; experiments: { experiment: string; summary: Record<string, number> }[] }>("/api/evals"),
  });
  const summary = evals.data?.summary || {};
  const metrics: [string, string][] = [
    ["Overall", String(summary.overall ?? "—")],
    ["Faithfulness", String(summary.faithfulness ?? "—")],
    ["Recall@5", String(summary.recall_at_5 ?? "—")],
    ["Citation precision", String(summary.citation_precision ?? "—")],
    ["Scoring consistency", String(summary.scoring_consistency ?? "—")],
    ["Required tools", String(summary.required_tool_usage ?? "—")],
  ];

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-3xl font-semibold">Quality Lab</h1>
      <p className="mt-2 text-sm text-slate-400">
        Локальные evals: детерминированные метрики, RAG и trajectory. Quality gate не пускает регресс в CI.
      </p>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {metrics.map(([label, value]) => (
          <div key={String(label)} className="card p-4">
            <div className="text-xs uppercase text-slate-400">{label}</div>
            <div className="mt-2 text-3xl font-semibold">{value}</div>
          </div>
        ))}
      </div>
      <section className="card mt-6 p-4">
        <h2 className="font-semibold">Experiments</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {((Array.isArray(summary.experiments) ? summary.experiments : evals.data?.experiments || []) as {
            name?: string;
            experiment?: string;
            score?: number;
            summary?: Record<string, number>;
          }[]).map((item, idx) => (
            <li key={idx} className="flex justify-between border-b border-line py-2">
              <span>{item.name || item.experiment}</span>
              <span className="text-accent">
                {String(item.score ?? (item.summary ? Object.values(item.summary)[0] : "—"))}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
