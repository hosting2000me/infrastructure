# Published-port allocation in this Swarm

## Key facts

- External Swarm overlay network `intranet` is for service-to-service communication. Joining it does NOT make a published `ports:` binding private. In default `mode: ingress`, published ports are reachable through **every** Swarm node on its reachable host interfaces.
- If a dashboard is reached only through a reverse proxy which is also attached to `intranet`, there is normally **no need to publish a host port** for the dashboard. Use the service DNS name and its in-container port.
- If host publication is required, use `mode: ingress` for consistent routing after node failover, and explicitly restrict incoming access through the existing firewall/proxy. Do not assume `ss` sees ingress published ports.
- Avoid `mode: host` for a relocatable agent unless there is a compelling reason.

Source: https://docs.docker.com/engine/swarm/ingress/

## See every Swarm published mapping (manager node)

```bash
docker service ls --format 'table {{.Name}}\t{{.Ports}}'
docker service inspect dagu_dagu --format '{{json .Endpoint.Spec.Ports}}'
```

These show Swarm port publications even when a task runs on another node. Also inspect *non-Swarm* listeners on every possible destination node:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
ss -lntup
```

## Repository port register

`docker/ports.csv` contains **44 individual port/protocol bindings from the Swarm service list supplied on 2026-10-24**, plus the inactive-but-declared `airflow2` port `8880/tcp` and two **proposed** agent reservations (`21001/tcp`, `21002/tcp`). Treat the list as a time-stamped snapshot, not a guaranteed live inventory. It includes both TCP and UDP where applicable.

Reserve new published ports in the CSV **in the same commit/PR** that adds the corresponding stack. Key is `published + protocol`; avoid reusing a reserved ingress port cluster-wide.

Use candidate range **21000-21999** for new app WebUIs. Proposed reservations: **OpenClaw `21001:18789/tcp`**, **Hermes `21002:9119/tcp`**. Both require full host checks and access-control configuration before deployment.

`docker/ports.py` is read-only: it checks CSV reservations, all live Swarm services, local node listeners/standalone containers, and optionally all Swarm nodes over SSH.

On a Swarm manager from the repository root:

```bash
python3 docker/ports.py list
python3 docker/ports.py check
python3 docker/ports.py next
```

The default `next` only inspects **the current host** for standalone ports and therefore labels the number a **candidate**, not a confirmed free cluster-wide port.

To check the host listeners and local Docker containers on every node (requires noninteractive SSH access to all nodes):

```bash
python3 docker/ports.py list --ssh-all-nodes
python3 docker/ports.py next --ssh-all-nodes
```

If any node cannot be inspected, candidate selection fails instead of falsely claiming the port is free. If SSH is not configured, run `docker ps` and `ss` on each fallback node manually; only then reserve a port. The script never updates Git or Docker itself, and cannot rule out a competing deployment between scan and application.

## Placement, connectivity, and failover

- New agent stacks: **one replica each**, NFS from **nfs02**, attach only to **intranet**; no `/var/run/docker.sock` mounts.
- Any node eligible for failover must mount the NFS export and have access to the container registry, intranet overlay, and required secrets.
- `node.hostname == vs15` is a hard constraint and **prevents failover**. Do not use it as permanent placement.
- Docker Swarm preferences offer `spread`, not a strict primary/secondary priority. To guarantee **initial** scheduling on `vs15` without permanent pinning, use a **two-phase bootstrap** with `placement.constraints: [node.labels.ai_agents_eligible == true]`: (1) label only `vs15`, deploy and confirm both agents start there; (2) label **both `vs11` and `vs12`** as approved fallback nodes. Swarm normally does not rebalance a running task just because other nodes become eligible. Upon task failure on `vs15`, the scheduler may start its replacement on any eligible fallback node. There is no automatic "return to vs15" guarantee.
- Stateful services must be stop-first; backups and the application recovery behavior remain important even with a shared NFS mount.

Source: https://docs.docker.com/engine/swarm/services/

## Pending before publishing OpenClaw/Hermes dashboards

Determine whether a reverse proxy on `intranet` already provides authenticated browser access. If so, prefer **zero new published ports** and connect the proxy to the service's internal port. Otherwise choose and reserve distinct ingress published ports after live inventory and secure their access externally.

## No reverse proxy: agreed for agent WebUIs (2026-10-24)

There is **no reverse proxy** in this Swarm. Both agents will need published TCP ports for direct browser access, not just membership in the `intranet` overlay network.

Publish only these UI ports, not any optional API/bridge ports, by default. Ingress makes the UI port reachable on every Swarm node; restrict it to the trusted LAN/VPN using firewall rules on **all nodes**. Hermes dashboard additionally requires an authentication provider (LAN username/password or OAuth). OpenClaw requires its Gateway token and per-origin Control UI settings; plain HTTP LAN may have secure-context/device-pairing limitations. Neither stack should be opened to the public internet by mistake.

For direct published UIs there is no need to deploy an additional proxy just for Swarm failover; with ingress, the same published port routes to the task on another eligible node.

Observed non-published services in the user's snapshot (no published port mapping): `portainer_agent`, `swarmpit_db`, `swarmpit_influxdb`, `swarmpit_pagent`.
