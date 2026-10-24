# Docker stack authoring rules for agents

Read `docker/README.md` and at least two neighboring real stack examples before generating a new file under `docker/swarm-stacks/`.

- Target **Docker Swarm**. Output `compose.yml`, `start`, `stop`, and a short `README.md`; do not substitute `docker compose up`.
- Follow the repository naming, service, network, NFS volume and placement conventions.
- Do not infer that declarations in Git prove a service is active. Do not change existing stacks when adding a new one.
- Ask for node placement, external network, ports/proxy, NFS export, and privileged/sandbox access where missing. No arbitrary defaults for these deployment decisions.
- Use official upstream images and verified entrypoints and initialization instructions. Avoid `build:` inside a stack deployment unless an image is built/published separately.
- Assume one replica for stateful agents; require stop-first updates and rollback.
- Keep secrets/OAuth material outside Git (Swarm secrets or a local, ignored env). Do not commit real `*.env` files; check that the target filename is ignored.
- Never enable host Docker socket mounts, privileged mode, uncontrolled network exposure, or public admin UIs silently.
- Check Docker Swarm compatibility and the agent's required state directory, UID/GID, dashboard auth and health behavior.
- Produce a short, reproducible first-run/onboarding guide and post-deployment smoke test.
- Never deploy to the live Swarm or merge into `main` without explicit authorization.

Official project documentation:
- OpenClaw: https://docs.openclaw.ai/install/docker
- Hermes: https://hermes-agent.nousresearch.com/docs/user-guide/docker

## OpenClaw and Hermes Agent deployment decisions (2026-10-24)

- Agent containers **MUST NOT** mount /var/run/docker.sock or access the Docker daemon. Disable Docker-backed sandboxes.
- Attach only to external Swarm network `intranet`.
- Persistent state: NFS server `nfs02`, distinct exports `:/docker/volumes/openclaw` and `:/docker/volumes/hermes-agent` (exact export existence and permissions still require live verification).
- One replica per stateful agent, with `stop-first` updates/rollback and no permanent `node.hostname == vs15` constraint.
- Preferred initial node is `vs15`, but **failover is mandatory**. Use a two-stage bootstrap: constraint `node.labels.ai_agents_eligible == true` for both stacks; label only vs15 before initial deployment, verify both agents landed there, then label approved fallback nodes. Do not set a permanent hostname constraint; do not expect automatic failback. Never modify node labels without operator approval.
- Live Swarm inventory was supplied on 2026-10-24 and recorded in `docker/ports.csv` (44 published port/protocol mappings; plus one inactive Git reservation). Proposed UI ingress reservations: **21001/tcp -> 18789 OpenClaw** and **21002/tcp -> 9119 Hermes**. These are only candidates until host listeners and standalone Docker containers are checked on all eligible nodes. See `docker/PORTS.md` and `docker/ports.py`.
- User confirmed there is **no reverse proxy**. Both UIs use direct Swarm ingress published ports. IMPORTANT: overlay `intranet` does not restrict ingress exposure; firewall/trusted-LAN/VPN policy and strong agent auth are mandatory. No optional Hermes API port should be published by default.
- Before deployment, verify that every eligible failover node can access NFS, pull the image and reach the intranet network, and that application authentication/onboarding is configured.

- Draft implementation files already exist in `docker/swarm-stacks/openclaw/` and `docker/swarm-stacks/hermes-agent/` in this branch. Reuse/revise them rather than regenerating unrelated stacks. Neither has been deployed or validated against a live cluster.
