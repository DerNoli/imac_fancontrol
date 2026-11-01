#!/usr/bin/python3
# Save as: macfantray
# chmod +x macfantray

import sys
import os
import glob
import subprocess
import configparser
import xml.etree.ElementTree as ET
import math
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QColor, QPen
from PyQt6.QtCore import QTimer, Qt, QRectF

# ---------------------------------------------------------
# CONFIG (muss zu macfan.sh passen)
# ---------------------------------------------------------

CPU_LABEL = "TCXc"
GPU_LABEL = "TG0d"
CPU_FALLBACK = "temp17_input"
GPU_FALLBACK = "temp25_input"

MIN_FAN = 1500
MAX_FAN = 4000
MIN_TEMP = 40
MAX_TEMP = 65
CPU_WEIGHT = 0.4
GPU_WEIGHT = 0.7
K = 0.12

# Icon: wie fein der Füllstand abgestuft wird (Anzahl Schritte)
ICON_STEPS = 24

# ---------------------------------------------------------
# HWMON HANDLING
# ---------------------------------------------------------

def read_str(path):
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return None


def read_int(path):
    val = read_str(path)
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def find_hwmon():
    """hwmon-Verzeichnis des applesmc anhand des Namens finden."""
    for d in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        if read_str(os.path.join(d, "name")) == "applesmc":
            return d
    return None


def find_temp(hw, label, fallback):
    """temp*_input-Datei zu einem SMC-Key-Label finden (case-sensitiv)."""
    for f in glob.glob(os.path.join(hw, "temp*_label")):
        if read_str(f) == label:
            return f[:-len("_label")] + "_input"
    return os.path.join(hw, fallback)


# ---------------------------------------------------------
# LOGARITHMIC FAN CURVE (identisch zu macfan.sh)
# ---------------------------------------------------------

def fan_curve(temp, min_fan, max_fan):
    if temp <= MIN_TEMP:
        return min_fan
    if temp >= MAX_TEMP:
        return max_fan
    x = temp - MIN_TEMP
    rng = MAX_TEMP - MIN_TEMP
    scale = (max_fan - min_fan) / math.log(1 + K * rng)
    return int(round(min_fan + math.log(1 + K * x) * scale))


# ---------------------------------------------------------
# DYNAMIC THERMOMETER ICON
# ---------------------------------------------------------

def temp_fraction(weighted):
    """Gewichtete Temperatur auf 0.0 .. 1.0 abbilden (MIN_TEMP .. MAX_TEMP)."""
    frac = (weighted - MIN_TEMP) / (MAX_TEMP - MIN_TEMP)
    return max(0.0, min(1.0, frac))


def fill_color(frac):
    """Grün (kalt) -> Gelb -> Rot (heiß)."""
    hue = int(round(120 * (1.0 - frac)))
    return QColor.fromHsv(hue, 220, 235)


