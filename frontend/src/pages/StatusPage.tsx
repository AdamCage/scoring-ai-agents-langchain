import { useQuery } from "@tanstack/react-query";
import { Health, api } from "../api";
import { PageTitle } from "../ui";

export function StatusPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  const data = health.data;
  const rows: [string, string][] = [
    ["API", data?.status ?? "—"],
    ["Модель скоринга", String(data?.scoring_model ?? "—")],
    ["Векторный индекс", String(data?.vector_backend ?? "in-memory")],
    ["База знаний", String(data?.knowledge_base ?? "—")],
    ["LLM", data?.llm_provider ?? "—"],
    ["Observability", data?.observability ?? "—"],
    ["Langfuse", data?.langfuse ?? "—"],
    ["LangSmith", data?.langsmith ?? "—"],
    ["Сборка", data?.build ?? "—"],
    ["Среда", data?.environment ?? "—"],
  ];

  return (
    <div>
      <PageTitle
        kicker="Статус"
        title="Что включено на этом стенде"
        text="Честный чеклист: модель, in-memory RAG, RouterAI, Langfuse OSS и слот LangSmith."
      />
      <ul className="tile divide-y divide-line">
        {rows.map(([label, value]) => (
          <li key={label} className="flex items-center justify-between px-5 py-4 text-sm">
            <span className="text-muted">{label}</span>
            <span className="font-medium">{value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
