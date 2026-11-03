# Agente VPS Guardian

Serviço leve em Python que coleta métricas do host e as envia por **HTTPS de saída**
para a central. Não abre portas, não aceita comandos e não escreve no Docker.

- **Alvo:** Ubuntu 22.04 / 24.04 (Python 3.10+)
- **Serviço:** `systemd`, usuário de sistema `vps-guardian`, sem privilégios
- **Dependência externa:** apenas `psutil`

## O que coleta

| Métrica | Detalhe |
|---|---|
| CPU | percentual, núcleos lógicos, load average 1/5/15 |
| RAM | total, usada, disponível, percentual |
| Swap | total, usada, percentual |
| Disco | total/usado/livre/percentual **por ponto de montagem** |
| Rede | bytes e taxa (bits/s) por interface, calculada entre coletas |
| Uptime | segundos desde o boot |
| Sistema | hostname, distro, versão, kernel, arquitetura |
| Agente | versão e timestamp UTC da coleta |

## O que **nunca** coleta nem faz

- Não lê variáveis de ambiente, `.env`, chaves privadas, senhas ou conteúdo de volumes.
- Não executa comandos — nem recebe comandos da central.
- Não escreve no Docker (fase 1.0 é somente leitura; a coleta Docker chega na fase 8).
- Não envia logs completos por padrão.
- Não aceita HTTP sem TLS (exceto `localhost`, para teste local).

## Instalação

Pré-requisito: servidor já cadastrado no painel e um **token de provisionamento**
(emitido em `POST /api/v1/servers/{id}/provisioning-token`, válido por 15 minutos).

```bash
# no repositório clonado, dentro do host monitorado
sudo bash agent/scripts/install.sh \
  --server-id <UUID-do-painel> \
  --token <token-de-provisionamento> \
  --api-url https://guardian.seudominio.com
```

Leia o script antes de executar: ele não baixa nada da internet e não usa `curl | bash`.

O instalador:

1. valida Python ≥ 3.10 e execução como root;
2. cria o usuário de sistema `vps-guardian` (sem shell) e os diretórios de estado/log;
3. instala o agente em `/opt/vps-guardian` com virtualenv próprio;
4. grava `/etc/vps-guardian/agent.json` com permissão `0600`;
5. instala e habilita o `guardian-agent.service` endurecido;
6. no primeiro start, troca o token temporário pela **credencial permanente** e
   reescreve o config sem o token.

## Verificação

```bash
systemctl status guardian-agent
journalctl -u guardian-agent -n 30 --no-pager
tail -f /var/log/vps-guardian/agent.log
```

Teste de coleta sem enviar nada:

```bash
sudo -u vps-guardian /opt/vps-guardian/venv/bin/guardian-agent \
  --config /etc/vps-guardian/agent.json --dry-run
```

Um ciclo único (útil em diagnóstico):

```bash
sudo -u vps-guardian /opt/vps-guardian/venv/bin/guardian-agent \
  --config /etc/vps-guardian/agent.json --once
```

No painel, o servidor deve passar a `online` com `last_metrics_at` atualizado.

## Configuração (`/etc/vps-guardian/agent.json`)

| Chave | Padrão | Descrição |
|---|---|---|
| `api_url` | — | base HTTPS da central |
| `server_id` | — | UUID do servidor no painel |
| `credential` | `null` | credencial individual (preenchida no 1º start) |
| `provisioning_token` | — | usado uma vez para registrar |
| `interval_seconds` | `30` | intervalo de coleta (10–3600) |
| `request_timeout_seconds` | `10` | timeout de cada requisição |
| `verify_tls` | `true` | validação do certificado (não desative em produção) |
| `spool_dir` | `/var/lib/vps-guardian/spool` | buffer local de payloads |
| `state_file` | `/var/lib/vps-guardian/state.json` | contadores para taxa de rede |
| `log_file` | `/var/log/vps-guardian/agent.log` | log JSON com rotação (5 MB × 3) |
| `max_spool_items` | `120` | máximo de coletas em buffer |
| `max_spool_age_seconds` | `21600` | descarta buffer mais antigo que 6 h |
| `exclude_interfaces` | `["lo"]` | interfaces ignoradas (aceita prefixos) |

Alterações exigem `systemctl restart guardian-agent`.

## Resiliência

- Falha de rede/timeout/5xx → o payload vai para o buffer local e é reenviado depois.
- HTTP 4xx (exceto 429) → erro permanente: o payload é descartado e registrado no log
  (reenviar não resolveria).
- Buffer limitado por quantidade **e** idade; o item mais antigo é descartado primeiro.
- Reinício do serviço não trava; contadores de rede são persistidos para não zerar taxas.
- Uma falha de coleta não derruba o loop (`try/except` por ciclo).

## Segurança

- Roda como `vps-guardian`, sem capabilities (`CapabilityBoundingSet=`), com
  `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `RestrictAddressFamilies` e
  `SystemCallFilter=@system-service`.
- Escrita permitida apenas em `/var/lib/vps-guardian` e `/var/log/vps-guardian`.
- Configuração `0600`; escrita atômica (sem arquivo parcial).
- Credencial mascarada nos logs por filtro dedicado.
- TLS obrigatório; `verify_tls` só pode ser desativado por decisão explícita.

## Remoção

```bash
sudo bash agent/scripts/uninstall.sh          # remove serviço e código
sudo bash agent/scripts/uninstall.sh --purge  # remove também config, logs e usuário
```

Depois de remover, **revogue a credencial** no painel
(`POST /api/v1/servers/{id}/credentials/revoke`).

## Problemas comuns

| Sintoma | Causa provável | Ação |
|---|---|---|
| `configuração inválida` | JSON malformado ou `api_url` sem https | verificar `/etc/vps-guardian/agent.json` |
| `HTTP 401` no log | credencial revogada/rotacionada | gerar novo token e reinstalar |
| `HTTP 422` no log | payload não aceito (versão incompatível) | atualizar o agente |
| servidor não fica online | relógio do host errado | `timedatectl status` |
| serviço reinicia em loop | diretório sem permissão | `journalctl -u guardian-agent` |

## Consumo de recursos

Referência esperada: poucos MB de RSS e < 1 % de CPU em VPS de 2 vCPU, com coleta a
cada 30 s. A medição real por host é feita na validação do piloto (Fase 5) e registrada
no relatório daquela fase.
