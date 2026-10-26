#!/usr/bin/env python3
"""Read-only Swarm port inventory and candidate allocator (run on a manager).

No network or Swarm changes are made. The CSV registry reserves ports in Git;
live Swarm and local/SSH checks provide runtime evidence.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REGISTRY = Path(__file__).with_name("ports.csv")
BIND_RE = re.compile(r"(?<!\d)(\d+)->\d+/(tcp|udp|sctp)")


def run(args, timeout=15):
    try:
        result = subprocess.run(args, check=True, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise RuntimeError(f"{' '.join(args[:3])}: {detail.strip()}") from exc
    return result.stdout


def registry():
    rows = []
    with REGISTRY.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if not row.get("published") or row["published"].startswith("#"):
                continue
            p = int(row["published"])
            assert 1 <= p <= 65535, row
            proto = row["protocol"].lower().strip()
            assert proto in ("tcp", "udp", "sctp"), row
            assert row["service"], row
            rows.append({**row, "published": p, "protocol": proto})
    return rows


def swarm():
    ids = run(["docker", "service", "ls", "-q"]).split()
    services = []
    for n in range(0, len(ids), 50):
        payload = json.loads(run(["docker", "service", "inspect", *ids[n:n + 50]]))
        for service in payload:
            name = service["Spec"]["Name"]
            endpoint = service.get("Endpoint") or {}
            ports = (endpoint.get("Ports") or endpoint.get("Spec", {}).get("Ports")
                     or service["Spec"].get("EndpointSpec", {}).get("Ports") or [])
            for binding in ports:
                port = binding.get("PublishedPort")
                if port:
                    services.append({
                        "published": int(port),
                        "protocol": binding.get("Protocol", "tcp").lower(),
                        "service": name,
                        "target": binding.get("TargetPort"),
                        "mode": binding.get("PublishMode", "ingress"),
                    })
    return services


def host_ports(ss_output, docker_output, host):
    found = []
    for line in ss_output.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0] not in ("tcp", "udp"):
            continue
        match = re.search(r":(\d+)$", fields[4])
        if match:
            found.append({"published": int(match.group(1)), "protocol": fields[0],
                          "service": f"{host}:socket", "target": "-", "mode": "host"})
    for line in docker_output.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        for port, protocol in BIND_RE.findall(item.get("Ports", "")):
            found.append({"published": int(port), "protocol": protocol,
                          "service": f"{host}:{item.get('Names', 'container')}",
                          "target": "-", "mode": "container"})
    return found


def scan_local():
    return host_ports(run(["ss", "-H", "-lntu"]),
                      run(["docker", "ps", "--format", "{{json .}}"]), "local")


def scan_nodes():
    # Requires passwordless SSH from the manager to every node.
    nodes = run(["docker", "node", "ls", "--format", "{{.Hostname}}"]).splitlines()
    if not nodes:
        raise RuntimeError("No Swarm nodes returned; run from a manager")
    ports, failures = [], []
    for host in nodes:
        command = ("set -e; printf 'BEGIN_SS\\n'; ss -H -lntu; "
                   "printf 'BEGIN_DOCKER\\n'; docker ps --format '{{json .}}'")
        try:
            output = run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4",
                          host, command], timeout=12)
            if "BEGIN_SS\n" not in output or "BEGIN_DOCKER\n" not in output:
                raise RuntimeError("Missing expected scan sections")
            ss_text, docker_text = output.split("BEGIN_DOCKER\n", 1)
            ports += host_ports(ss_text.split("BEGIN_SS\n", 1)[1], docker_text, host)
        except RuntimeError as exc:
            failures.append(f"{host}: {exc}")
    return ports, failures


def print_table(rows):
    for row in sorted(rows, key=lambda r: (r["published"], r["protocol"], r["service"])):
        print(f"{row['published']:>5}/{row['protocol']:<4}  "
              f"{row['service']:<38} -> {str(row.get('target', '-')):<6} "
              f"{row.get('mode', '')}")


def validate_registry(rows, live):
    errors = []
    registered = defaultdict(list)
    for row in rows:
        registered[(row["published"], row["protocol"])].append(row)
    for key, entries in registered.items():
        if len(entries) > 1:
            errors.append(f"Duplicate Git reservation {key}: "
                          + ", ".join(x["service"] for x in entries))
    for row in live:
        for entry in registered.get((row["published"], row["protocol"]), []):
            if entry["service"] != row["service"]:
                errors.append(f"Git reserves {row['published']}/{row['protocol']} "
                              f"for {entry['service']}, live Swarm uses {row['service']}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "next", "check"])
    parser.add_argument("--start", type=int, default=21000)
    parser.add_argument("--end", type=int, default=21999)
    parser.add_argument("--protocol", choices=["tcp", "udp"], default="tcp")
    parser.add_argument("--ssh-all-nodes", action="store_true",
                        help="Also check listening sockets and docker ps on ALL Swarm nodes via SSH")
    args = parser.parse_args()
    if not 1 <= args.start <= args.end <= 65535:
        parser.error("invalid port range")
    try:
        saved = registry()
        live = swarm()
        hosts, failures = scan_nodes() if args.ssh_all_nodes else (scan_local(), [])
    except (RuntimeError, ValueError, AssertionError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")

    issues = validate_registry(saved, live)
    for issue in issues:
        print("CONFLICT:", issue, file=sys.stderr)
    if args.action == "list":
        print("--- Git reservations (not proof of running state) ---")
        print_table(saved)
        print("--- Live Swarm published ports ---")
        print_table(live)
        print("--- Host sockets and local containers ---" if not args.ssh_all_nodes
              else "--- Host sockets and containers across Swarm nodes ---")
        print_table(hosts)
    elif args.action == "next":
        if issues:
            parser.exit(3, "Resolve port registry conflicts before allocating.\n")
        if failures:
            parser.exit(4, "SSH checks incomplete; cannot issue a cluster-verified candidate:\n"
                        + "\n".join(failures) + "\n")
        taken = {(x["published"], x["protocol"]) for x in saved + live + hosts}
        candidate = next((p for p in range(args.start, args.end + 1)
                          if (p, args.protocol) not in taken), None)
        if candidate is None:
            parser.exit(5, "No available candidate in selected range.\n")
        print(f"CANDIDATE: {candidate}/{args.protocol}")
        if not args.ssh_all_nodes:
            print("WARNING: only local host checked; other nodes may have listeners"
                  " or standalone containers. Add --ssh-all-nodes.")
        else:
            print("CHECKED: Git registry, all Swarm services, and host sockets/"
                  "containers on all Swarm nodes.")
        print("Reserve the port in ports.csv in the SAME Git change as the stack;"
              " recheck before deployment.")
    elif args.action == "check" and not issues:
        print("OK: no duplicate Git reservations or Git-vs-live-Swarm conflicts.")
    if failures:
        print("INCOMPLETE SSH CHECK:\n" + "\n".join(failures), file=sys.stderr)
        return 4
    return 3 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
