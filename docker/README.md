# Docker infrastructure (repository snapshot)

> Source: `docker/swarm-stacks/*` on the `main` branch, inspected 2026-10-24.
> This describes **declarations in Git**, not verified live Swarm state. Do not assume all stacks currently run.

## Orchestration and conventions

- Runtime: **Docker Swarm**. Deploy with `docker stack deploy`, not `docker compose up`.
- Each stack lives in `docker/swarm-stacks/<stack>/`, usually with `compose.yml` (older stacks use `<stack>.yml`), `start`, and `stop`.
- `start`: `docker stack deploy -c <file>.yml --detach=false --with-registry-auth <stack>`.
- `stop`: `docker stack rm <stack>`.
- Services are generally **single-replica** and pinned via `deploy.placement.constraints`. Changes to placement require explicit approval.
- Existing external Swarm networks: **`intranet`** and **`dmz`**. Do not create or replace them implicitly.
- Persistent service data usually lives on **NFS** via Docker local volumes with `driver_opts.type: nfs`, `nfsvers=4`, `addr=nfs02`, `device=:/docker/volumes/<stack>[/<subdir>]`.
- Exceptions: old `airflow` uses NFS server `is02`; `cryptoinvest-demo` also mounts `/data/bigdata/btc` from `nfs02`.
- Some stacks load node-local `.env`; `dagu` uses an external Swarm secret. The root `.gitignore` excludes `.env` but not arbitrary `*.env`.
- Observability: Fluent Bit sends logs to Grafana Loki, but this does **not** imply that every service is configured to use the Fluent Bit logging driver.

## Declared stacks

| Stack | Configuration | Node selector | Network | Published ports | Data/config |
| --- | --- | --- | --- | --- | --- |
| airflow | `airflow.yml` | `vs12` | intranet | 8888:8080 | NFS `is02:/docker/volumes/airflow/{data,dags}` |
| airflow2 | `compose.yml` | `vs15` | intranet | 8880:8080 (webserver) | NFS `nfs02:/docker/volumes/airflow2/dags`; `airflow.env` |
| cryptoinvest-demo | `compose.yml` | `vs11` | dmz | 20011:8000 | NFS `nfs02:/docker/volumes/cryptoinvest-demo`, `nfs02:/data/bigdata/btc`; `.env` |
| dagu | `compose.yml` | `vs15` | intranet | 8525:8080 | NFS `nfs02:/docker/volumes/dagu`; external secret; host Docker socket |
| dns | `dnsmasq.yml` | `node.labels.dns == yes` | intranet | 53/tcp, 53/udp, 5380:8080 | external Swarm config `dnsmasq_260814`; global mode |
| fluent-bit | `fluent-bit.yml` | `vs11` | intranet | 24224:24224 | NFS `nfs02:/docker/volumes/fluentbit`; host container-log bind mount; local config bind mount |

## Standard for adding a stack

Keep the familiar directory layout:

```text
docker/swarm-stacks/<name>/
  compose.yml
  start
  stop
  README.md          # initialization, credentials, maintenance and caveats
```

Use an upstream image where possible (prefer a pinned stable version/digest), `deploy.mode: replicated`, `replicas: 1`, an approved node constraint, a declared external network, and an explicit persistent volume mapping. Add `ports:` **only after deciding exposure**. Prefer a private/reverse-proxy route for agent admin consoles.

For stateful singletons use `deploy.update_config.order: stop-first` and `deploy.rollback_config.order: stop-first` to avoid overlapping readers/writers of the same state volume.

For a new stack, first establish:
1. exact official image, tag, process command and initialization steps;
2. Swarm node placement and whether NFS storage is appropriate;
3. network (`intranet` or `dmz`), allowed callers, published ports or reverse proxy;
4. exact NFS export/path and in-container mount point (and UID/GID compatibility);
5. secret sources, optional OAuth onboarding, non-committed local env;
6. whether agent sandbox needs Docker access; mounting `/var/run/docker.sock` effectively grants host-level control and is **not** a default;
7. resource limits, healthcheck, restart and update strategy.

`start` and `stop` should remain consistent with the existing scripts. Do not auto-deploy, create secrets or edit live services as part of generating a stack.

## Known discrepancies and security follow-ups

- `airflow2/airflow.env` is **tracked** and contains a nonempty `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`. As the repository is public, check whether the value embeds credentials; if so, rotate credentials and remove them from Git history. Never quote the value in documentation or chat.
- `fluent-bit/fluent-bit.yml` bind-mounts `./fluent-bit.conf`; a relative host source may not resolve as expected with `docker stack deploy` on a remote Swarm node. Verify actual live deployment before changing it.
- `airflow` uses NFS alias `is02`, whereas newer stacks use `nfs02`. Do not silently normalize legacy paths.
- No definitive information in Git about Swarm managers, ingress/reverse proxy, internal DNS/IP ranges, available node resources, or which stacks are *currently* active. Get these from the operator rather than guessing.

## Planned agent experiments

- `openclaw`: official GHCR image `ghcr.io/openclaw/openclaw`; Control UI/Gateway defaults to container port `18789`. Requires an onboarding/auth configuration and persistent state. Docker sandbox is optional, **off by default**. Official docs: https://docs.openclaw.ai/install/docker
- `hermes-agent`: official `nousresearch/hermes-agent` image, `gateway run`; all mutable state under `/opt/data`. Optional dashboard on container port `9119`, and API server on `8642` when enabled. Auth required for network-exposed dashboard. Official docs: https://hermes-agent.nousresearch.com/docs/user-guide/docker

**Do not choose node, NFS path, published ports, gateway accessibility or host Docker socket permissions for these two stacks until the operator answers.**
