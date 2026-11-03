import { useQuery } from "@tanstack/react-query";

import { ApiError, api } from "./api";

/** Sessão atual. Não repete a chamada: é a fonte de verdade do usuário logado. */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export function isForbidden(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403;
}
