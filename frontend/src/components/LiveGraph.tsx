import { useEffect, useState } from "react";
import mermaid from "mermaid";
import { GraphDefinition } from "../api";
import { mermaidWithStatuses, NodeStatus } from "../graphModel";

let mermaidReady = false;

function ensureMermaid() {
  if (mermaidReady) return;
  mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
  mermaidReady = true;
}

export function LiveGraph({
  definition,
  statuses,
}: {
  definition?: GraphDefinition;
  statuses: Record<string, NodeStatus>;
}) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");

  const statusKey = JSON.stringify(statuses);

  useEffect(() => {
    if (!definition?.mermaid) return;
    let cancelled = false;
    ensureMermaid();
    const source = mermaidWithStatuses(definition.mermaid, definition.nodes, statuses);
    mermaid
      .render(`live-graph-${Date.now()}`, source)
      .then((out) => {
        if (!cancelled) {
          setSvg(out.svg);
          setError("");
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
    // statuses is snapshotted via statusKey so token events do not re-render mermaid
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [definition, statusKey]);

  if (!definition?.mermaid) {
    return <p className="text-sm text-muted">Схема графа ещё не загружена.</p>;
  }
  if (error) return <p className="text-sm text-bad">{error}</p>;
  if (!svg) return <p className="text-sm text-muted">Рисую LangGraph…</p>;
  return <div className="mermaid-wrap overflow-x-auto rounded-2xl bg-canvas p-4" dangerouslySetInnerHTML={{ __html: svg }} />;
}
