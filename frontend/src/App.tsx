import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ErrorBox, Spinner } from "./components/ui";
import { isUnauthorized, useMe } from "./lib/auth";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";

// Recharts é pesado: o detalhe do servidor é carregado sob demanda.
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const ServerDetailPage = lazy(() =>
  import("./pages/ServerDetailPage").then((module) => ({ default: module.ServerDetailPage })),
);

function Protected() {
  const me = useMe();

  if (me.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner label="Verificando sessão..." />
      </div>
    );
  }

  if (me.isError) {
    if (isUnauthorized(me.error)) {
      return <Navigate to="/login" replace />;
    }
    return (
      <div className="mx-auto max-w-lg p-8">
        <ErrorBox error={me.error} onRetry={() => void me.refetch()} />
      </div>
    );
  }

  if (!me.data) {
    return <Navigate to="/login" replace />;
  }

  return <Layout user={me.data.user} />;
}

function PageFallback() {
  return (
    <div className="py-16">
      <Spinner label="Carregando painel..." />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Protected />}>
        <Route
          path="/"
          element={
            <Suspense fallback={<PageFallback />}>
              <DashboardPage />
            </Suspense>
          }
        />
        <Route
          path="/servers/:serverId"
          element={
            <Suspense fallback={<PageFallback />}>
              <ServerDetailPage />
            </Suspense>
          }
        />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
