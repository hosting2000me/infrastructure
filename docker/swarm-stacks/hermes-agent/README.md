# Hermes Agent — draft Swarm stack

## Status

Configuration only; **not deployed**. Proposed published WebUI port **21002/tcp -> 9119/tcp**. Not present in the supplied 2026-10-24 Swarm service list; host-level port checks and firewall are still required.

Official reference: https://hermes-agent.nousresearch.com/docs/user-guide/docker

## Runtime

- Official image: `nousresearch/hermes-agent:stable` (pin digest for production).
- Service: `hermes-agent_gateway`, one replica.
- Gateway and Dashboard are supervised by the image's built-in s6 init in the **same container**. Do not override `entrypoint` or create a separate dashboard service for this deployment.
- NFS `nfs02:/docker/volumes/hermes-agent` mounted as `/opt/data` (contains config, `.env`, sessions and credentials).
- External network: `intranet`. Only the dashboard port is published; optional API port **8642 is not published**.
- `HERMES_DASHBOARD=1` and `HERMES_DASHBOARD_HOST=0.0.0.0` enable a reachable dashboard; non-loopback dashboard access requires a configured auth provider and fails closed otherwise.
- No Docker socket, Docker backend or privileged runtime.

## Required setup before launch

1. Confirm the NFS export is mounted from every failover node and writable for Hermes runtime UID/GID **10000:10000** (or explicitly agree a different mapping).
2. **NFS + SQLite:** Hermes stores `state.db` on the data volume. The official Docker documentation explicitly recommends `database.journal_mode: delete` for NFS/SMB mounts instead of the default WAL. Put this in the persistent `/opt/data/config.yaml` **before the first gateway start**:
   ```yaml
   database:
     journal_mode: delete
   ```
   If `state.db` already exists in WAL mode, simply changing the config is insufficient; stop all Hermes processes and run the documented offline `hermes sessions set-journal-mode delete` procedure before restarting.
3. On vs15, initialize the data volume and run the official interactive setup once:
   ```bash
   docker volume create --driver local \
     --opt type=nfs --opt o=nfsvers=4,addr=nfs02,rw \
     --opt device=:/docker/volumes/hermes-agent hermes-agent_data

   docker run --rm -it \
     -v hermes-agent_data:/opt/data \
     nousresearch/hermes-agent:stable setup
   ```
   Configure an LLM provider and gateway channels as required.
3. Put dashboard credentials in **/opt/data/.env on NFS**, never in Git. For trusted LAN/VPN access, official Hermes supports:
   ```dotenv
   HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin
   HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<strong-unique-password>
   HERMES_DASHBOARD_BASIC_AUTH_SECRET=<long-random-session-secret>
   ```
   This password provider is appropriate only on a trusted LAN/VPN, **not for public HTTP Internet exposure**. Use Nous Portal OAuth or OIDC for Internet-facing access. If no valid auth provider is configured, the remote dashboard should fail closed.
4. Verify published **21002/tcp** is unused by Swarm, other Docker containers and host processes. Restrict Swarm ingress port at the firewall on *all nodes*, not only vs15.
5. Apply `ai_agents_eligible=true` initially only on **vs15**, deploy and verify both agents, then mark **vs11** and **vs12** eligible for failover.

## Deploy/inspect (manager)

```bash
docker stack config -c compose.yml
sh start
docker service ps hermes-agent_gateway
docker service logs --tail 100 hermes-agent_gateway
```

Use `http://<reachable-swarm-node>:21002` from a trusted LAN/VPN client, or an SSH localhost tunnel if necessary. No reverse proxy is used.

**Important:** The Hermes state directory is not safe for simultaneous gateway writers. The configured single replica and stop-first update policy reduce planned overlap but Swarm itself does not guarantee fencing in every network-partition failure. Check fencing/availability characteristics of NFS before relying on automatic failover for important data.
