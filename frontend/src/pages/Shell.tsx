import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Health } from "../api";
import { Logo, TechPill } from "../ui";

const links = [
  { to: "/", label: "Заявка" },
  { to: "/architecture", label: "LangChain" },
  { to: "/observability", label: "Observability" },
  { to: "/quality", label: "Evaluation" },
];

export function Shell() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  const navigate = useNavigate();
  const data = health.data;
  const langfuseOn = data?.langfuse === "enabled";
  const langsmithOn = data?.langsmith === "enabled";

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-20 border-b border-line/70 bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Logo />
          <nav className="flex flex-wrap gap-1">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  `rounded-full px-3.5 py-2 text-[14px] ${
                    isActive ? "bg-ink text-white" : "text-muted hover:bg-white hover:text-ink"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <NavLink
            to="/status"
            className="hidden items-center gap-2 text-xs text-muted hover:text-ink md:flex"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-ok" />
            {data?.llm_provider || "…"} · {data?.scoring_model || "…"}
          </NavLink>
        </div>
        <div className="border-t border-line/50 bg-white/70">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-2">
            <div className="flex flex-wrap gap-1.5">
              <TechPill on>LangGraph</TechPill>
              <TechPill on>LangChain Agents</TechPill>
              <TechPill on={langfuseOn}>Langfuse Tracing + Datasets</TechPill>
              <TechPill on={langsmithOn}>LangSmith Evaluation</TechPill>
              <TechPill on={Boolean(data?.llm_configured)}>RouterAI</TechPill>
            </div>
            <div className="flex gap-2">
              <button className="btn-yellow !px-3 !py-1.5 text-sm" onClick={() => navigate("/?showcase=1")}>
                Run showcase
              </button>
              {data?.langsmith_experiment?.url ? (
                <a
                  className="btn-ghost !px-3 !py-1.5 text-sm"
                  href={data.langsmith_experiment.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open LangSmith Experiment ↗
                </a>
              ) : null}
              <a
                className="btn-ghost !px-3 !py-1.5 text-sm"
                href="https://github.com/adamcage/scoring-ai-agents-langchain"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
            </div>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-4 pb-24 pt-6 md:pb-10">
        <Outlet />
      </div>
    </div>
  );
}
