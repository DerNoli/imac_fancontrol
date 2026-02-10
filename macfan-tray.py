#!/usr/bin/python3
# Save as: macfantray
# chmod +x macfantray

import sys
import os
import subprocess
import configparser
import xml.etree.ElementTree as ET
import math
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

# Sensor Paths
CPU_SENSOR = "/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00/device:5e/APP0001:00/temp10_input"
GPU_SENSOR = "/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00/device:5e/APP0001:00/temp23_input"
FAN_SENSOR = "/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00/device:5e/APP0001:00/fan1_input"

def read_int(path):
    try:
        with open(path, 'r') as f:
            return int(f.read().strip())
    except:
        return 0

# ---------------------------------------------------------
# LOGARITHMIC FAN CURVE
# ---------------------------------------------------------

def fan_curve(temp):
    """
    Logarithmische Lüfterkurve:
    - temp: gewichtete Temperatur (°C)
    - Rückgabe: Ziel-RPM
    """

    # Sicherheitskorridor
    temp = max(30, min(temp, 95))

    # Logarithmische Steigung
    # 30°C → ~800 RPM
    # 50°C → ~1500 RPM
    # 70°C → ~2500 RPM
    # 90°C → ~3500 RPM
    rpm = 800 + 1200 * math.log1p((temp - 30) / 10)

    # Begrenzen
    return int(max(800, min(rpm, 4000)))


# ---------------------------------------------------------
# UNIVERSAL THEME DETECTION
# ---------------------------------------------------------

class ThemeDetector:
    def __init__(self):
        self.cached_dark = False
        self.update_theme()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_theme)
        self.timer.start(60000)

    def _get_gsettings(self, schema, key):
        try:
            cmd = ["gsettings", "get", schema, key]
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip().strip("'")
        except:
            return None

    def detect_gnome_dark(self):
        scheme = self._get_gsettings("org.gnome.desktop.interface", "color-scheme")
        if scheme:
            return scheme == "prefer-dark"
        return None

    def detect_cinnamon_dark(self):
        theme = self._get_gsettings("org.cinnamon.desktop.interface", "gtk-theme")
        if theme:
            return "dark" in theme.lower()
        return None

    def detect_mate_dark(self):
        theme = self._get_gsettings("org.mate.interface", "gtk-theme")
        if theme:
            return "dark" in theme.lower()
        return None

    def detect_kde_dark(self):
        path = os.path.expanduser("~/.config/kdeglobals")
        if not os.path.exists(path):
            return None
        cfg = configparser.ConfigParser()
        try:
            cfg.read(path)
            scheme = cfg["General"]["ColorScheme"].lower()
            return "dark" in scheme
        except:
            return None

    def detect_xfce_dark(self):
        path = os.path.expanduser("~/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml")
        if not os.path.exists(path):
            return None
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            for prop in root.findall("property"):
                if prop.get("name") == "ThemeName":
                    theme = prop.get("value", "").lower()
                    return "dark" in theme
        except:
            pass
        return None

    def detect_lxqt_dark(self):
        path = os.path.expanduser("~/.config/lxqt/session.conf")
        if not os.path.exists(path):
            return None
        cfg = configparser.ConfigParser()
        try:
            cfg.read(path)
            theme = cfg["General"]["theme"].lower()
            return "dark" in theme
        except:
            return None

    def detect_env_dark(self):
        for var in ["GTK_THEME", "QT_QPA_PLATFORMTHEME"]:
            if var in os.environ:
                if "dark" in os.environ[var].lower():
                    return True
        return None

    def update_theme(self):
        detectors = [
            self.detect_gnome_dark,
            self.detect_cinnamon_dark,
            self.detect_mate_dark,
            self.detect_kde_dark,
            self.detect_xfce_dark,
            self.detect_lxqt_dark,
            self.detect_env_dark,
        ]
        for fn in detectors:
            result = fn()
            if result is not None:
                self.cached_dark = result
                return
        self.cached_dark = False

    def is_dark(self):
        return self.cached_dark


# ---------------------------------------------------------
# MAIN APP
# ---------------------------------------------------------

class MacFanTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.theme = ThemeDetector()

        self.menu = QMenu()
        self.info_action = self.menu.addAction("Loading…")
        self.info_action.setDisabled(True)
        self.menu.addSeparator()

        refresh_action = self.menu.addAction("Refresh Now")
        refresh_action.triggered.connect(self.update)

        quit_action = self.menu.addAction("Quit")
        quit_action.triggered.connect(self.app.quit)

        self.tray = QSystemTrayIcon()
        self.tray.setContextMenu(self.menu)
        self.tray.setVisible(True)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(2000)

        self.last_mode = None

        self.update()

    def themed_icon(self, cold, normal, hot, weighted):
        dark = self.theme.is_dark()
        mode_key = "dark" if dark else "light"
        
        if weighted < 45:
            return QIcon(cold[mode_key])
        elif weighted < 70:
            return QIcon(normal[mode_key])
        else:
            return QIcon(hot[mode_key])

    def update(self):
        cpu = read_int(CPU_SENSOR) // 1000
        gpu = read_int(GPU_SENSOR) // 1000
        fan = read_int(FAN_SENSOR)
        weighted = int(cpu * 0.4 + gpu * 0.6)

        target_rpm = fan_curve(weighted)

        cold_icons = {
            "light": "/usr/share/icons/breeze/status/22/temperature-cold.svg",
            "dark": "/usr/share/icons/breeze-dark/status/22/temperature-cold.svg"
        }
        normal_icons = {
            "light": "/usr/share/icons/breeze/status/22/temperature-normal.svg",
            "dark": "/usr/share/icons/breeze-dark/status/22/temperature-normal.svg"
        }
        hot_icons = {
            "light": "/usr/share/icons/breeze/status/22/temperature-hot.svg",
            "dark": "/usr/share/icons/breeze-dark/status/22/temperature-hot.svg"
        }

        icon = self.themed_icon(cold_icons, normal_icons, hot_icons, weighted)
        self.tray.setIcon(icon)

        mode = "COOL" if weighted < 45 else "NORMAL" if weighted < 70 else "HOT"

        self.info_action.setText(
            f"CPU: {cpu}°C | GPU: {gpu}°C | Fan: {fan} RPM | Target: {target_rpm} RPM | Mode: {mode}"
        )

        self.tray.setToolTip(
            f"CPU: {cpu}°C\nGPU: {gpu}°C\nFan: {fan} RPM\nTarget: {target_rpm} RPM\nMode: {mode}"
        )

        if mode != self.last_mode:
            if self.last_mode is not None:
                self.tray.showMessage(
                    "MacFanTray",
                    f"Profil gewechselt: {mode}\nCPU {cpu}°C | GPU {gpu}°C | Fan {fan} RPM | Ziel {target_rpm} RPM",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000
                )
            self.last_mode = mode

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    MacFanTray().run()
