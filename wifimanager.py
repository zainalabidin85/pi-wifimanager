#!/usr/bin/env python3
import logging
import os
import subprocess
import threading
import time

from flask import Flask, redirect, render_template, request

WIFI_IFACE = "wlan0"
AP_SSID = "Pi5-Setup"
AP_PASSWORD = ""  # WPA2 requires 8+ chars; set to "" for an open AP
AP_CON_NAME = "PiWifiManagerAP"
BOOT_WAIT = 15        # seconds to wait at boot for an already-known network
CONNECT_TIMEOUT = 20  # seconds to wait for a new connection to come up

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("wifimanager")

app = Flask(__name__)


def run(cmd, check=True):
    log.info("running: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def is_connected(wifi_iface=WIFI_IFACE):
    result = subprocess.run(
        ["nmcli", "-t", "-f", "DEVICE,STATE", "device"],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        dev, _, state = line.partition(":")
        if dev == wifi_iface:
            return state == "connected"
    return False


def start_ap(wifi_iface=WIFI_IFACE):
    log.info("Starting access point %s", AP_SSID)
    cmd = ["nmcli", "device", "wifi", "hotspot", "ifname", wifi_iface,
           "con-name", AP_CON_NAME, "ssid", AP_SSID]
    if AP_PASSWORD:
        cmd += ["password", AP_PASSWORD]
    run(cmd)
    if not AP_PASSWORD:
        # `nmcli device wifi hotspot` always secures the AP, generating a random
        # WPA2 password if none is given -- explicitly strip security for a true
        # open network.
        run(["nmcli", "connection", "modify", AP_CON_NAME, "remove", "802-11-wireless-security"])
        run(["nmcli", "connection", "up", AP_CON_NAME])


def scan_networks(wifi_iface=WIFI_IFACE):
    run(["nmcli", "device", "wifi", "rescan", "ifname", wifi_iface], check=False)
    time.sleep(2)
    result = run(
        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "ifname", wifi_iface],
        check=False,
    )
    seen = set()
    networks = []
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) < 3:
            continue
        ssid, signal, security = parts[0], parts[1], parts[2]
        if not ssid or ssid == AP_SSID or ssid in seen:
            continue
        seen.add(ssid)
        networks.append({"ssid": ssid, "signal": signal, "secured": security not in ("", "--")})
    networks.sort(key=lambda n: -int(n["signal"] or 0))
    return networks


def try_connect(ssid, password, wifi_iface=WIFI_IFACE):
    cmd = ["nmcli", "device", "wifi", "connect", ssid, "ifname", wifi_iface]
    if password:
        cmd += ["password", password]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.warning("connect failed: %s", result.stderr.strip())
        return False
    for _ in range(CONNECT_TIMEOUT):
        if is_connected(wifi_iface):
            return True
        time.sleep(1)
    return False


def delayed_exit(delay=3):
    time.sleep(delay)
    os._exit(0)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", networks=scan_networks())


@app.route("/connect", methods=["POST"])
def connect():
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "")
    if not ssid:
        return render_template("index.html", networks=scan_networks(), error="Please choose a network.")

    log.info("Attempting to connect to %s", ssid)
    if try_connect(ssid, password):
        subprocess.run(["nmcli", "connection", "delete", AP_CON_NAME], capture_output=True)
        threading.Thread(target=delayed_exit, daemon=True).start()
        return render_template("success.html", ssid=ssid)

    return render_template(
        "index.html", networks=scan_networks(),
        error=f"Could not connect to '{ssid}'. Check the password and try again.",
    )


@app.route("/<path:path>", methods=["GET"])
def catch_all(path):
    # OS captive-portal probes (Android /generate_204, Apple
    # /hotspot-detect.html, Windows /connecttest.txt, etc.) all land here since
    # DNS resolves every hostname to us. Redirecting instead of 404ing is what
    # makes those OSes pop the "sign in to network" portal automatically.
    return redirect("/", code=302)


def main():
    log.info("Waiting up to %ss for an existing WiFi connection...", BOOT_WAIT)
    for _ in range(BOOT_WAIT):
        if is_connected(WIFI_IFACE):
            log.info("Already connected, WiFiManager exiting.")
            return
        time.sleep(1)

    start_ap(WIFI_IFACE)
    app.run(host="0.0.0.0", port=80)


if __name__ == "__main__":
    main()
