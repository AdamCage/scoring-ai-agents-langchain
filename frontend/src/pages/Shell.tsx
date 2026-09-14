import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Health } from "../api";
import { Logo } from "../ui";

const links = [
  { to: "/", label: "Заявка" },
  { to: "/architecture", label: "LangChain" },
  { to: "/observability", label: "Observability" },
  { to: "/quality", label: "Evaluation" },
];

export function Shell() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });

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
            {health.data?.llm_provider || "…"} · {health.data?.scoring_model || "…"}
          </NavLink>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-4 pb-24 pt-6 md:pb-10">
        <Outlet />
      </div>
    </div>
  );
}