def build_icon(frac, dark):
    """Thermometer zeichnen; die Füllung steigt mit der Temperatur."""
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    outline = QColor(235, 235, 235) if dark else QColor(55, 55, 55)

    # Außenform: Röhre + Kugel
    outer = QPainterPath()
    outer.addRoundedRect(QRectF(23, 3, 18, 44), 9, 9)
    outer.addEllipse(QRectF(19, 37, 26, 26))
    outer = outer.simplified()

    # Innenform (Füllbereich): Röhre + Kugel
    inner = QPainterPath()
    inner.addRoundedRect(QRectF(28, 8, 8, 42), 4, 4)
    inner.addEllipse(QRectF(24, 42, 16, 16))
    inner = inner.simplified()

    # Füllung: Kugel immer gefüllt, Röhre steigt mit frac
    level_empty = 46.0   # Oberkante der Kugel
    level_full = 8.0     # Oberkante der Röhre
    level_y = level_empty - frac * (level_empty - level_full)

    p.save()
    p.setClipPath(inner)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill_color(frac))
    p.drawRect(QRectF(0, level_y, size, size - level_y))
    p.restore()

    # Umriss
    pen = QPen(outline)
    pen.setWidthF(4.0)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(outer)

    # Skalenstriche rechts der Röhre
    tick_pen = QPen(outline)
    tick_pen.setWidthF(3.0)
    tick_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(tick_pen)
    for y in (12, 22, 32):
        p.drawLine(46, y, 54, y)

    p.end()
    return QIcon(pm)


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
        except Exception:
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
        except Exception:
            return None

    def detect_xfce_dark(self):
        path = os.path.expanduser("~/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml")
        if not os.path.exists(path):
            return None
        try:
            root = ET.parse(path).getroot()
            for prop in root.iter("property"):
                if prop.get("name") == "ThemeName":
                    return "dark" in prop.get("value", "").lower()
        except Exception:
            pass
        return None

    def detect_lxqt_dark(self):
        path = os.path.expanduser("~/.config/lxqt/session.conf")
        if not os.path.exists(path):
            return None
        cfg = configparser.ConfigParser()
        try:
            cfg.read(path)
            return "dark" in cfg["General"]["theme"].lower()
        except Exception:
            return None

    def detect_env_dark(self):
        for var in ["GTK_THEME", "QT_QPA_PLATFORMTHEME"]:
            if var in os.environ and "dark" in os.environ[var].lower():
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

        self.hw = None
        self.cpu_path = None
        self.gpu_path = None
        self.resolve_paths()

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

        self.icon_cache = {}
        self.last_icon_key = None
        self.last_mode = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(2000)

        self.update()

    def resolve_paths(self):
        self.hw = find_hwmon()
        if self.hw:
            self.cpu_path = find_temp(self.hw, CPU_LABEL, CPU_FALLBACK)
            self.gpu_path = find_temp(self.hw, GPU_LABEL, GPU_FALLBACK)

    def set_fill_icon(self, weighted):
        """Icon setzen; neu zeichnen nur, wenn sich Stufe oder Theme ändern."""
        dark = self.theme.is_dark()
        step = int(round(temp_fraction(weighted) * ICON_STEPS))
        key = (step, dark)

        if key == self.last_icon_key:
            return

        if key not in self.icon_cache:
            self.icon_cache[key] = build_icon(step / ICON_STEPS, dark)

        self.tray.setIcon(self.icon_cache[key])
        self.last_icon_key = key

    def update(self):
        # Pfad neu bestimmen, falls hwmon fehlt (z. B. Modul neu geladen)
        if not self.hw or not os.path.isdir(self.hw):
            self.resolve_paths()
        if not self.hw:
            self.info_action.setText("applesmc hwmon nicht gefunden")
            self.tray.setToolTip("applesmc hwmon nicht gefunden")
            return

        cpu = read_int(self.cpu_path) // 1000
        gpu = read_int(self.gpu_path) // 1000
        fan = read_int(os.path.join(self.hw, "fan1_input"))
        hw_min = read_int(os.path.join(self.hw, "fan1_min")) or MIN_FAN
        hw_max = read_int(os.path.join(self.hw, "fan1_max")) or MAX_FAN
        min_fan = max(MIN_FAN, hw_min)
        max_fan = min(MAX_FAN, hw_max)

        weighted = int(round(cpu * CPU_WEIGHT + gpu * GPU_WEIGHT))
        target_rpm = fan_curve(weighted, min_fan, max_fan)

        pwm = read_str(os.path.join(self.hw, "pwm1_enable"))
        ctrl = "manuell" if pwm == "1" else "Automatik" if pwm in ("0", "2") else "?"

        self.set_fill_icon(weighted)

        mode = "COOL" if weighted < 45 else "NORMAL" if weighted < 70 else "HOT"

        self.info_action.setText(
            f"CPU: {cpu}°C | GPU: {gpu}°C | Fan: {fan} RPM | Target: {target_rpm} RPM | {mode} | {ctrl}"
        )

        self.tray.setToolTip(
            f"CPU: {cpu}°C\nGPU: {gpu}°C\nFan: {fan} RPM\nTarget: {target_rpm} RPM\n"
            f"Mode: {mode}\nSteuerung: {ctrl}"
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
