"""
Sovereignty verification — Phase 9 implementation (M6).

Complements tools/egress_monitor.sh (host-level tcpdump capture, requires
sudo — meant for the recorded demo/manual audit). This module is the
container-native, always-available runtime check the app itself can call and
expose via API, needing no elevated privileges or extra tooling:

  - verify_no_egress(): actually attempts an outbound connection to a public
    IP and reports whether it succeeded. A real runtime probe, not just a
    config claim.
  - monitor_network_events(): lists this process's currently open outbound
    connections (via /proc/net/tcp[6] on Linux containers) and flags any
    remote address that isn't one of the declared internal services.
  - generate_sovereignty_report(): bundles the above with model-hash
    verification and RBAC route coverage into one exportable report — the
    DoD's "sovereignty report exports cleanly".
"""
from __future__ import annotations
import ipaddress
import logging
import os
import socket

logger = logging.getLogger(__name__)

# The only hosts EdgeMind is *supposed* to talk to — every other outbound
# destination is, by definition, an egress violation for a sovereign system.
_INTERNAL_HOST_ENV_VARS = ["DATABASE_URL", "QDRANT_URL", "MINIO_URL", "OLLAMA_BASE_URL"]


def list_allowed_internal_hosts() -> list[str]:
    """The internal Docker-Compose service hostnames this backend is configured
    to reach — derived from env vars, not hardcoded, so it stays accurate as
    deployment config changes."""
    hosts = {"localhost", "127.0.0.1"}
    for var in _INTERNAL_HOST_ENV_VARS:
        value = os.getenv(var)
        if not value:
            continue
        # crude host extraction good enough for postgresql://user:pass@host:port/db
        # and http://host:port shapes without pulling in urllib for a one-liner
        rest = value.split("://", 1)[-1]
        rest = rest.split("@")[-1]
        host = rest.split("/")[0].split(":")[0]
        if host:
            hosts.add(host)
    return sorted(hosts)


def verify_no_egress(probe_host: str = "8.8.8.8", probe_port: int = 53, timeout: float = 2.0) -> dict:
    """
    Attempt a real outbound TCP connection to a well-known public IP from this
    running container only.

    Host OS networking is intentionally out of scope for this sovereignty
    verdict: the badge is about the container's network isolation, not whether
    the laptop/host has internet connectivity.

    Returns {
        "scope": "container",
        "egress_blocked": bool,
        "probe": "<host>:<port>",
        "detail": str,
    }

    egress_blocked=True means the container could NOT reach a public endpoint
    (refused, timed out, network unreachable) — i.e. sovereignty holds.
    egress_blocked=False means this container CAN reach the public internet — a
    violation that should fail the DoD check.
    """
    try:
        with socket.create_connection((probe_host, probe_port), timeout=timeout):
            return {
                "scope": "container",
                "egress_blocked": False,
                "probe": f"{probe_host}:{probe_port}",
                "detail": "Outbound connection from this container to a public host succeeded — egress is NOT blocked.",
            }
    except OSError as exc:
        return {
            "scope": "container",
            "egress_blocked": True,
            "probe": f"{probe_host}:{probe_port}",
            "detail": f"Outbound connection from this container failed as expected ({exc}) — egress is blocked.",
        }


def _hex_ip_to_str(hex_ip: str) -> str:
    """Decode /proc/net/tcp's IPv4 address format: 4 bytes stored in
    little-endian word order, e.g. "0100007F" -> bytes 01 00 00 7F -> reversed
    7F 00 00 01 -> 127.0.0.1."""
    return socket.inet_ntoa(bytes.fromhex(hex_ip)[::-1])


def _is_local_or_internal_ip(ip: str) -> bool:
    """Treat loopback and private Docker/host-local ranges as internal so the
    sovereignty check only flags truly external destinations. This avoids
    misclassifying the Docker bridge/gateway or localhost traffic as egress."""
    if ip in {"0.0.0.0", "::", "127.0.0.1", "::1", "localhost"}:
        return True
    try:
        parsed = ipaddress.ip_address(ip)
        return (
            parsed.is_loopback
            or parsed.is_private
            or parsed.is_link_local
            or parsed.is_multicast
            or parsed.is_unspecified
            or parsed.is_reserved
        )
    except ValueError:
        return False


def monitor_network_events() -> dict:
    """
    Best-effort, container-native connection listing (Linux /proc/net/tcp) —
    no tcpdump/root required. Returns established outbound connections from
    this container's network namespace and flags any remote address not in the
    allowed internal service list.

    This deliberately ignores the host OS network state; sovereignty is judged
    on the container's own isolation, not on whether the laptop itself has
    internet access.

    Unsupported platforms (non-Linux, /proc unavailable) degrade to an empty,
    explicitly-marked-unsupported result rather than a hard failure.
    """
    allowed_hosts = list_allowed_internal_hosts()
    allowed_ips = set()
    for host in allowed_hosts:
        try:
            allowed_ips.add(socket.gethostbyname(host))
        except OSError:
            continue
    allowed_ips.update({"0.0.0.0", "127.0.0.1"})

    connections = []
    flagged = []
    for proc_file in ("/proc/net/tcp", "/proc/net/tcp6"):
        if not os.path.isfile(proc_file):
            continue
        try:
            with open(proc_file) as f:
                lines = f.readlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 4:
                continue
            local, remote, state = fields[1], fields[2], fields[3]
            if state != "01":  # 01 = ESTABLISHED
                continue
            try:
                remote_ip_hex, remote_port_hex = remote.split(":")
                remote_ip = _hex_ip_to_str(remote_ip_hex) if len(remote_ip_hex) == 8 else remote_ip_hex
                remote_port = int(remote_port_hex, 16)
            except (ValueError, OSError):
                continue
            entry = {"remote_ip": remote_ip, "remote_port": remote_port}
            connections.append(entry)
            if remote_ip not in allowed_ips and not _is_local_or_internal_ip(remote_ip):
                flagged.append(entry)

    supported = any(os.path.isfile(p) for p in ("/proc/net/tcp", "/proc/net/tcp6"))
    return {
        "supported": supported,
        "allowed_hosts": allowed_hosts,
        "connections": connections,
        "flagged_external_connections": flagged,
    }


