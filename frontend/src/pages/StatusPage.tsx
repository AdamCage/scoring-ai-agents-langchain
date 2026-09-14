import { useQuery } from "@tanstack/react-query";
import { Health, api } from "../api";
import { PageTitle } from "../ui";

export function StatusPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  const data = health.data;
  const rows: [string, string][] = [
    ["API", data?.status ?? "—"],
    ["Модель скоринга", String(data?.scoring_model ?? "—")],
    ["Векторный индекс", String(data?.vector_index ?? "—")],
    ["База знаний", String(data?.knowledge_base ?? "—")],
    ["LLM", data?.llm_provider ?? "—"],
    ["Observability", data?.observability ?? "—"],
    ["LangSmith", data?.langsmith ?? "—"],
    ["Langfuse", data?.langfuse ?? "—"],
    ["Сборка", data?.build ?? "—"],
    ["Среда", data?.environment ?? "—"],
  ];

  return (
    <div>
      <PageTitle
        kicker="Статус"
        title="Что включено в этом демо"
        text="Короткий чеклист для интервью: модель, RAG, LLM и локальная observability."
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
