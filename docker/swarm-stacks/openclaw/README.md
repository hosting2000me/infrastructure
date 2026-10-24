# OpenClaw — draft Swarm stack

## Status

Configuration only; **not deployed**. Direct browser port **21001/tcp -> 18789/tcp** is present in the proposed Git reservation register. It does not appear in the supplied 2026-10-24 Swarm service list, but still requires host-level port checks on all eligible nodes.

Official reference: https://docs.openclaw.ai/docker

## Runtime

- Official image: `ghcr.io/openclaw/openclaw:latest` (trial; pin a release digest before long-term use).
- Service: `openclaw_gateway`, one replica.
- Network: external `intranet`.
- NFS volume: `nfs02:/docker/volumes/openclaw` mounted at `/home/node/.openclaw`.
- Credentials: **external** Swarm secret `openclaw_gateway_token`; at runtime a shell wrapper passes it to the official Gateway process as an environment variable. Never commit token or auth-profile contents.
- Gateway listens on `18789` inside the container. Published port is `21001` via Swarm ingress.
- No host Docker socket. Docker sandboxing is not enabled.
- Initial node: **vs15**; allowed failover nodes: **vs11**, **vs12**. Follow the shared two-stage `ai_agents_eligible` placement-label process in `../../PORTS.md`.

## Required before first deployment

1. Verify NFS export exists, supports the runtime `node` user (typically UID/GID 1000) and is writable from **every** eligible node.
2. Initialize the state/config directory using the official onboarding CLI against the persistent NFS volume. To create the volume on vs15 for initial setup:
   ```bash
   docker volume create --driver local \
     --opt type=nfs --opt o=nfsvers=4,addr=nfs02,rw \
     --opt device=:/docker/volumes/openclaw openclaw_state

   docker run --rm -it --entrypoint node \
     -e HOME=/home/node \
     -v openclaw_state:/home/node/.openclaw \
     ghcr.io/openclaw/openclaw:latest \
     dist/index.js onboard --mode local --no-install-daemon
   ```
   Complete provider/channel credentials and local Gateway mode. Confirm the resulting NFS config includes the right allowed browser origins for direct access (e.g. the exact `http://<hostname>:21001` addresses you actually use); do not set a wildcard. The service's external Swarm token will override onboarding's token in the running Gateway.
3. Create `openclaw_gateway_token` as an external Swarm secret from a strong random value. Preserve a copy in your password manager so you can paste it into Control UI. For example, on a manager *outside* the Git checkout:
   ```bash
   umask 077
   openssl rand -hex 32 > /root/openclaw_gateway_token.local
   docker secret create openclaw_gateway_token /root/openclaw_gateway_token.local
   # Store the token safely; remove this temporary plaintext file afterward.
   ```
4. Verify **21001/tcp** is not used by Swarm, by a standalone container or by a host process across the relevant nodes. Restrict ingress on all nodes to trusted admin clients. Direct HTTP sends the credential over the LAN unless transported via a secure tunnel.
5. Before initial deploy, apply `ai_agents_eligible=true` **only to vs15**. After both agents are healthy, label **vs11 and vs12** as backup nodes. Do not apply `node.hostname == vs15` permanently.

## Deploy and inspect (from this directory on a Swarm manager)

```bash
docker stack config -c compose.yml
./start
docker service ps openclaw_gateway
docker service logs --tail 100 openclaw_gateway
```

If scripts are not executable, use `sh start` (same convention as the existing stacks).

The Control UI is available on the published port, subject to Gateway token auth and device pairing. For a trusted localhost browser origin, use an SSH forward to any healthy Swarm node, e.g. `ssh -L 21001:127.0.0.1:21001 <reachable-node>` and visit `http://localhost:21001`. Browser features may require HTTPS or localhost for a secure context.

Swarm placement reschedules on node failure *when resources, node eligibility and NFS are available*; it does not force failback. During a network partition, old and replacement tasks must not write simultaneously to the same state. Stop-first updates are configured, but they do not constitute distributed fencing.

Do not enable Docker-backed sandbox, privileged mode, or additional host mounts without an explicit new approval.
