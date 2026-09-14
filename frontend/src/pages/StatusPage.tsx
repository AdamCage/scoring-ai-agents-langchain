import { useQuery } from "@tanstack/react-query";
import { Health, api } from "../api";

export function StatusPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  const data = health.data;
  const rows = [
    ["API", data?.status],
    ["Scoring model", data?.scoring_model],
    ["Vector index", data?.vector_index],
    ["Knowledge base", data?.knowledge_base],
    ["LLM provider", data?.llm_provider],
    ["Observability", data?.observability],
    ["LangSmith", data?.langsmith],
    ["Langfuse", data?.langfuse],
    ["Build", data?.build],
    ["Environment", data?.environment],
  ];
  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="text-3xl font-semibold">System Status</h1>
      <ul className="card mt-6 divide-y divide-line">
        {rows.map(([k, v]) => (
          <li key={String(k)} className="flex justify-between px-4 py-3 text-sm">
            <span className="text-slate-400">{k}</span>
            <span>{String(v ?? "—")}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
