#!/usr/bin/env bash
#
# Bootstrap installer for trader-position-analytics systemd unit/timer.
# Run on the VPS once after Phase 1 (Python 3.14 + venv + ChromaDB data) is complete.
#
# Usage:
#   cd /opt/trader_position_analytics
#   bash deploy/install.sh
#
# Re-run is safe (idempotent: cp overwrites, daemon-reload re-reads, enable --now is idempotent).

set -euo pipefail

readonly REPO_DIR="/opt/trader_position_analytics"
readonly SYSTEMD_SRC="${REPO_DIR}/deploy/systemd"
readonly SYSTEMD_DST="/etc/systemd/system"
readonly UNIT_SERVICE="trader-position-analytics.service"
readonly UNIT_TIMER="trader-position-analytics.timer"

log() { printf '[install] %s\n' "$*"; }
fail() { printf '[install ERROR] %s\n' "$*" >&2; exit 1; }

# 1. Pre-flight checks
log "Pre-flight checks..."

[[ -d "${REPO_DIR}" ]] || fail "Repo dir not found: ${REPO_DIR}"
[[ -f "${SYSTEMD_SRC}/${UNIT_SERVICE}" ]] || fail "Missing source: ${SYSTEMD_SRC}/${UNIT_SERVICE}"
[[ -f "${SYSTEMD_SRC}/${UNIT_TIMER}" ]] || fail "Missing source: ${SYSTEMD_SRC}/${UNIT_TIMER}"
[[ -x "${REPO_DIR}/.venv/bin/python3.14" ]] || fail "venv python not found: ${REPO_DIR}/.venv/bin/python3.14"
[[ -f "${REPO_DIR}/.env" ]] || fail ".env not found: ${REPO_DIR}/.env (deploy via GHA first or create manually)"

# 2. Install unit files
log "Installing systemd unit files to ${SYSTEMD_DST}..."
sudo cp "${SYSTEMD_SRC}/${UNIT_SERVICE}" "${SYSTEMD_DST}/${UNIT_SERVICE}"
sudo cp "${SYSTEMD_SRC}/${UNIT_TIMER}" "${SYSTEMD_DST}/${UNIT_TIMER}"
sudo chmod 0644 "${SYSTEMD_DST}/${UNIT_SERVICE}" "${SYSTEMD_DST}/${UNIT_TIMER}"

# 3. Reload systemd
log "Reloading systemd daemon..."
sudo systemctl daemon-reload

# 4. Enable + start timer
log "Enabling and starting timer..."
sudo systemctl enable --now "${UNIT_TIMER}"

# 5. Status
log "Installation complete. Timer status:"
systemctl list-timers "${UNIT_TIMER}" --no-pager || true
echo
log "Service unit status:"
systemctl status "${UNIT_SERVICE}" --no-pager --lines=0 || true
echo
log "Next steps:"
log "  - Manual smoke test: sudo systemctl start ${UNIT_SERVICE}"
log "  - Watch logs:        sudo journalctl -u ${UNIT_SERVICE} -e"
log "  - List timers:       systemctl list-timers ${UNIT_TIMER}"
