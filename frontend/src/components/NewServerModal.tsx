import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api } from "../lib/api";
import type { ServerEnvironment, ServerInput, ServerPanel } from "../lib/types";
import { Button, Field, inputClasses, Modal } from "./ui";

const ENVIRONMENTS: { value: ServerEnvironment; label: string }[] = [
  { value: "production", label: "Produção" },
  { value: "staging", label: "Homologação" },
  { value: "development", label: "Desenvolvimento" },
  { value: "other", label: "Outro" },
];

const PANELS: { value: ServerPanel; label: string }[] = [
  { value: "easypanel", label: "Easypanel" },
  { value: "portainer", label: "Portainer" },
  { value: "icp", label: "ICP Integrator" },
  { value: "none", label: "Nenhum" },
];

export function NewServerModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [hostname, setHostname] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [environment, setEnvironment] = useState<ServerEnvironment>("production");
  const [panel, setPanel] = useState<ServerPanel>("easypanel");
  const [tags, setTags] = useState("");

  const create = useMutation({
    mutationFn: (payload: ServerInput) => api.createServer(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["servers"] }),
        queryClient.invalidateQueries({ queryKey: ["summary"] }),
      ]);
      setName("");
      setHostname("");
      setIpAddress("");
      setTags("");
      onClose();
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate({
      name: name.trim(),
      hostname: hostname.trim() || null,
      ip_address: ipAddress.trim() || null,
      environment,
      panel,
      tags: tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    });
  };

  return (
    <Modal open={open} title="Novo servidor" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Nome" hint="Identificação única, ex.: VPS-01">
          <input
            required
            minLength={2}
            maxLength={120}
            value={name}
            onChange={(event) => setName(event.target.value)}
            className={inputClasses}
            placeholder="VPS-01"
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Hostname" hint="opcional">
            <input
              value={hostname}
              onChange={(event) => setHostname(event.target.value)}
              className={inputClasses}
              placeholder="vps-01.exemplo.com"
            />
          </Field>
          <Field label="IP" hint="opcional">
            <input
              value={ipAddress}
              onChange={(event) => setIpAddress(event.target.value)}
              className={inputClasses}
              placeholder="203.0.113.10"
            />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Ambiente">
            <select
              value={environment}
              onChange={(event) => setEnvironment(event.target.value as ServerEnvironment)}
              className={inputClasses}
            >
              {ENVIRONMENTS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Painel">
            <select
              value={panel}
              onChange={(event) => setPanel(event.target.value as ServerPanel)}
              className={inputClasses}
            >
              {PANELS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Tags" hint="separadas por vírgula, opcional">
          <input
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            className={inputClasses}
            placeholder="web, cliente-a"
          />
        </Field>

        {create.isError ? (
          <p role="alert" className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
            {create.error instanceof Error ? create.error.message : "Falha ao cadastrar."}
          </p>
        ) : null}

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Salvando..." : "Cadastrar"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
