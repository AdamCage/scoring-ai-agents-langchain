import { GraphDefinition, GraphNode, SSEEvent, Span } from "./api";

export type NodeStatus = "pending" | "running" | "done" | "skipped" | "error";

export const STATUS_LABEL: Record<NodeStatus, string> = {
  pending: "ждёт",
  running: "идёт",
  done: "готово",
  skipped: "пропуск",
  error: "ошибка",
};

export function mermaidWithStatuses(source: string, nodes: GraphNode[], statuses: Record<string, NodeStatus>): string {
  const lines = [
    source.trim(),
    "classDef pending fill:#F2F3F7,stroke:#E4E5EA,color:#6E6E73",
    "classDef running fill:#FFCC00,stroke:#000000,color:#000000",
    "classDef done fill:#000000,stroke:#000000,color:#ffffff",
    "classDef skipped fill:#F2F3F7,stroke:#D0D1D6,color:#A0A0A5",
    "classDef error fill:#E31227,stroke:#E31227,color:#ffffff",
  ];
  for (const node of nodes) {
    lines.push(`class ${node.mmd} ${statuses[node.id] || "pending"}`);
  }
  return lines.join("\n");
}

export function statusesFromEvents(
  events: SSEEvent[],
  definition: GraphDefinition | undefined,
  finished: boolean,
): Record<string, NodeStatus> {
  const seen: Record<string, NodeStatus> = {};
  for (const event of events) {
    if (!event.node) continue;
    if (event.type === "node_start") seen[event.node] = "running";
    if (event.type === "node_end") seen[event.node] = "done";
    if (event.type === "error") seen[event.node] = "error";
  }
  const nodes = definition?.nodes || [];
  const out: Record<string, NodeStatus> = {};
  for (const node of nodes) {
    const status = seen[node.id];
    if (status) {
      out[node.id] = status;
    } else if (finished) {
      out[node.id] = node.optional ? "skipped" : "pending";
    } else {
      out[node.id] = "pending";
    }
  }
  if (finished && seen.request_information) {
    out.calculate_score = out.calculate_score === "pending" ? "skipped" : out.calculate_score;
    for (const id of definition?.happy_path || []) {
      if (id !== "validate_application" && out[id] === "pending") out[id] = "skipped";
    }
  }
  return out;
}

export function statusesFromSpans(spans: Span[], definition: GraphDefinition | undefined): Record<string, NodeStatus> {
  const known = new Set((definition?.nodes || []).map((node) => node.id));
  const seen: Record<string, NodeStatus> = {};
  for (const span of spans) {
    if (!known.has(span.name)) continue;
    seen[span.name] = span.status === "error" ? "error" : "done";
  }
  const out: Record<string, NodeStatus> = {};
  const hasAny = Object.keys(seen).length > 0;
  for (const node of definition?.nodes || []) {
    if (seen[node.id]) out[node.id] = seen[node.id];
    else out[node.id] = hasAny && node.optional ? "skipped" : hasAny ? "skipped" : "pending";
  }
  return out;
}

export function progressPercent(statuses: Record<string, NodeStatus>, happyPath: string[]): number {
  if (!happyPath.length) return 0;
  const done = happyPath.filter((id) => statuses[id] === "done").length;
  const running = happyPath.filter((id) => statuses[id] === "running").length;
  return Math.min(100, Math.round(((done + running * 0.45) / happyPath.length) * 100));
}
