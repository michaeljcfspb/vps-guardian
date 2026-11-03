import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="grid min-h-screen place-items-center px-4 text-center">
      <div>
        <p className="text-5xl font-semibold text-slate-700">404</p>
        <p className="mt-3 text-slate-300">Página não encontrada.</p>
        <Link
          to="/"
          className="focus-ring mt-6 inline-block rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800/60"
        >
          Voltar ao dashboard
        </Link>
      </div>
    </div>
  );
}
