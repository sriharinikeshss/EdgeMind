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
    Attempt a real outbound TCP connection to a well-known public IP.
    Returns {"egress_blocked": bool, "probe": "<host>:<port>", "detail": str}.

    egress_blocked=True means the connection could NOT be made (refused,
    timed out, network unreachable) — i.e. sovereignty holds. egress_blocked
    =False means the container CAN reach the public internet — a violation
    that should fail the DoD check.
    """
    try:
        with socket.create_connection((probe_host, probe_port), timeout=timeout):
            return {
                "egress_blocked": False,
                "probe": f"{probe_host}:{probe_port}",
                "detail": "Outbound connection to a public host succeeded — egress is NOT blocked.",
            }
    except OSError as exc:
        return {
            "egress_blocked": True,
            "probe": f"{probe_host}:{probe_port}",
            "detail": f"Outbound connection failed as expected ({exc}) — egress is blocked.",
        }


def _hex_ip_to_str(hex_ip: str) -> str:
    """Decode /proc/net/tcp's IPv4 address format: 4 bytes stored in
    little-endian word order, e.g. "0100007F" -> bytes 01 00 00 7F -> reversed
    7F 00 00 01 -> 127.0.0.1."""
    return socket.inet_ntoa(bytes.fromhex(hex_ip)[::-1])


def monitor_network_events() -> dict:
    """
    Best-effort, container-native connection listing (Linux /proc/net/tcp) —
    no tcpdump/root required. Returns established outbound connections and
    flags any remote address not in list_allowed_internal_hosts()'s resolved
    IPs. Unsupported platforms (non-Linux, /proc unavailable) degrade to an
    empty, explicitly-marked-unsupported result rather than a hard failure.
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
            if remote_ip not in allowed_ips and remote_ip not in ("0.0.0.0", "::"):
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

    from artifacts.storage import ARTIFACT_ENCRYPTION_ENABLED

    report = {
        "sovereign": egress["egress_blocked"] and not network["flagged_external_connections"],
        "egress_check": egress,
        "network_monitor": network,
        "model_hash_verification": model_hash_status,
        "artifact_encryption_enabled": ARTIFACT_ENCRYPTION_ENABLED,
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
