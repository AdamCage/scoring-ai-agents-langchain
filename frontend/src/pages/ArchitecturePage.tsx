import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import mermaid from "mermaid";
import { api } from "../api";

const TABS = [
  { id: "langchain", label: "LangChain", file: "langchain-runtime.mmd", process: "02-langchain-in-process.md" },
  { id: "observability", label: "Observability", file: "observability-pipeline.mmd", process: "03-observability-in-process.md" },
  { id: "evaluation", label: "Evaluation", file: "evaluation-pipeline.mmd", process: "04-evaluation-in-process.md" },
];

mermaid.initialize({ startOnLoad: false, theme: "dark" });

export function ArchitecturePage() {
  const [tab, setTab] = useState(TABS[0]);
  const [svg, setSvg] = useState("");
  const diagrams = useQuery({
    queryKey: ["arch"],
    queryFn: () => api<{ files: string[] }>("/api/docs/architecture"),
  });
  const traces = useQuery({
    queryKey: ["traces-mini"],
    queryFn: () => api<{ traces: { run_id: string; spans: { name: string; mmd_node?: string; code_path?: string; duration_ms?: number }[] }[] }>("/api/traces"),
  });

  useEffect(() => {
    fetch(`/api/docs/file/architecture/${tab.file}`, { credentials: "include" })
      .then((r) => r.text())
      .then(async (text) => {
        const id = `mmd-${tab.id}`;
        const { svg } = await mermaid.render(id, text);
        setSvg(svg);
      })
      .catch(() => setSvg("<p>Схема недоступна</p>"));
  }, [tab]);

  const [process, setProcess] = useState("");
  useEffect(() => {
    fetch(`/api/docs/file/processes/${tab.process}`, { credentials: "include" })
      .then((r) => r.text())
      .then(setProcess)
      .catch(() => setProcess(""));
  }, [tab]);

  const last = traces.data?.traces?.[0];

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-3xl font-semibold">Architecture Explorer</h1>
      <p className="mt-2 max-w-3xl text-sm text-slate-400">
        Те же `.mmd` и процессные `.md`, что лежат в репозитории. Справа — привязка к последнему run:
        span, узел схемы и code path.
      </p>
      <div className="mt-4 flex gap-2">
        {TABS.map((item) => (
          <button key={item.id} className={item.id === tab.id ? "btn" : "btn-ghost"} onClick={() => setTab(item)}>
            {item.label}
          </button>
        ))}
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="card overflow-auto p-4" dangerouslySetInnerHTML={{ __html: svg }} />
        <div className="card p-4 text-sm">
          <h2 className="font-semibold">Последний run</h2>
          {last ? (
            <ul className="mt-3 space-y-2">
              {last.spans.map((span) => (
                <li key={span.name} className="rounded-lg border border-line p-2">
                  <div className="text-accent">{span.name}</div>
                  <div className="font-mono text-xs text-slate-400">{span.code_path}</div>
                  <div className="text-xs text-slate-500">mmd: {span.mmd_node || "—"} · {Math.round(span.duration_ms || 0)} ms</div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-slate-400">Прогоните заявку на Workbench — сюда подтянутся spans.</p>
          )}
        </div>
      </div>
      <article className="card mt-6 whitespace-pre-wrap p-5 text-sm leading-6 text-slate-300">{process}</article>
      <p className="mt-4 text-xs text-slate-500">Доступные схемы: {(diagrams.data?.files || []).join(", ")}</p>
    </div>
  );
}