def generate_sovereignty_report(db=None) -> dict:
    """
    Bundle egress verification + live connection audit + model-hash status +
    RBAC route coverage into one exportable report. `db`, if given, adds an
    audit-log chain-verification summary (Phase 9 M5).
    """
    from models.registry import registry

    egress = verify_no_egress()
    network = monitor_network_events()

    model_hash_status = {}
    for model_id in registry.models.keys():
        try:
            model_hash_status[model_id] = registry.verify_model_hash(model_id)
        except Exception as exc:
            model_hash_status[model_id] = {"verified": False, "detail": str(exc)}

    report = {
        "sovereign": egress["egress_blocked"] and not network["flagged_external_connections"],
        "egress_check": egress,
        "network_monitor": network,
        "model_hash_verification": model_hash_status,
        "rbac_protected_routes": [
            "/api/agent", "/api/tasks", "/api/rag/search", "/api/vision/*",
            "/api/documents/*", "/api/artifacts/*", "/api/audit/*", "/api/sovereignty/*",
            "/api/approvals/*",
        ],
    }

    if db is not None:
        from database.repo import verify_audit_chain
        report["audit_log_chain"] = verify_audit_chain(db)

    return report


def enforce_airgap_isolation() -> dict:
    """
    Enforce air-gapped isolation at the container network namespace layer.
    Removes the default gateway route (0.0.0.0/0) so outbound traffic to public
    IPs fails immediately at the Linux kernel level.
    
    Direct subnet routes (172.x.0.0/16) and loopback are preserved, so:
      - Inter-container traffic (Postgres, MinIO, Qdrant, Ollama) continues uninterrupted.
      - Inbound traffic from host forwarded ports (127.0.0.1:8000 via bridge gateway 172.x.0.1)
        continues uninterrupted.
      - Public outbound probes (e.g. 8.8.8.8) are strictly blocked.
    
    Uses Python native Linux Netlink socket (AF_NETLINK / RTM_DELROUTE) with
    fallback to subprocess 'ip route del default'. Safe, idempotent, and non-disruptive.
    """
    import errno
    import struct
    import subprocess
    import shutil

    # Try native Linux Netlink route deletion first
    if hasattr(socket, "AF_NETLINK") and hasattr(socket, "NETLINK_ROUTE"):
        try:
            sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE)
            sock.bind((0, 0))
            # Delete default route (dst 0.0.0.0/0) in main routing table (table 254)
            rtmsg = struct.pack("BBBBBBBBI", socket.AF_INET, 0, 0, 0, 254, 0, 0, 1, 0)
            nlmsg_len = 16 + len(rtmsg)
            # RTM_DELROUTE = 25, NLM_F_REQUEST = 1, NLM_F_ACK = 4
            nlmsghdr = struct.pack("IHHII", nlmsg_len, 25, 1 | 4, 1, os.getpid())
            sock.send(nlmsghdr + rtmsg)
            resp = sock.recv(1024)
            sock.close()
            if len(resp) >= 20:
                err = struct.unpack("i", resp[16:20])[0]
                # 0 = success, -ESRCH (-3) or -ENOENT (-2) = already deleted
                if err in (0, -errno.ESRCH, -errno.ENOENT):
                    logger.info("Default gateway successfully removed via Netlink (air-gap enforced).")
                    return {
                        "enforced": True,
                        "method": "netlink",
                        "detail": "Default gateway removed. Outbound internet egress blocked; local Docker network retained.",
                    }
                else:
                    logger.warning(f"Netlink RTM_DELROUTE returned error code: {err}")
        except Exception as exc:
            logger.warning(f"Netlink route deletion attempt failed: {exc}")

    # Fallback to ip route del default if ip tool is installed
    if shutil.which("ip"):
        try:
            proc = subprocess.run(
                ["ip", "route", "del", "default"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if proc.returncode == 0 or "No such process" in proc.stderr:
                logger.info("Default gateway removed via ip route del default (air-gap enforced).")
                return {
                    "enforced": True,
                    "method": "ip_tool",
                    "detail": "Default gateway removed via iproute2. Outbound egress blocked.",
                }
            logger.warning(f"ip route del default returned {proc.returncode}: {proc.stderr}")
        except Exception as exc:
            logger.warning(f"Subprocess ip route deletion failed: {exc}")

    return {
        "enforced": False,
        "method": "none",
        "detail": "Could not remove default route. Ensure container has NET_ADMIN capability.",
    }
