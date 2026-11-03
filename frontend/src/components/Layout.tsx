import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import type { User } from "../lib/types";

const navItem = ({ isActive }: { isActive: boolean }) =>
  `focus-ring rounded-lg px-3 py-1.5 text-sm transition ${
    isActive ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
  }`;

export function Layout({ user }: { user: User }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <Link to="/" className="focus-ring flex items-center gap-2 rounded-lg">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-emerald-500/15 text-emerald-400">
              ◆
            </span>
            <span className="text-sm font-semibold tracking-widest text-slate-100">
              VPS GUARDIAN
            </span>
          </Link>

          <nav className="ml-2 flex items-center gap-1">
            <NavLink to="/" end className={navItem}>
              Dashboard
            </NavLink>
          </nav>

          <div className="ml-auto flex items-center gap-3 text-xs text-slate-400">
            <span className="hidden sm:block">
              {user.name}
              <span className="ml-1 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                {user.role === "admin" ? "admin" : "operador"}
              </span>
            </span>
            <button
              type="button"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              className="focus-ring rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 transition hover:border-slate-600 hover:bg-slate-800/60 disabled:opacity-50"
            >
              {logout.isPending ? "Saindo..." : "Sair"}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>

      <footer className="mx-auto max-w-7xl px-4 pb-10 pt-2 text-xs text-slate-600">
        VPS Guardian · timestamps em UTC, exibidos em America/Sao_Paulo
      </footer>
    </div>
  );
}
