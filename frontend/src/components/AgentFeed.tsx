import { GraphDefinition, SSEEvent } from "../api";

type FeedItem = {
  id: string;
  title: string;
  tech: string;
  body: string;
  tone: "default" | "tool" | "rag" | "llm";
};

function lastBy<T>(items: T[], pred: (item: T) => boolean): T | undefined {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (pred(items[index])) return items[index];
  }
  return undefined;
}

function tokensFor(events: SSEEvent[], node: string): string {
  return events
    .filter((event) => event.type === "token" && event.node === node)
    .map((event) => String(event.data.text || ""))
    .join("");
}

export function AgentFeed({
  events,
  definition,
}: {
  events: SSEEvent[];
  definition?: GraphDefinition;
}) {
  const items: FeedItem[] = [];
  const labels = new Map((definition?.nodes || []).map((node) => [node.id, node]));

  for (const [index, event] of events.entries()) {
    const meta = event.node ? labels.get(event.node) : undefined;
    if (event.type === "node_start" && event.node) {
      items.push({
        id: `start-${index}`,
        title: meta?.label || event.node,
        tech: meta?.tech || "LangGraph",
        body: `Узел ${event.node} запущен`,
        tone: meta?.kind === "retriever" ? "rag" : meta?.kind === "tool" ? "tool" : "default",
      });
    }
    if (event.type === "tool" && event.node === "calculate_score") {
      items.push({
        id: `score-${index}`,
        title: "CatBoost tool",
        tech: "ScoringResult",
        body: `score=${event.data.score} · PD=${event.data.pd} · ${event.data.risk_band} · ${event.data.decision}`,
        tone: "tool",
      });
    }
    if (event.type === "tool" && event.node === "explain_score") {
      const features = (event.data.features as { label: string; shap_value: number }[]) || [];
      items.push({
        id: `shap-${index}`,
        title: "SHAP explain",
        tech: "Tool",
        body: features
          .slice(0, 3)
          .map((item) => `${item.label} (${item.shap_value > 0 ? "+" : ""}${Number(item.shap_value).toFixed(3)})`)
          .join(" · "),
        tone: "tool",
      });
    }
    if (event.type === "retrieval") {
      items.push({
        id: `rag-${index}`,
        title: "Hybrid RAG",
        tech: `vector → BM25 → RRF → rerank · ${event.data.latency_ms ?? "—"} мс`,
        body: `rerank: ${((event.data.rerank as string[]) || []).slice(0, 4).join(", ") || "—"}`,
        tone: "rag",
      });
    }
    if (event.type === "interrupt") {
      items.push({
        id: `int-${index}`,
        title: "Interrupt",
        tech: String(event.data.reason || "human"),
        body: event.node === "human_review" ? "Нужен human review" : "Заявке не хватает данных",
        tone: "default",
      });
    }
    if (event.type === "error") {
      items.push({
        id: `err-${index}`,
        title: "Ошибка",
        tech: "graph",
        body: String(event.data.message || "unknown"),
        tone: "default",
      });
    }
  }

  const streamingNode = lastBy(events, (event) => event.type === "node_start")?.node;
  const running = streamingNode && !events.some((event) => event.type === "node_end" && event.node === streamingNode);
  const liveText = streamingNode && running ? tokensFor(events, streamingNode) : "";
  const analyst = tokensFor(events, "risk_analysis");
  const critic = tokensFor(events, "policy_critic");
  const synth = tokensFor(events, "synthesize");

  if (analyst) {
    items.push({ id: "llm-risk", title: "Риск-аналитик", tech: "LangChain LLM", body: analyst, tone: "llm" });
  }
  if (critic) {
    items.push({ id: "llm-critic", title: "Policy critic", tech: "LangChain LLM", body: critic, tone: "llm" });
  }
  if (synth) {
    items.push({ id: "llm-synth", title: "Synthesizer", tech: "LangGraph", body: synth, tone: "llm" });
  }

  const toneClass = {
    default: "bg-canvas",
    tool: "bg-yellow/40",
    rag: "bg-canvas",
    llm: "bg-white ring-1 ring-line",
  };

  return (
    <section className="tile flex max-h-[520px] flex-col p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[17px] font-semibold">Ход агентов</h3>
        <span className="pill">{events.length} SSE</span>
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-auto pr-1">
        {items.length === 0 ? (
          <p className="text-sm text-muted">После старта здесь появятся tools, retrieval и токены LLM.</p>
        ) : (
          items.slice(-16).map((item) => (
            <article key={item.id} className={`rounded-2xl px-3 py-3 ${toneClass[item.tone]}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold">{item.title}</p>
                <p className="text-[11px] text-muted">{item.tech}</p>
              </div>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-ink/90">{item.body}</p>
            </article>
          ))
        )}
        {liveText && streamingNode && !["risk_analysis", "policy_critic", "synthesize"].includes(streamingNode) ? (
          <article className="rounded-2xl bg-yellow px-3 py-3">
            <p className="text-sm font-semibold">Стрим · {streamingNode}</p>
            <p className="mt-1 text-sm leading-6">{liveText}</p>
          </article>
        ) : null}
      </div>
    </section>
  );
}
