import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Health } from "../api";
import { useEffect } from "react";

const links = [
  { to: "/", label: "Workbench" },
  { to: "/architecture", label: "Architecture" },
  { to: "/observability", label: "Observability" },
  { to: "/quality", label: "Quality Lab" },
  { to: "/status", label: "Status" },
];

export function Shell() {
  const navigate = useNavigate();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ authenticated: boolean }>("/api/auth/me"),
    retry: false,
  });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });

  useEffect(() => {
    if (me.isError) navigate("/login");
  }, [me.isError, navigate]);

  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="rounded-md bg-accent/15 px-2 py-1 text-sm font-bold text-accent">CreditLens</span>
          <span className="hidden text-sm text-slate-400 md:inline">
            {health.data?.scoring_model} · {health.data?.llm_provider}
          </span>
        </div>
        <nav className="flex flex-wrap gap-2">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-white/10 text-white" : "text-slate-400 hover:text-white"}`
              }
              end={link.to === "/"}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
