#!/usr/bin/env bash
# =============================================================================
#  egress_monitor.sh — Phase 1 sovereignty check (M6)
#
#  Wraps tcpdump to capture any packets leaving the host during a test window.
#  Used to verify zero external egress during a KAVACH task run.
#
#  Usage:
#    ./tools/egress_monitor.sh [DURATION_SECONDS]
#
#  Default duration: 60 seconds.
#  Requires: tcpdump (install with apt/brew), sudo privileges.
#
#  Output:
#    - Live packet count to stdout
#    - Detailed capture saved to /tmp/kavach_egress_<timestamp>.pcap
#    - Exit code 0 if no external packets, 1 if external packets detected
#
#  Phase 9: this script is integrated into the automated sovereignty test suite
#  and generates a sovereignty_report.json used for the demo.
# =============================================================================

set -euo pipefail

DURATION="${1:-60}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PCAP_FILE="/tmp/kavach_egress_${TIMESTAMP}.pcap"

# Local subnets that are allowed (Docker bridge networks + loopback)
# Any traffic NOT to these ranges is flagged as external egress.
ALLOWED_NETS="(dst net 127.0.0.0/8 or dst net 10.0.0.0/8 or dst net 172.16.0.0/12 or dst net 192.168.0.0/16)"

echo "=================================================================="
echo " KAVACH Sovereignty Egress Monitor"
echo " Duration  : ${DURATION}s"
echo " Capture   : ${PCAP_FILE}"
echo " Allowed   : loopback + RFC1918 subnets only"
echo "=================================================================="
echo ""
echo "Starting tcpdump... (Ctrl-C to stop early)"
echo ""

# Run tcpdump in background, capturing non-local traffic
sudo tcpdump \
  -i any \
  -w "${PCAP_FILE}" \
  -G "${DURATION}" \
  -W 1 \
  "not (${ALLOWED_NETS})" &

TCPDUMP_PID=$!

# Show a live packet count every 5 seconds
ELAPSED=0
EXTERNAL_COUNT=0
while kill -0 "${TCPDUMP_PID}" 2>/dev/null; do
  sleep 5
  ELAPSED=$((ELAPSED + 5))
  # Count packets in the pcap so far (requires tcpdump read pass)
  if [ -f "${PCAP_FILE}" ]; then
    EXTERNAL_COUNT=$(sudo tcpdump -r "${PCAP_FILE}" 2>/dev/null | wc -l || echo 0)
    echo "[${ELAPSED}s / ${DURATION}s] External packets captured so far: ${EXTERNAL_COUNT}"
  fi
  if [ "${ELAPSED}" -ge "${DURATION}" ]; then
    break
  fi
done

wait "${TCPDUMP_PID}" 2>/dev/null || true

# Final count
if [ -f "${PCAP_FILE}" ]; then
  EXTERNAL_COUNT=$(sudo tcpdump -r "${PCAP_FILE}" 2>/dev/null | wc -l || echo 0)
fi

echo ""
echo "=================================================================="
echo " RESULT"
echo "=================================================================="

if [ "${EXTERNAL_COUNT}" -eq 0 ]; then
  echo " ✅ SOVEREIGNTY VERIFIED — 0 external packets detected."
  echo " Capture saved to: ${PCAP_FILE}"
  exit 0
else
  echo " ❌ SOVEREIGNTY VIOLATION — ${EXTERNAL_COUNT} external packets detected!"
  echo " Inspect the capture: sudo tcpdump -r ${PCAP_FILE} -n"
  echo " Capture saved to: ${PCAP_FILE}"
  exit 1
fi
