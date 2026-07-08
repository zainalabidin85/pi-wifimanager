#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo ./install.sh"
  exit 1
fi

INSTALL_DIR=/opt/pi-wifimanager
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing dependencies..."
apt-get update
apt-get install -y network-manager python3-flask

echo "Enabling NetworkManager..."
systemctl unmask NetworkManager
systemctl enable --now NetworkManager

# On older Raspberry Pi OS (Bullseye/Buster) networking is managed by dhcpcd by
# default; hand control of wlan0 to NetworkManager so nmcli can manage AP/STA mode.
if [ -f /etc/dhcpcd.conf ] && systemctl is-enabled dhcpcd &>/dev/null; then
  grep -q "^denyinterfaces wlan0" /etc/dhcpcd.conf || echo "denyinterfaces wlan0" >> /etc/dhcpcd.conf
  systemctl restart dhcpcd || true
fi

echo "Copying files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/wifimanager.py" "$SCRIPT_DIR/templates" "$INSTALL_DIR/"

echo "Setting up captive portal DNS redirect..."
mkdir -p /etc/NetworkManager/dnsmasq-shared.d
cat > /etc/NetworkManager/dnsmasq-shared.d/captive-portal.conf <<'EOF'
# Answer every DNS query on the hotspot with the Pi's own address so devices
# detect a captive portal and prompt the user to sign in automatically.
address=/#/10.42.0.1
EOF

echo "Installing systemd service..."
cp "$SCRIPT_DIR/wifimanager.service" /etc/systemd/system/wifimanager.service
systemctl daemon-reload
systemctl enable wifimanager.service

echo ""
echo "Done. Reboot to test (sudo reboot), or start it now with: sudo systemctl start wifimanager"
echo "If the Pi has no known WiFi connection, it will start an AP named 'Pi5-Setup' (password: 12345678)."
