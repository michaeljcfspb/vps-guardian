import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Button, Field, inputClasses, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { isUnauthorized, useMe } from "../lib/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const me = useMe();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: () => api.login(email.trim(), password),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/", { replace: true });
    },
  });

  if (me.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner label="Verificando sessão..." />
      </div>
    );
  }

  // Sessão já válida: não faz sentido mostrar o formulário.
  if (me.isSuccess) {
    return null;
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate();
  };

  const errorMessage = login.isError
    ? isUnauthorized(login.error)
      ? "E-mail ou senha inválidos."
      : login.error instanceof Error
        ? login.error.message
        : "Falha ao entrar."
    : null;

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-emerald-500/15 text-2xl text-emerald-400">
            ◆
          </span>
          <h1 className="mt-4 text-xl font-semibold tracking-wide text-slate-100">
            VPS GUARDIAN
          </h1>
          <p className="mt-1 text-sm text-slate-500">Monitoramento centralizado das suas VPS</p>
        </div>

        <form
          onSubmit={submit}
          className="card space-y-4 p-6"
          aria-label="Formulário de acesso"
        >
          <Field label="E-mail">
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClasses}
              placeholder="admin@seudominio.com"
            />
          </Field>

          <Field label="Senha">
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClasses}
              placeholder="••••••••••••"
            />
          </Field>

          {errorMessage ? (
            <p role="alert" className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
              {errorMessage}
            </p>
          ) : null}

          <Button type="submit" disabled={login.isPending} className="w-full">
            {login.isPending ? "Entrando..." : "Entrar"}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-600">
          Acesso restrito. Tentativas são registradas em auditoria.
        </p>
      </div>
    </div>
  );
}
