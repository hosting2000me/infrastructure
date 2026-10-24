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
