#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# FlipLens Pi Core Setup
#
# High-level behaviour:
# - Set the Pi hostname to "fliplens-pi" so it’s reachable as fliplens-pi.local.
# - Install and enable Avahi/mDNS so .local discovery works on the LAN.
# - Install core dependencies (git, python3, venv, pip).
# - Clone or update the FlipLens repo at /home/pi/vinted-ai-cloud.
# - Create a Python venv and install backend requirements.
# - Create and enable a systemd service "fliplens-core.service"
#   that runs `app.py` on port 10000 and restarts on failure.
# - At the end, print instructions on how to check status/logs
#   and how to test http://fliplens-pi.local:10000/health
# ============================================================

TARGET_HOSTNAME="fliplens-pi"
PI_USER="pi"
PI_HOME="/home/${PI_USER}"
REPO_DIR="${PI_HOME}/vinted-ai-cloud"
SERVICE_NAME="fliplens-core"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PORT="10000"

log() {
  echo "[fliplens-pi-setup] $*"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    log "This script must be run as root. Use: sudo ./scripts/pi_core_setup.sh"
    exit 1
  fi
}

set_hostname() {
  local current
  current="$(hostname)"
  if [ "${current}" != "${TARGET_HOSTNAME}" ]; then
    log "Setting hostname from '${current}' to '${TARGET_HOSTNAME}'..."
    hostnamectl set-hostname "${TARGET_HOSTNAME}"

    # Make sure /etc/hosts maps 127.0.1.1 correctly
    if grep -q "127.0.1.1" /etc/hosts; then
      sed -i "s/^127.0.1.1.*/127.0.1.1\t${TARGET_HOSTNAME}/" /etc/hosts
    else
      echo "127.0.1.1\t${TARGET_HOSTNAME}" >> /etc/hosts
    fi
    log "Hostname set. A reboot may be required for some tools to pick this up."
  else
    log "Hostname already '${TARGET_HOSTNAME}', skipping."
  fi
}

install_packages() {
  log "Updating apt and installing required packages..."
  apt-get update
  apt-get install -y \
    avahi-daemon avahi-utils libnss-mdns \
    git python3 python3-venv python3-pip
}

enable_avahi() {
  log "Ensuring Avahi (mDNS) is enabled..."
  systemctl enable avahi-daemon
  systemctl restart avahi-daemon
  log "Avahi daemon is running. Host should be discoverable as ${TARGET_HOSTNAME}.local"
}

ensure_repo() {
  if [ ! -d "${REPO_DIR}/.git" ]; then
    log "Cloning repo into ${REPO_DIR}..."
    sudo -u "${PI_USER}" git clone https://github.com/Pedrothebusdriver/vinted-ai-cloud "${REPO_DIR}"
  else
    log "Repo already exists, pulling latest changes..."
    cd "${REPO_DIR}"
    sudo -u "${PI_USER}" git pull --ff-only || log "git pull failed – please check manually."
  fi
}

setup_venv() {
  cd "${REPO_DIR}"
  if [ ! -d "venv" ]; then
    log "Creating Python virtual environment..."
    sudo -u "${PI_USER}" python3 -m venv venv
  else
    log "Virtualenv already exists, reusing."
  fi

  log "Installing Python dependencies into venv..."
  # shellcheck disable=SC1091
  sudo -u "${PI_USER}" bash -lc "
    set -euo pipefail
    cd '${REPO_DIR}'
    source venv/bin/activate
    pip install --upgrade pip
    if [ -f requirements.txt ]; then
      pip install -r requirements.txt
    else
      echo '[fliplens-pi-setup] WARNING: requirements.txt not found – install deps manually if needed.'
    fi
  "
}

write_service_unit() {
  log "Writing systemd service unit to ${SERVICE_FILE}..."
  cat > "${SERVICE_FILE}" <<'SERVICE_UNIT'
[Unit]
Description=FlipLens Core Backend (Flask on Pi)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${PI_USER}
WorkingDirectory=${REPO_DIR}
Environment="PORT=${PORT}"
ExecStart=${REPO_DIR}/venv/bin/python app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
SERVICE_UNIT
}

enable_service() {
  log "Reloading systemd and enabling ${SERVICE_NAME}..."
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}"
  systemctl restart "${SERVICE_NAME}"
  log "Service ${SERVICE_NAME} is started. Use 'systemctl status ${SERVICE_NAME}' to check."
}

print_summary() {
  cat <<EOF

============================================================
FlipLens Pi Core setup complete (hopefully without fuckery).
------------------------------------------------------------
Hostname:      ${TARGET_HOSTNAME}
Service:       ${SERVICE_NAME}.service
Repo:          ${REPO_DIR}
Port:          ${PORT}
Reachable as:  http://${TARGET_HOSTNAME}.local:${PORT}/health

Useful commands (on the Pi):
  sudo systemctl status ${SERVICE_NAME}
  sudo journalctl -u ${SERVICE_NAME} -f

From your Mac or phone (same Wi-Fi):
  Open Safari/Browser and go to:
    http://${TARGET_HOSTNAME}.local:${PORT}/health

In the mobile app Connect screen:
  Use:
    http://${TARGET_HOSTNAME}.local:${PORT}

============================================================
EOF
}

main() {
  require_root
  set_hostname
  install_packages
  enable_avahi
  ensure_repo
  setup_venv
  write_service_unit
  enable_service
  print_summary
}

main "$@"
