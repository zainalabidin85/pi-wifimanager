# pi-wifimanager

Headless WiFi provisioning for Raspberry Pi. If the Pi can't find a known WiFi
network at boot, it starts its own access point with a captive portal, so you
can join it from a phone or laptop and pick a network — no keyboard, monitor,
or Ethernet cable required.

## How it works

1. On boot, the service waits up to `BOOT_WAIT` seconds to see if `wlan0` is
   already connected to a known network.
2. If not, it starts an access point (`nmcli device wifi hotspot`) and serves
   a small Flask app on port 80 listing nearby networks.
3. A wildcard DNS entry answers every hostname on the hotspot with the Pi's
   own address, so when a connecting device probes for internet access
   (Android's `/generate_204`, Apple's `/hotspot-detect.html`, Windows'
   `/connecttest.txt`, etc.) it gets redirected back to the Pi instead of the
   real internet — which is what makes phones/laptops automatically pop up
   the "Sign in to network" prompt.
4. Once you submit a network and password, the Pi tries to connect. On
   success it tears down its own access point and exits; the WiFi connection
   persists (managed by NetworkManager) across future reboots.
5. On failure, it shows an error and lets you try again.

## Requirements

- Raspberry Pi OS (or any Debian-based distro) with **NetworkManager**
  managing WiFi — this is the default on current Raspberry Pi OS
- Python 3 with Flask

`install.sh` installs both if they're missing.

## Install

```bash
git clone https://github.com/zainalabidin85/pi-wifimanager.git
cd pi-wifimanager
sudo ./install.sh
```

The installer:

- Installs `network-manager` and `python3-flask`
- Enables NetworkManager (and hands `wlan0` over to it if the Pi was still
  using `dhcpcd`, as on older Raspberry Pi OS releases)
- Copies the app to `/opt/pi-wifimanager`
- Adds a wildcard DNS rule for the hotspot's captive portal
- Installs and enables `wifimanager.service`, so this runs automatically on
  every boot

Reboot to test, or start it immediately:

```bash
sudo systemctl start wifimanager
```

## Configuration

Edit the constants at the top of `wifimanager.py` before installing (or on
the Pi at `/opt/pi-wifimanager/wifimanager.py`, then `sudo systemctl restart
wifimanager`):

| Constant | Default | Description |
|---|---|---|
| `WIFI_IFACE` | `wlan0` | WiFi interface to manage |
| `AP_SSID` | `Pi5-Setup` | Name of the setup access point |
| `AP_PASSWORD` | `` | No Access point password (`""` for an open AP). |
| `AP_CON_NAME` | `PiWifiManagerAP` | NetworkManager connection name used for the temporary AP |
| `BOOT_WAIT` | `15` | Seconds to wait at boot for an existing connection before starting the AP |
| `CONNECT_TIMEOUT` | `20` | Seconds to wait for a newly-submitted network to come up |

## Security

- **Change `AP_SSID`/`AP_PASSWORD` per device.** The values in this repo are
  placeholders, not meant to be used as-is on a real device — especially
  don't reuse your Pi's login/sudo password as the AP password, since it'll
  be broadcast in cleartext to anyone who joins the setup network.
- The setup AP has no internet uplink and only exposes the network picker
  and captive-portal redirect, so the exposure while it's up is limited to
  "whoever knows the AP password can choose which network your Pi joins
  next" — still worth a non-default password.
- Runs as `root` (via systemd, `User=root`) because `nmcli` needs root to
  manage connections.

## Files

| File | Purpose |
|---|---|
| `wifimanager.py` | Flask app + boot logic (AP fallback, network scan, connect) |
| `templates/index.html` | Network picker page |
| `templates/success.html` | Shown after a successful connection |
| `wifimanager.service` | systemd unit, runs on boot |
| `install.sh` | Installs dependencies, DNS redirect, and the systemd service |

## Uninstall

```bash
sudo systemctl disable --now wifimanager
sudo rm /etc/systemd/system/wifimanager.service
sudo rm /etc/NetworkManager/dnsmasq-shared.d/captive-portal.conf
sudo rm -rf /opt/pi-wifimanager
sudo systemctl daemon-reload
```

## Known limitations

- Only tested with NetworkManager's `shared` hotspot mode on Raspberry Pi OS
  Bookworm. Older releases using `dhcpcd`/`hostapd`/`dnsmasq` directly will
  need adjustments.
- Flask's built-in development server is used to keep the dependency list
  minimal — fine for the low, infrequent traffic of a setup portal, but not
  a general-purpose production server.
- Some clients using DNS-over-HTTPS may bypass the wildcard DNS redirect and
  not auto-trigger the captive portal popup; joining the AP and opening any
  `http://` URL manually still works as a fallback.
