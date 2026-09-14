import { GraphDefinition } from "../api";
import { NodeStatus, progressPercent, STATUS_LABEL } from "../graphModel";

const CHIP: Record<NodeStatus, string> = {
  pending: "bg-canvas text-muted",
  running: "bg-yellow text-ink",
  done: "bg-ink text-white",
  skipped: "bg-canvas text-muted line-through",
  error: "bg-red-50 text-bad",
};

export function GraphProgress({
  definition,
  statuses,
  busy,
}: {
  definition?: GraphDefinition;
  statuses: Record<string, NodeStatus>;
  busy: boolean;
}) {
  const nodes = definition?.nodes || [];
  const happy = definition?.happy_path || nodes.map((node) => node.id);
  const percent = busy || Object.values(statuses).some((status) => status !== "pending") ? progressPercent(statuses, happy) : 0;
  const current = nodes.find((node) => statuses[node.id] === "running");
  const loop = statuses.retrieve_more === "running" || statuses.retrieve_more === "done";
  const groups: string[][] = [];
  for (const node of nodes) {
    if (node.optional && statuses[node.id] === "pending" && !busy) continue;
    if (node.parallel_group) {
      const last = groups[groups.length - 1];
      const lastNode = last ? nodes.find((item) => item.id === last[0]) : undefined;
      if (last && lastNode?.parallel_group === node.parallel_group) {
        last.push(node.id);
        continue;
      }
    }
    groups.push([node.id]);
  }

  return (
    <section className="tile p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-[17px] font-semibold">Как идёт LangGraph</h3>
          <p className="mt-1 text-sm text-muted">
            {current ? `${current.label} · ${current.tech}` : percent === 100 ? "Граф завершён" : "Ожидание прогона"}
            {loop ? " · петля критика" : ""}
          </p>
        </div>
        <span className="text-sm font-semibold">{percent}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-canvas">
        <div className="h-full rounded-full bg-yellow transition-all duration-300" style={{ width: `${percent}%` }} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {groups.map((ids) => (
          <div key={ids.join("-")} className={ids.length > 1 ? "flex gap-2 rounded-2xl bg-canvas p-1" : ""}>
            {ids.map((id) => {
              const node = nodes.find((item) => item.id === id);
              if (!node) return null;
              const status = statuses[id] || "pending";
              return (
                <div key={id} className={`min-w-[104px] rounded-2xl px-3 py-2 ${CHIP[status]}`}>
                  <div className="text-[13px] font-semibold">{node.label}</div>
                  <div className={`mt-0.5 text-[11px] ${status === "done" ? "text-white/70" : ""}`}>
                    {node.tech} · {STATUS_LABEL[status]}
                    {ids.length > 1 ? " · ∥" : ""}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
}
