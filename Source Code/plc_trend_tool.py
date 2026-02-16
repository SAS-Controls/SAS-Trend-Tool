#!/usr/bin/env python3
"""
PLC Trend Tool v1.0
Southern Automation Solutions

A portable desktop trending application for Allen-Bradley PLCs.
Reads tag data from ControlLogix, CompactLogix, and Micro800 PLCs
using pylogix and displays real-time trends with data export.

Usage (source):
    python plc_trend_tool.py

Usage (compiled):
    plc_trend_tool.exe

Dependencies (for source):
    pip install customtkinter pylogix matplotlib pillow
"""

import csv
import json
import logging
import os
import sys
import time
import threading
import tkinter as tk
from bisect import bisect_left
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# == PyInstaller resource path helper ==
def resource_path(relative_path):
    """Get absolute path to resource - works for dev and PyInstaller bundle.
    Checks multiple locations to handle different working directories."""
    # 1) PyInstaller frozen bundle
    if getattr(sys, 'frozen', False):
        candidate = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(candidate):
            return candidate
        # Also check next to the EXE
        candidate = os.path.join(os.path.dirname(sys.executable), relative_path)
        if os.path.exists(candidate):
            return candidate
        return os.path.join(sys._MEIPASS, relative_path)

    # 2) Next to the script file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(script_dir, relative_path)
    if os.path.exists(candidate):
        return candidate

    # 3) Current working directory
    candidate = os.path.join(os.getcwd(), relative_path)
    if os.path.exists(candidate):
        return candidate

    # 4) Default to script directory (for error messages)
    return os.path.join(script_dir, relative_path)


def _ensure_assets():
    """Extract embedded assets to disk if the assets/ folder is missing.
    This makes the app self-contained — no separate asset files needed."""
    import base64
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, "assets")

    # Check if all expected files exist
    expected = ["icon.ico", "icon.png", "logo.png", "logo_light.png"]
    all_present = all(os.path.exists(os.path.join(assets_dir, f)) for f in expected)
    if all_present:
        return  # Assets folder is fine

    # Try to import embedded data
    try:
        from assets_data import ASSETS
    except ImportError:
        logging.warning("assets/ folder missing and assets_data.py not found — logos will be unavailable")
        return

    # Extract assets to disk
    os.makedirs(assets_dir, exist_ok=True)
    for filename, b64_parts in ASSETS.items():
        filepath = os.path.join(assets_dir, filename)
        if not os.path.exists(filepath):
            try:
                b64_str = "".join(b64_parts)
                data = base64.b64decode(b64_str)
                with open(filepath, "wb") as f:
                    f.write(data)
                logging.info(f"Extracted asset: {filepath} ({len(data):,} bytes)")
            except Exception as e:
                logging.warning(f"Failed to extract {filename}: {e}")

# Run asset extraction at import time
_ensure_assets()

# == Dependency checks ==
try:
    import customtkinter as ctk
except ImportError:
    print("ERROR: customtkinter not installed. Run: pip install customtkinter")
    sys.exit(1)

try:
    from pylogix import PLC
except ImportError:
    print("ERROR: pylogix not installed. Run: pip install pylogix")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
except ImportError:
    print("ERROR: matplotlib not installed. Run: pip install matplotlib")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install pillow")
    sys.exit(1)


# =========================================================================
# THEME -- Matches SAS Network Diagnostic Tool exactly
# Each constant is a (light_mode, dark_mode) tuple.
# CustomTkinter auto-selects the correct value based on appearance mode.
# =========================================================================

# -- SAS Brand Colors --
SAS_BLUE = "#0070BB"
SAS_BLUE_DARK = "#005A96"
SAS_BLUE_LIGHT = "#4F81BD"
SAS_BLUE_ACCENT = "#365F91"
SAS_ORANGE = "#E8722A"
SAS_ORANGE_DARK = "#C45E1F"
SAS_ORANGE_LIGHT = "#F09050"

# -- UI Colors (light, dark) --
BG_DARK = ("#D5D8DC", "#1E1E1E")        # main window background
BG_MEDIUM = ("#C8CCD0", "#2B2B2B")      # sidebar / header bars
BG_CARD = ("#EAECF0", "#333333")        # cards, panels, chart wrapper
BG_CARD_HOVER = ("#DCE0E5", "#3E3E3E")  # hovered cards / rows
BG_INPUT = ("#FFFFFF", "#141414")        # input fields, chart plot area
TEXT_PRIMARY = ("#1A1A2E", "#EAEAEA")
TEXT_SECONDARY = ("#4A5568", "#999999")
TEXT_MUTED = ("#718096", "#666666")
BORDER_COLOR = ("#B0B8C4", "#444444")
BORDER_ACTIVE = SAS_BLUE

# -- Status Colors --
STATUS_GOOD = "#22C55E"
STATUS_WARN = "#F59E0B"
STATUS_ERROR = "#EF4444"
STATUS_INFO = SAS_BLUE_LIGHT
STATUS_OFFLINE = "#6B7280"

# -- Typography --
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"
FONT_SIZE_TITLE = 20
FONT_SIZE_HEADING = 16
FONT_SIZE_SUBHEADING = 14
FONT_SIZE_BODY = 12
FONT_SIZE_SMALL = 11
FONT_SIZE_TINY = 10

# -- Layout --
SIDEBAR_WIDTH = 250
CARD_CORNER_RADIUS = 8
CARD_PADDING = 16
BUTTON_CORNER_RADIUS = 6
BUTTON_HEIGHT = 36
INPUT_HEIGHT = 36

# -- Application Info --
APP_NAME = "PLC Trend Tool"
APP_FULL_NAME = "PLC Trend Tool"
APP_VERSION = "1.0.0"
APP_COMPANY = "Southern Automation Solutions"

# -- Chart Colors --
TRACE_COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6", "#ec4899",
    "#06b6d4", "#f97316", "#14b8a6", "#a855f7", "#84cc16", "#e11d48",
    "#6366f1", "#0ea5e9", "#d946ef", "#facc15",
]

TRENDABLE_TYPES = {
    "BOOL", "SINT", "INT", "DINT", "LINT", "USINT", "UINT",
    "UDINT", "REAL", "LREAL", "BYTE", "WORD", "DWORD", "LWORD",
}


def resolve_color(color) -> str:
    """Resolve a (light, dark) tuple to a single string for raw tkinter widgets."""
    if isinstance(color, (list, tuple)) and len(color) == 2:
        try:
            mode = ctk.get_appearance_mode()
            return color[0] if mode == "Light" else color[1]
        except Exception:
            return color[1]
    if isinstance(color, str) and " " in color and color.startswith("#"):
        parts = color.split()
        if len(parts) == 2 and all(p.startswith("#") for p in parts):
            try:
                mode = ctk.get_appearance_mode()
                return parts[0] if mode == "Light" else parts[1]
            except Exception:
                return parts[1]
    return color


# =========================================================================
# SETTINGS PERSISTENCE
# =========================================================================
def get_settings_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "plc_trend_tool_settings.json")

def load_settings():
    defaults = {
        "theme": "Dark", "last_ip": "", "last_slot": 0,
        "last_controller": "ControlLogix", "sample_rate": "1 sec",
        "window_width": 1400, "window_height": 850,
        "max_points": 100000, "smart_cursor": True,
    }
    path = get_settings_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    return defaults

def save_settings(settings):
    try:
        with open(get_settings_path(), "w") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass


# =========================================================================
# PLC COMMUNICATION MANAGER
# =========================================================================
class PLCManager:
    def __init__(self):
        self.comm = None
        self.connected = False
        self.ip = ""
        self.slot = 0
        self.controller_type = "ControlLogix"
        self.device_name = ""
        self._lock = threading.Lock()

    def connect(self, ip, slot, controller_type):
        self.ip = ip.strip()
        self.slot = int(slot)
        self.controller_type = controller_type
        if not self.ip:
            return False, "IP address is required."
        try:
            with self._lock:
                if self.comm:
                    try: self.comm.Close()
                    except Exception: pass
                self.comm = PLC(self.ip, self.slot)
                self.comm.Micro800 = (controller_type == "Micro800")
                self.comm.SocketTimeout = 5.0
                test = self.comm.GetDeviceProperties()
                if test.Value is not None:
                    self.device_name = test.Value.ProductName or "Unknown Device"
                    self.connected = True
                    return True, self.device_name
                else:
                    self.connected = False
                    return False, f"Connection test failed: {test.Status}"
        except Exception as e:
            self.connected = False
            return False, str(e)

    def disconnect(self):
        with self._lock:
            if self.comm:
                try: self.comm.Close()
                except Exception: pass
            self.comm = None
            self.connected = False
            self.device_name = ""

    def get_tags(self):
        if not self.connected or not self.comm:
            return [], {}, "Not connected."
        try:
            with self._lock:
                result = self.comm.GetTagList()
            if result.Value is None:
                return [], {}, f"Failed: {result.Status}"
            controller_tags = []
            program_tags = {}
            for tag in result.Value:
                if any(x in tag.TagName for x in ["__", "Routine:", "Map:", "Task:"]):
                    continue
                tag_info = {
                    "name": tag.TagName,
                    "dataType": tag.DataType if tag.DataType else "UNKNOWN",
                    "trendable": tag.DataType in TRENDABLE_TYPES and tag.Struct == 0,
                }
                if tag.TagName.startswith("Program:"):
                    dot_idx = tag.TagName.find(".")
                    prog = tag.TagName[:dot_idx] if dot_idx > 0 else tag.TagName
                    program_tags.setdefault(prog, []).append(tag_info)
                else:
                    controller_tags.append(tag_info)
            controller_tags.sort(key=lambda t: t["name"].lower())
            for prog in program_tags:
                program_tags[prog].sort(key=lambda t: t["name"].lower())
            return controller_tags, program_tags, None
        except Exception as e:
            return [], {}, str(e)

    def read_tags(self, tag_names):
        if not self.connected or not self.comm:
            return {}
        try:
            with self._lock:
                if len(tag_names) == 1:
                    ret = self.comm.Read(tag_names[0])
                    val = ret.Value if ret.Status == "Success" else None
                    if isinstance(val, bool): val = int(val)
                    return {tag_names[0]: val}
                else:
                    ret = self.comm.Read(tag_names)
                    values = {}
                    for r in ret:
                        val = r.Value if r.Status == "Success" else None
                        if isinstance(val, bool): val = int(val)
                        values[r.TagName] = val
                    return values
        except Exception:
            return {}


# =========================================================================
# TREND DATA MANAGER
# =========================================================================
class TrendDataManager:
    def __init__(self, max_points=100000):
        self.data = []
        self.tags = []
        self.sample_rate = 1.0
        self.start_time = None
        self.trending = False
        self.max_points = max_points
        self._lock = threading.Lock()
        self.min_values = {}
        self.max_values = {}
        self.live_values = {}

    def start(self, tags, sample_rate):
        with self._lock:
            self.data = []
            self.tags = list(tags)
            self.sample_rate = sample_rate
            self.start_time = datetime.now().isoformat(timespec="milliseconds")
            self.trending = True
            self.min_values = {}
            self.max_values = {}
            self.live_values = {}

    def stop(self):
        self.trending = False

    def update_tags(self, new_tags):
        """Update the tag list mid-trend. New tags start collecting on next poll.
        Removed tags keep their historical data in existing points."""
        with self._lock:
            self.tags = list(new_tags)

    def add_point(self, values):
        ts = datetime.now()
        point = {"timestamp": ts.isoformat(timespec="milliseconds"), "dt": ts, "values": values}
        with self._lock:
            self.data.append(point)
            if len(self.data) > self.max_points:
                self.data = self.data[-self.max_points:]
            for tag, val in values.items():
                self.live_values[tag] = val
                if val is not None:
                    if tag not in self.min_values or val < self.min_values[tag]:
                        self.min_values[tag] = val
                    if tag not in self.max_values or val > self.max_values[tag]:
                        self.max_values[tag] = val

    def get_chart_data(self):
        with self._lock:
            result = {}
            for tag in self.tags:
                times = []
                vals = []
                for pt in self.data:
                    times.append(pt["dt"])
                    v = pt["values"].get(tag)
                    # Use NaN for missing values (tag added mid-trend) so
                    # matplotlib draws line gaps instead of choking on None
                    vals.append(v if v is not None else float('nan'))
                result[tag] = (times, vals)
            return result

    def clear(self):
        with self._lock:
            self.data = []
            self.min_values = {}
            self.max_values = {}
            self.live_values = {}

    def export_pytrend(self, filepath, plc_ip, controller_type, slot):
        with self._lock:
            export_data = [{"timestamp": pt["timestamp"], "values": pt["values"]} for pt in self.data]
        payload = {
            "version": "1.0",
            "appName": "PLC Trend Tool -- Southern Automation Solutions",
            "metadata": {
                "plcIP": plc_ip, "controllerType": controller_type, "slot": slot,
                "tags": self.tags, "sampleRate": self.sample_rate,
                "startTime": self.start_time,
                "endTime": datetime.now().isoformat(timespec="milliseconds"),
                "totalPoints": len(export_data),
                "exportedAt": datetime.now().isoformat(timespec="milliseconds"),
            },
            "data": export_data,
        }
        with open(filepath, "w") as f:
            json.dump(payload, f, indent=2)

    def export_csv(self, filepath):
        with self._lock:
            data_copy = list(self.data)
        if not data_copy:
            return
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp"] + self.tags)
            for pt in data_copy:
                row = [pt["timestamp"]] + [pt["values"].get(t, "") for t in self.tags]
                writer.writerow(row)

    def import_pytrend(self, filepath):
        with open(filepath, "r") as f:
            content = json.load(f)
        meta = content.get("metadata", {})
        raw_data = content.get("data", [])
        with self._lock:
            self.data = []
            self.tags = meta.get("tags", [])
            self.sample_rate = meta.get("sampleRate", 1.0)
            self.start_time = meta.get("startTime", "")
            self.trending = False
            self.min_values = {}
            self.max_values = {}
            self.live_values = {}
            for pt in raw_data:
                ts_str = pt.get("timestamp", "")
                try: dt = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError): dt = datetime.now()
                point = {"timestamp": ts_str, "dt": dt, "values": pt.get("values", {})}
                self.data.append(point)
                for tag, val in point["values"].items():
                    self.live_values[tag] = val
                    if val is not None:
                        if tag not in self.min_values or val < self.min_values[tag]:
                            self.min_values[tag] = val
                        if tag not in self.max_values or val > self.max_values[tag]:
                            self.max_values[tag] = val
        return meta

    @property
    def point_count(self):
        with self._lock:
            return len(self.data)

    def get_time_range(self):
        """Return (first_dt, last_dt) or (None, None) if no data."""
        with self._lock:
            if not self.data:
                return None, None
            return self.data[0]["dt"], self.data[-1]["dt"]


# =========================================================================
# MAIN APPLICATION
# =========================================================================
class PLCTrendTool(ctk.CTk):
    """Main application window -- layout matches SAS Network Diagnostic Tool."""

    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        theme = self.settings.get("theme", "Dark")
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")

        self.title(APP_FULL_NAME)
        w = self.settings.get("window_width", 1400)
        h = self.settings.get("window_height", 850)
        self.geometry(f"{w}x{h}")
        self.minsize(1100, 700)
        self.configure(fg_color=BG_DARK)

        # == Window Icon ==
        # CustomTkinter overrides iconbitmap during __init__, so we must
        # set ours AFTER CTk finishes setup.  We use both iconphoto (for
        # the taskbar) and iconbitmap (for the title bar / file explorer).
        self._setup_window_icon()

        self.plc = PLCManager()
        max_pts = self.settings.get("max_points", 100000)
        self.trend = TrendDataManager(max_points=max_pts)
        self.trend_thread = None
        self.chart_update_timer = None
        self.selected_tags = set()
        self.tag_data_types = {}
        self.view_mode = "live"
        self.all_ctrl_tags = []
        self.all_prog_tags = {}

        # Smart cursor state
        self._cursor_vline = None
        self._cursor_annotations = []
        self._cursor_dots = []
        self._cursor_enabled = self.settings.get("smart_cursor", True)

        # Chart state
        self._tag_scales = {}           # {tag: {"auto": True, "min": 0, "max": 100}}
        self._line_props = {}           # {tag: {"color": str, "width": float, "style": str}}
        self._tag_order = []            # display order of tags in isolated mode
        self.axes = []                  # list of axes (single subplot)
        self.lines = {}                 # {tag: Line2D}
        self._syncing_xlim = False      # guard for xlim sync callbacks
        self._drag_state = None         # drag-reorder state: {"src_idx": int, "highlight": artist}

        # Time window and display state
        self._time_span_seconds = self.settings.get("time_span", 30)
        self._follow_live = True        # auto-follow latest data during live trending
        self._paused = False            # display pause (data still collects)
        self._isolated_mode = self.settings.get("isolated_mode", False)
        self._scale_mode = self.settings.get("scale_mode", "independent")  # "same" or "independent"

        self._build_sidebar()
        self._build_main_area()
        self._show_trend_view()
        self._restore_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # == WINDOW ICON ==
    def _setup_window_icon(self):
        """Set window icon for title bar, taskbar, ALT-TAB, and file explorer.
        
        CustomTkinter overrides iconbitmap in __init__, so we must:
        1. Set AppUserModelID (Windows) so taskbar uses OUR icon not Python's
        2. Use iconphoto for taskbar/ALT-TAB (CTk does NOT override this)
        3. Use iconbitmap with retries for title bar (CTk overrides once)
        """
        ico_path = resource_path(os.path.join("assets", "icon.ico"))
        png_path = resource_path(os.path.join("assets", "icon.png"))
        logo_path = resource_path(os.path.join("assets", "logo.png"))

        for label, path in [("ICO", ico_path), ("PNG", png_path), ("Logo", logo_path)]:
            logging.info(f"Icon [{label}]: {path} -> {'FOUND' if os.path.exists(path) else 'MISSING'}")

        # Step 1: Windows AppUserModelID — makes taskbar show our icon
        # Without this, Windows groups the app under "python.exe" icon
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "SAS.PLCTrendTool.1.0"
                )
                logging.info("Set Windows AppUserModelID")
            except Exception as e:
                logging.warning(f"AppUserModelID failed: {e}")

        # Step 2: iconphoto — sets taskbar + ALT-TAB icon
        # CTk does NOT override this, so it sticks reliably
        icon_file = png_path if os.path.exists(png_path) else (
            logo_path if os.path.exists(logo_path) else None)
        if icon_file:
            try:
                icon_img = tk.PhotoImage(file=icon_file)
                self.iconphoto(True, icon_img)
                self._icon_photo_ref = icon_img  # prevent GC
                logging.info(f"iconphoto set from: {icon_file}")
            except Exception as e:
                logging.warning(f"iconphoto failed: {e}")

        # Step 3: iconbitmap — sets the small icon in the title bar (Windows)
        # CTk sets its own icon during __init__, so we override after.
        # Multiple attempts at different delays to ensure we win the race.
        if os.path.exists(ico_path):
            def _set_ico():
                try:
                    self.iconbitmap(ico_path)
                    logging.info(f"iconbitmap set: {ico_path}")
                except Exception as e:
                    logging.warning(f"iconbitmap failed: {e}")
            # Try immediately, then again after CTk finishes its deferred setup
            self.after(50, _set_ico)
            self.after(200, _set_ico)
            self.after(600, _set_ico)

    # == SIDEBAR ==
    def _build_sidebar(self):
        self._sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0,
                                      fg_color=BG_MEDIUM, border_width=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=120)
        logo_frame.pack(fill="x", padx=12, pady=(16, 4))
        logo_frame.pack_propagate(False)

        logo_loaded = False
        try:
            dark_logo_path = resource_path(os.path.join("assets", "logo.png"))
            light_logo_path = resource_path(os.path.join("assets", "logo_light.png"))
            logging.info(f"Sidebar logo paths: dark={dark_logo_path} (exists={os.path.exists(dark_logo_path)}), "
                         f"light={light_logo_path} (exists={os.path.exists(light_logo_path)})")
            if os.path.exists(dark_logo_path):
                dark_img = Image.open(dark_logo_path).convert("RGBA")
                light_img = Image.open(light_logo_path).convert("RGBA") if os.path.exists(light_logo_path) else dark_img
                # Scale to fit sidebar width with padding, constrain height
                max_w = SIDEBAR_WIDTH - 32
                max_h = 100
                aspect = dark_img.width / dark_img.height
                logo_w = max_w
                logo_h = int(logo_w / aspect)
                if logo_h > max_h:
                    logo_h = max_h
                    logo_w = int(logo_h * aspect)
                logging.info(f"Sidebar logo size: {logo_w}x{logo_h} (source: {dark_img.size})")
                ctk_logo = ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(logo_w, logo_h))
                ctk.CTkLabel(logo_frame, text="", image=ctk_logo, fg_color="transparent").pack(expand=True)
                self._logo_ref = ctk_logo
                logo_loaded = True
            else:
                logging.warning(f"Logo file not found at: {dark_logo_path}")
        except Exception as e:
            logging.warning(f"Logo loading failed: {e}")

        if not logo_loaded:
            ctk.CTkLabel(logo_frame, text="SAS", font=(FONT_FAMILY, 28, "bold"),
                         text_color=SAS_BLUE).pack(pady=(5, 0))

        ctk.CTkLabel(self._sidebar, text=APP_NAME, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=TEXT_PRIMARY).pack(padx=16, pady=(4, 4))
        ctk.CTkFrame(self._sidebar, fg_color=BORDER_COLOR, height=1).pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(self._sidebar, text="TOOLS", font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=20, pady=(0, 6))

        self._nav_buttons = {}
        self._add_nav_button("trend", "\U0001F4C8  Trend View", self._show_trend_view)
        self._add_nav_button("connect", "\U0001F50C  PLC Connection", self._show_connect_view)
        self._add_nav_button("tags", "\U0001F3F7  Tag Browser", self._show_tags_view)

        spacer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        bottom = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(0, 12))

        ctk.CTkButton(bottom, text="\u2699  Settings", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      fg_color="transparent", text_color=TEXT_SECONDARY,
                      hover_color=BG_CARD_HOVER, anchor="w", height=36, corner_radius=6,
                      command=self._show_settings_view).pack(fill="x", pady=(0, 2))

        ctk.CTkFrame(bottom, fg_color=BORDER_COLOR, height=1).pack(fill="x", padx=4, pady=8)

        self._sidebar_status = ctk.CTkLabel(bottom, text="\u25CF Disconnected",
                                            font=(FONT_FAMILY, FONT_SIZE_TINY),
                                            text_color=STATUS_OFFLINE, anchor="w")
        self._sidebar_status.pack(fill="x", padx=4, pady=(0, 4))

        ctk.CTkLabel(bottom, text=APP_COMPANY, font=(FONT_FAMILY, FONT_SIZE_TINY),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=4)
        ctk.CTkLabel(bottom, text=f"v{APP_VERSION}", font=(FONT_FAMILY, FONT_SIZE_TINY),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=4)

    def _add_nav_button(self, key, text, command):
        btn = ctk.CTkButton(self._sidebar, text=text, font=(FONT_FAMILY, FONT_SIZE_BODY),
                            fg_color="transparent", text_color=TEXT_SECONDARY,
                            hover_color=BG_CARD_HOVER, anchor="w", height=40, corner_radius=6,
                            command=command)
        btn.pack(fill="x", padx=12, pady=(0, 2))
        self._nav_buttons[key] = btn

    def _set_active_nav(self, key):
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(fg_color=BG_CARD, text_color=SAS_BLUE_LIGHT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SECONDARY)

    # == MAIN AREA ==
    def _build_main_area(self):
        self._main_area = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self._main_area.pack(side="right", fill="both", expand=True)
        self._trend_view = self._create_trend_view()
        self._connect_view = self._create_connect_view()
        self._settings_view = self._create_settings_view()

    def _hide_all_views(self):
        for v in [self._trend_view, self._connect_view, self._settings_view]:
            v.pack_forget()

    def _show_trend_view(self):
        self._hide_all_views()
        self._trend_view.pack(fill="both", expand=True)
        self._set_active_nav("trend")

    def _show_connect_view(self):
        self._hide_all_views()
        self._connect_view.pack(fill="both", expand=True)
        self._set_active_nav("connect")

    def _show_tags_view(self):
        """Show trend view with the tag panel visible."""
        self._show_trend_view()
        self._set_active_nav("tags")
        if not self._tag_panel_visible:
            self._toggle_tag_panel()

    def _show_settings_view(self):
        self._hide_all_views()
        self._settings_view.pack(fill="both", expand=True)
        self._set_active_nav("")

    def _build_section_header(self, parent, title):
        ctk.CTkLabel(parent, text=title.upper(), font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=24, pady=(8, 6))

    # == VIEW: PLC CONNECTION ==
    def _create_connect_view(self):
        view = ctk.CTkScrollableFrame(self._main_area, fg_color="transparent",
                                       scrollbar_button_color=BG_MEDIUM, scrollbar_button_hover_color=SAS_BLUE)
        hdr = ctk.CTkFrame(view, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 4))
        ctk.CTkLabel(hdr, text="\U0001F50C  PLC Connection", font=(FONT_FAMILY, FONT_SIZE_HEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(side="left")
        ctk.CTkLabel(view, text="Connect to an Allen-Bradley controller to browse tags and start trending.",
                     font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_SECONDARY, anchor="w").pack(fill="x", padx=24, pady=(0, 16))
        self._build_section_header(view, "CONNECTION SETTINGS")

        conn_card = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS, border_width=1, border_color=BORDER_COLOR)
        conn_card.pack(fill="x", padx=24, pady=(0, 16))
        inner = ctk.CTkFrame(conn_card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=CARD_PADDING)

        # Controller type
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(row1, text="Controller Type", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w", width=140).pack(side="left")
        self.controller_type_var = ctk.StringVar(value="ControlLogix")
        ctk.CTkOptionMenu(row1, variable=self.controller_type_var, values=["ControlLogix", "CompactLogix", "Micro800"],
                          font=(FONT_FAMILY, FONT_SIZE_BODY), fg_color=BG_MEDIUM, button_color=SAS_BLUE,
                          button_hover_color=SAS_BLUE_DARK, dropdown_fg_color=BG_MEDIUM, width=200, height=INPUT_HEIGHT).pack(side="left", padx=(12, 0))

        # IP Address
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(row2, text="IP Address", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w", width=140).pack(side="left")
        self.ip_entry = ctk.CTkEntry(row2, width=200, height=INPUT_HEIGHT, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                      fg_color=BG_INPUT, border_color=BORDER_COLOR, placeholder_text="192.168.1.10")
        self.ip_entry.pack(side="left", padx=(12, 0))
        self.ip_entry.bind("<Return>", lambda e: self._connect())

        # Slot
        row3 = ctk.CTkFrame(inner, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(row3, text="Processor Slot", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w", width=140).pack(side="left")
        self.slot_entry = ctk.CTkEntry(row3, width=80, height=INPUT_HEIGHT, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                        fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.slot_entry.insert(0, "0")
        self.slot_entry.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(row3, text="(Usually 0 for CompactLogix/Micro800)", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_MUTED).pack(side="left", padx=(12, 0))

        # Buttons
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")
        self.connect_btn = ctk.CTkButton(btn_row, text="Connect", width=140, height=BUTTON_HEIGHT,
                                          font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"), fg_color=SAS_BLUE,
                                          hover_color=SAS_BLUE_DARK, corner_radius=BUTTON_CORNER_RADIUS, command=self._connect)
        self.connect_btn.pack(side="left")
        self.conn_status_label = ctk.CTkLabel(btn_row, text="", font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_SECONDARY)
        self.conn_status_label.pack(side="left", padx=(16, 0))

        # Device info
        self._build_section_header(view, "DEVICE INFO")
        self.device_card = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS, border_width=1, border_color=BORDER_COLOR)
        self.device_card.pack(fill="x", padx=24, pady=(0, 16))
        self.device_info_label = ctk.CTkLabel(self.device_card, text="Not connected -- connect to a PLC to see device information.",
                                               font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_MUTED, anchor="w")
        self.device_info_label.pack(fill="x", padx=CARD_PADDING, pady=CARD_PADDING)
        return view

    # == VIEW: TREND ==
    def _create_trend_view(self):
        # Plain tk.Frame — CTkFrame adds ~20px internal canvas overhead
        view = tk.Frame(self._main_area, bg=resolve_color(BG_DARK))
        view.grid_rowconfigure(0, weight=0)
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)
        self._trend_view_frame = view

        # Toolbar — plain tk.Frame, fixed 28px
        toolbar = tk.Frame(view, bg=resolve_color(BG_MEDIUM), height=28)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(0, weight=1)
        self._toolbar_frame = toolbar

        inner = tk.Frame(toolbar, bg=resolve_color(BG_MEDIUM))
        inner.pack(fill="x", padx=6, pady=2)
        self._toolbar_inner = inner

        tb_font = (FONT_FAMILY, FONT_SIZE_SMALL)
        tb_fg = resolve_color(TEXT_SECONDARY)
        tb_bg = resolve_color(BG_MEDIUM)
        tb_btn_bg = resolve_color(BG_CARD)
        tb_border = resolve_color(BORDER_COLOR)
        tb_hover = resolve_color(BG_CARD_HOVER)

        # Tag panel toggle button
        self._tag_panel_visible = True
        self._tag_toggle_btn = tk.Button(inner, text="\U0001F3F7 Tags", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                                          bg=SAS_BLUE, fg="#FFFFFF", activebackground=SAS_BLUE_DARK,
                                          activeforeground="#FFFFFF", bd=0, relief="flat", padx=6, pady=1,
                                          command=self._toggle_tag_panel, cursor="hand2")
        self._tag_toggle_btn.pack(side="left", padx=(0, 4))

        # Separator
        tk.Frame(inner, bg=tb_border, width=1).pack(side="left", fill="y", padx=4, pady=2)

        # Start/Stop buttons
        self.start_btn = tk.Button(inner, text="\u25B6 Start Trend", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                                    bg=SAS_BLUE, fg="#FFFFFF", activebackground=SAS_BLUE_DARK,
                                    activeforeground="#FFFFFF", bd=0, relief="flat", padx=8, pady=1,
                                    command=self._start_trend, state="disabled", cursor="hand2")
        self.start_btn.pack(side="left", padx=(0, 6))

        self.stop_btn = tk.Button(inner, text="\u25A0 Stop", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                                   bg=STATUS_ERROR, fg="#FFFFFF", activebackground="#b91c1c",
                                   activeforeground="#FFFFFF", bd=0, relief="flat", padx=8, pady=1,
                                   command=self._stop_trend, cursor="hand2")
        # stop_btn packed only when trending

        self.pause_btn = tk.Button(inner, text="\u275A\u275A Pause", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                                    bg=SAS_ORANGE, fg="#FFFFFF", activebackground="#d97706",
                                    activeforeground="#FFFFFF", bd=0, relief="flat", padx=8, pady=1,
                                    command=self._pause_trend, cursor="hand2")

        self.resume_btn = tk.Button(inner, text="\u25B6 Resume", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                                     bg=STATUS_GOOD, fg="#FFFFFF", activebackground="#15803d",
                                     activeforeground="#FFFFFF", bd=0, relief="flat", padx=8, pady=1,
                                     command=self._resume_trend, cursor="hand2")

        tk.Label(inner, text="Rate:", font=tb_font, fg=tb_fg, bg=tb_bg).pack(side="left", padx=(4, 2))
        self.rate_var = ctk.StringVar(value="1 sec")
        ctk.CTkOptionMenu(inner, variable=self.rate_var,
                          values=["100 ms", "250 ms", "500 ms", "1 sec", "2 sec", "5 sec", "10 sec", "30 sec", "60 sec"],
                          font=tb_font, fg_color=BG_CARD, button_color=SAS_BLUE,
                          button_hover_color=SAS_BLUE_DARK, dropdown_fg_color=BG_MEDIUM, width=85, height=22).pack(side="left", padx=(0, 4))

        # Separator
        tk.Frame(inner, bg=tb_border, width=1).pack(side="left", fill="y", padx=4, pady=2)

        # Chart properties button
        scale_btn = tk.Button(inner, text="\u2699 Props", font=tb_font,
                               bg=tb_bg, fg=tb_fg, activebackground=tb_hover,
                               activeforeground=resolve_color(TEXT_PRIMARY),
                               bd=1, relief="solid", padx=6, pady=0,
                               command=self._show_chart_properties, cursor="hand2",
                               highlightthickness=0)
        scale_btn.pack(side="left", padx=(0, 4))

        # Separator
        tk.Frame(inner, bg=tb_border, width=1).pack(side="left", fill="y", padx=4, pady=2)

        self.point_label = tk.Label(inner, text="", font=tb_font, fg=resolve_color(TEXT_MUTED), bg=tb_bg)
        self.point_label.pack(side="left", padx=(0, 6))
        self.view_badge_label = tk.Label(inner, text="", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                                          fg=resolve_color(TEXT_MUTED), bg=tb_bg)
        self.view_badge_label.pack(side="left")

        # Right buttons — plain tk for tight sizing
        def _make_tb_btn(parent, text, cmd, state="normal"):
            b = tk.Button(parent, text=text, font=tb_font, bg=tb_bg, fg=tb_fg,
                          activebackground=tb_hover, activeforeground=resolve_color(TEXT_PRIMARY),
                          bd=1, relief="solid", padx=4, pady=0, command=cmd,
                          state=state, cursor="hand2", highlightthickness=0)
            b.pack(side="right", padx=1)
            return b

        self.clear_data_btn = _make_tb_btn(inner, "Clear", self._clear_data, "disabled")
        _make_tb_btn(inner, "Import", self._import_file)
        self.export_csv_btn = _make_tb_btn(inner, "CSV", self._export_csv, "disabled")
        self.export_json_btn = _make_tb_btn(inner, ".pytrend", self._export_pytrend, "disabled")
        tk.Label(inner, text="Export:", font=tb_font, fg=resolve_color(TEXT_MUTED), bg=tb_bg).pack(side="right", padx=(0, 2))

        # ── Horizontal PanedWindow: Tag Panel (left) | Chart+Table (right) ──
        self._h_paned = tk.PanedWindow(view, orient=tk.HORIZONTAL, sashwidth=5,
                                        bg=resolve_color(BORDER_COLOR), relief="flat",
                                        sashrelief="flat", opaqueresize=True)
        self._h_paned.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # ── Left: Tag Picker Panel ──
        self._tag_panel = tk.Frame(self._h_paned, bg=resolve_color(BG_CARD),
                                    highlightbackground=resolve_color(BORDER_COLOR),
                                    highlightthickness=1, bd=0)
        self._tag_panel.grid_rowconfigure(2, weight=1)
        self._tag_panel.grid_columnconfigure(0, weight=1)

        # Tag panel header
        tp_hdr = tk.Frame(self._tag_panel, bg=resolve_color(BG_MEDIUM))
        tp_hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(tp_hdr, text="\U0001F3F7 Tags", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                 fg=resolve_color(TEXT_PRIMARY), bg=resolve_color(BG_MEDIUM)).pack(side="left", padx=(8, 4), pady=4)
        self.tag_count_label = tk.Label(tp_hdr, text="", font=(FONT_FAMILY, FONT_SIZE_TINY),
                                         fg=resolve_color(TEXT_MUTED), bg=resolve_color(BG_MEDIUM))
        self.tag_count_label.pack(side="left", padx=(0, 4))
        refresh_btn = tk.Button(tp_hdr, text="\u21BB", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                 bg=resolve_color(BG_MEDIUM), fg=resolve_color(TEXT_SECONDARY),
                                 activebackground=resolve_color(BG_CARD_HOVER), bd=0, relief="flat",
                                 padx=4, command=self._fetch_tags, cursor="hand2")
        refresh_btn.pack(side="right", padx=(0, 4))
        self._add_tooltip(refresh_btn, "Refresh tag list from PLC")

        # Search + controls row
        tp_search = tk.Frame(self._tag_panel, bg=resolve_color(BG_CARD))
        tp_search.grid(row=1, column=0, sticky="ew", padx=4, pady=(4, 2))
        self.tag_search_var = ctk.StringVar()
        self.tag_search_var.trace_add("write", lambda *_: self._filter_tags())
        self.tag_search = ctk.CTkEntry(tp_search, placeholder_text="Search...", textvariable=self.tag_search_var,
                                        font=(FONT_FAMILY, FONT_SIZE_SMALL), fg_color=BG_INPUT,
                                        border_color=BORDER_COLOR, height=26)
        self.tag_search.pack(side="left", fill="x", expand=True, padx=(0, 4))

        sel_btn_style = dict(font=(FONT_FAMILY, FONT_SIZE_TINY), bd=0, relief="flat",
                             bg=resolve_color(BG_MEDIUM), fg=resolve_color(TEXT_SECONDARY),
                             activebackground=resolve_color(BG_CARD_HOVER), padx=4, cursor="hand2")
        tk.Button(tp_search, text="All", command=self._select_all_visible, **sel_btn_style).pack(side="left", padx=1)
        tk.Button(tp_search, text="Clear", command=self._clear_selection, **sel_btn_style).pack(side="left", padx=1)
        self.selected_label = tk.Label(tp_search, text="0 sel", font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                                        fg=SAS_BLUE, bg=resolve_color(BG_CARD))
        self.selected_label.pack(side="right", padx=(4, 0))

        # Tag tree
        tp_tree_frame = tk.Frame(self._tag_panel, bg=resolve_color(BG_CARD))
        tp_tree_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 4))
        tp_tree_frame.grid_rowconfigure(0, weight=1)
        tp_tree_frame.grid_columnconfigure(0, weight=1)

        self.tree_style = ttk.Style()
        self._apply_treeview_style()
        self.tag_tree = ttk.Treeview(tp_tree_frame, columns=("type",), show="tree headings", selectmode="none")
        self.tag_tree.heading("#0", text="Tag Name", anchor="w")
        self.tag_tree.heading("type", text="Type", anchor="w")
        self.tag_tree.column("#0", width=220, minwidth=120)
        self.tag_tree.column("type", width=60, minwidth=40)
        self.tag_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(tp_tree_frame, orient="vertical", command=self.tag_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tag_tree.configure(yscrollcommand=tree_scroll.set)
        self.tag_tree.bind("<ButtonRelease-1>", self._on_tag_click)
        self._set_tag_placeholder("Connect to a PLC to browse tags")

        self._h_paned.add(self._tag_panel, width=300, minsize=200, stretch="never")

        # ── Right: Chart + Table (vertical PanedWindow) ──
        right_frame = tk.Frame(self._h_paned, bg=resolve_color(BG_DARK))
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self._paned = tk.PanedWindow(right_frame, orient=tk.VERTICAL, sashwidth=6,
                                      bg=resolve_color(BORDER_COLOR), relief="flat",
                                      sashrelief="flat", opaqueresize=True)
        self._paned.grid(row=0, column=0, sticky="nsew", padx=4, pady=(0, 4))

        # Chart area
        chart_wrapper = tk.Frame(self._paned, bg=resolve_color(BG_CARD),
                                 highlightbackground=resolve_color(BORDER_COLOR),
                                 highlightthickness=1, bd=0)
        self._chart_wrapper = chart_wrapper
        chart_wrapper.grid_rowconfigure(0, weight=1)
        chart_wrapper.grid_columnconfigure(0, weight=1)

        self.fig = Figure(figsize=(10, 5), dpi=100)
        self._style_chart()
        self.ax = self.fig.add_subplot(111)
        self.axes = [self.ax]
        self._style_chart_axes(self.ax)

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_wrapper)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Hidden NavigationToolbar (we call its methods via custom buttons)
        _hidden_tb_frame = tk.Frame(chart_wrapper, width=0, height=0)
        self.chart_toolbar = NavigationToolbar2Tk(self.canvas, _hidden_tb_frame)
        self.chart_toolbar.update()

        # Vertical toolbar strip on right side of chart
        nav_strip = tk.Frame(chart_wrapper, bg=resolve_color(BG_CARD), width=28)
        nav_strip.grid(row=0, column=1, sticky="ns", padx=0, pady=0)
        nav_strip.grid_propagate(False)
        self._nav_strip = nav_strip

        nav_btn_style = dict(
            font=(FONT_FAMILY, 12), width=2, bd=0, relief="flat",
            bg=resolve_color(BG_CARD), fg=resolve_color(TEXT_SECONDARY),
            activebackground=resolve_color(BG_CARD_HOVER),
            activeforeground=resolve_color(TEXT_PRIMARY),
        )
        for symbol, tip, cmd in [
            ("\u2302", "Home (reset view)", self.chart_toolbar.home),
            ("\u2190", "Back", self.chart_toolbar.back),
            ("\u2192", "Forward", self.chart_toolbar.forward),
            ("\u2725", "Pan", lambda: self.chart_toolbar.pan()),
            ("\u2922", "Zoom", lambda: self.chart_toolbar.zoom()),
            ("\u2386", "Save image", self.chart_toolbar.save_figure),
        ]:
            btn = tk.Button(nav_strip, text=symbol, command=cmd, **nav_btn_style)
            btn.pack(fill="x", pady=1)
            self._add_tooltip(btn, tip)

        # Right-click context menu on chart (built dynamically per-click)
        self.canvas.get_tk_widget().bind("<Button-3>", self._show_chart_context_menu)

        # Smart cursor events
        self.canvas.mpl_connect("motion_notify_event", self._on_chart_mouse_move)
        self.canvas.mpl_connect("axes_leave_event", self._on_chart_mouse_leave)

        # Drag-reorder events for isolated subplots (Ctrl+left-click)
        self.canvas.mpl_connect("button_press_event", self._on_chart_press)
        self.canvas.mpl_connect("button_release_event", self._on_chart_release)

        # Auto-fit axes to fill chart area on resize
        self.canvas.get_tk_widget().bind("<Configure>", self._on_chart_resize)

        # Time scrollbar below chart
        chart_wrapper.grid_rowconfigure(1, weight=0)
        scroll_frame = tk.Frame(chart_wrapper, bg=resolve_color(BG_CARD), height=18)
        scroll_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        scroll_frame.grid_propagate(False)
        scroll_frame.grid_columnconfigure(0, weight=1)
        self._scroll_frame = scroll_frame

        self._chart_scrollbar = tk.Scrollbar(scroll_frame, orient=tk.HORIZONTAL,
                                               command=self._on_chart_xscroll)
        self._chart_scrollbar.pack(side="left", fill="x", expand=True)
        self._chart_scrollbar.set(0.0, 1.0)

        follow_btn = tk.Button(scroll_frame, text="\u25B6\u25B6", font=(FONT_FAMILY, 7),
                                bg=resolve_color(BG_CARD), fg=SAS_BLUE,
                                activebackground=SAS_BLUE, activeforeground="#FFFFFF",
                                bd=0, padx=4, pady=0, command=self._snap_to_live,
                                cursor="hand2")
        follow_btn.pack(side="right")
        self._add_tooltip(follow_btn, "Follow live data")
        self._follow_btn = follow_btn

        self._paned.add(chart_wrapper, stretch="always", minsize=200)

        # Table area
        table_wrapper = tk.Frame(self._paned, bg=resolve_color(BG_CARD),
                                 highlightbackground=resolve_color(BORDER_COLOR),
                                 highlightthickness=1, bd=0)
        self._table_wrapper = table_wrapper

        columns = ("tag", "type", "current", "min", "max", "status")
        self.live_tree = ttk.Treeview(table_wrapper, columns=columns, show="headings", height=6)
        for col, txt, w, anc in [("tag","Tag Name",200,"w"),("type","Type",80,"w"),("current","Current",130,"e"),
                                  ("min","Min",130,"e"),("max","Max",130,"e"),("status","Status",70,"center")]:
            self.live_tree.heading(col, text=txt, anchor="w" if anc == "w" else anc)
            self.live_tree.column(col, width=w, minwidth=50, anchor=anc)
        self.live_tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        live_scroll = ttk.Scrollbar(table_wrapper, orient="vertical", command=self.live_tree.yview)
        live_scroll.pack(side="right", fill="y", pady=4)
        self.live_tree.configure(yscrollcommand=live_scroll.set)

        self._paned.add(table_wrapper, stretch="never", minsize=80)

        self._h_paned.add(right_frame, minsize=400, stretch="always")

        return view

    def _toggle_tag_panel(self):
        """Toggle the tag picker panel visibility."""
        if self._tag_panel_visible:
            # Hide: remove from paned window
            self._h_paned.forget(self._tag_panel)
            self._tag_panel_visible = False
            self._tag_toggle_btn.configure(bg=resolve_color(BG_CARD), fg=resolve_color(TEXT_SECONDARY))
        else:
            # Show: re-add at left position
            self._h_paned.add(self._tag_panel, before=self._h_paned.panes()[0],
                              width=300, minsize=200, stretch="never")
            self._tag_panel_visible = True
            self._tag_toggle_btn.configure(bg=SAS_BLUE, fg="#FFFFFF")

    # == VIEW: SETTINGS ==
    def _create_settings_view(self):
        view = ctk.CTkScrollableFrame(self._main_area, fg_color="transparent",
                                       scrollbar_button_color=BG_MEDIUM, scrollbar_button_hover_color=SAS_BLUE)
        hdr = ctk.CTkFrame(view, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 4))
        ctk.CTkLabel(hdr, text="\u2699  Settings", font=(FONT_FAMILY, FONT_SIZE_HEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(side="left")
        ctk.CTkLabel(view, text="Customize application behavior. Changes are saved automatically.",
                     font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_SECONDARY, anchor="w").pack(fill="x", padx=24, pady=(0, 16))

        self._build_section_header(view, "APPEARANCE")
        theme_card = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        theme_card.pack(fill="x", padx=24, pady=(0, 16))
        theme_row = ctk.CTkFrame(theme_card, fg_color="transparent")
        theme_row.pack(fill="x", padx=16, pady=12)
        left = ctk.CTkFrame(theme_row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text="Theme", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"), text_color=TEXT_PRIMARY, anchor="w").pack(fill="x")
        ctk.CTkLabel(left, text="Switch between dark and light mode", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED, anchor="w").pack(fill="x")
        self._theme_var = ctk.StringVar(value=self.settings.get("theme", "Dark"))
        ctk.CTkOptionMenu(theme_row, variable=self._theme_var, values=["Dark", "Light"], font=(FONT_FAMILY, FONT_SIZE_BODY),
                          fg_color=BG_MEDIUM, button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
                          dropdown_fg_color=BG_MEDIUM, width=120, height=32, command=self._on_theme_selected).pack(side="right", padx=(12, 0))

        # -- DATA STORAGE --
        self._build_section_header(view, "DATA STORAGE")
        storage_card = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        storage_card.pack(fill="x", padx=24, pady=(0, 16))

        storage_row = ctk.CTkFrame(storage_card, fg_color="transparent")
        storage_row.pack(fill="x", padx=16, pady=12)
        st_left = ctk.CTkFrame(storage_row, fg_color="transparent")
        st_left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(st_left, text="Maximum Data Points", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x")
        ctk.CTkLabel(st_left, text="Limits memory usage if the app is left running unattended",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED, anchor="w").pack(fill="x")

        points_options = {
            "10,000  (~5 MB)": 10000, "50,000  (~25 MB)": 50000,
            "100,000  (~50 MB)": 100000, "250,000  (~125 MB)": 250000,
            "500,000  (~250 MB)": 500000, "1,000,000  (~500 MB)": 1000000,
        }
        current_max = self.settings.get("max_points", 100000)
        current_label = "100,000  (~50 MB)"
        for label, val in points_options.items():
            if val == current_max:
                current_label = label
                break
        self._max_points_var = ctk.StringVar(value=current_label)
        self._max_points_map = points_options

        def on_max_points_changed(value):
            pts = self._max_points_map.get(value, 100000)
            self.settings["max_points"] = pts
            self.trend.max_points = pts
            save_settings(self.settings)
            self._update_storage_info()

        ctk.CTkOptionMenu(storage_row, variable=self._max_points_var,
                          values=list(points_options.keys()),
                          font=(FONT_FAMILY, FONT_SIZE_SMALL),
                          fg_color=BG_MEDIUM, button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
                          dropdown_fg_color=BG_MEDIUM, width=185, height=32,
                          command=on_max_points_changed).pack(side="right", padx=(12, 0))

        # Storage info row
        info_row = ctk.CTkFrame(storage_card, fg_color="transparent")
        info_row.pack(fill="x", padx=16, pady=(0, 12))
        self._storage_info_label = ctk.CTkLabel(info_row, text="", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                                  text_color=TEXT_MUTED, anchor="w")
        self._storage_info_label.pack(fill="x")
        self._update_storage_info()

        # -- TRENDING --
        self._build_section_header(view, "TRENDING")
        trend_card = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        trend_card.pack(fill="x", padx=24, pady=(0, 16))

        cursor_row = ctk.CTkFrame(trend_card, fg_color="transparent")
        cursor_row.pack(fill="x", padx=16, pady=12)
        cr_left = ctk.CTkFrame(cursor_row, fg_color="transparent")
        cr_left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(cr_left, text="Smart Cursor", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x")
        ctk.CTkLabel(cr_left, text="Show crosshair with tag values when hovering over the trend chart",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED, anchor="w").pack(fill="x")

        self._cursor_switch_var = ctk.BooleanVar(value=self._cursor_enabled)

        def on_cursor_toggled():
            self._cursor_enabled = self._cursor_switch_var.get()
            self.settings["smart_cursor"] = self._cursor_enabled
            save_settings(self.settings)
            if not self._cursor_enabled:
                self._clear_cursor_elements()
                try: self.canvas.draw_idle()
                except Exception: pass

        ctk.CTkSwitch(cursor_row, text="", variable=self._cursor_switch_var,
                      onvalue=True, offvalue=False, command=on_cursor_toggled,
                      fg_color=BORDER_COLOR, progress_color=SAS_BLUE,
                      button_color=("#FFFFFF", "#CCCCCC"), button_hover_color=SAS_BLUE_LIGHT,
                      width=46, height=24).pack(side="right", padx=(12, 0))

        self._build_section_header(view, "ABOUT")
        about_card = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        about_card.pack(fill="x", padx=24, pady=(0, 16))
        about_inner = ctk.CTkFrame(about_card, fg_color="transparent")
        about_inner.pack(fill="x", padx=16, pady=12)
        for text, color, style in [(APP_FULL_NAME, TEXT_PRIMARY, ("bold",)), (f"Version {APP_VERSION}", TEXT_SECONDARY, ()),
                                    (APP_COMPANY, TEXT_SECONDARY, ()), ("", TEXT_MUTED, ()),
                                    ("Allen-Bradley PLC Trending", TEXT_MUTED, ())]:
            if not text:
                ctk.CTkFrame(about_inner, fg_color=BORDER_COLOR, height=1).pack(fill="x", pady=6)
                continue
            ctk.CTkLabel(about_inner, text=text, font=(FONT_FAMILY, FONT_SIZE_BODY) + style,
                         text_color=color, anchor="w").pack(fill="x", pady=1)
        return view

    # == STYLE HELPERS ==
    def _apply_treeview_style(self):
        style = self.tree_style
        style.theme_use("default")
        bg = resolve_color(BG_INPUT)
        fg = resolve_color(TEXT_PRIMARY)
        hdr_bg = resolve_color(BG_MEDIUM)
        border = resolve_color(BORDER_COLOR)
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, borderwidth=0,
                         font=(FONT_FAMILY, FONT_SIZE_BODY), rowheight=24)
        style.configure("Treeview.Heading", background=hdr_bg, foreground=fg, borderwidth=0,
                         font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", SAS_BLUE)], foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", border)])

    # == TOOLTIP + CONTEXT MENU ==
    def _add_tooltip(self, widget, text):
        """Add a hover tooltip to a tk widget."""
        tip = None
        def show(event):
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_attributes("-topmost", True)
            lbl = tk.Label(tip, text=text, justify="left",
                           font=(FONT_FAMILY, FONT_SIZE_SMALL),
                           bg=resolve_color(BG_MEDIUM), fg=resolve_color(TEXT_PRIMARY),
                           padx=6, pady=3, relief="solid", borderwidth=1)
            lbl.pack()
            tip.update_idletasks()
            tw = tip.winfo_reqwidth()
            screen_w = widget.winfo_screenwidth()
            x = event.x_root + 12
            if x + tw > screen_w - 4:
                x = event.x_root - tw - 8
            y = event.y_root + 8
            tip.wm_geometry(f"+{x}+{y}")
        def hide(event):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None
        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _get_axis_at_event(self, event):
        """Determine which axis index the mouse event is over."""
        if not self._isolated_mode or len(self.axes) <= 1:
            return None  # overlay mode — no specific axis
        # Convert tk event coords to figure coords
        w = self.canvas.get_tk_widget()
        dpi = self.fig.dpi
        fig_w, fig_h = self.fig.get_size_inches()
        px_w = fig_w * dpi
        px_h = fig_h * dpi
        fx = event.x / px_w if px_w else 0
        fy = 1.0 - (event.y / px_h) if px_h else 0
        tags = self._get_ordered_tags()
        for i, ax in enumerate(self.axes):
            bbox = ax.get_position()
            if bbox.x0 <= fx <= bbox.x1 and bbox.y0 <= fy <= bbox.y1:
                return i
        return None

    def _show_chart_context_menu(self, event):
        """Build and show dynamic right-click context menu on the chart."""
        menu = tk.Menu(self.canvas.get_tk_widget(), tearoff=0,
                       bg=resolve_color(BG_CARD), fg=resolve_color(TEXT_PRIMARY),
                       activebackground=SAS_BLUE, activeforeground="#FFFFFF",
                       font=(FONT_FAMILY, FONT_SIZE_SMALL))

        # Determine which axis was right-clicked (for isolated mode)
        tags = self._get_ordered_tags()
        clicked_ax_idx = None
        if self._isolated_mode and len(self.axes) > 1 and tags:
            # Convert tk event coords to matplotlib figure coords
            w = self.canvas.get_tk_widget()
            dpi = self.fig.dpi
            fig_w, fig_h = self.fig.get_size_inches()
            px_w = fig_w * dpi
            px_h = fig_h * dpi
            fx = event.x / px_w if px_w else 0
            fy = 1.0 - (event.y / px_h) if px_h else 0
            for i, ax in enumerate(self.axes):
                bbox = ax.get_position()
                if bbox.x0 <= fx <= bbox.x1 and bbox.y0 <= fy <= bbox.y1:
                    clicked_ax_idx = i
                    break

        # "Line Properties..." — context-aware
        if self._isolated_mode and clicked_ax_idx is not None and clicked_ax_idx < len(tags):
            clicked_tag = tags[clicked_ax_idx]
            short = clicked_tag.split(".")[-1] if "." in clicked_tag else clicked_tag
            menu.add_command(label=f"\u270E  Line Properties ({short})...",
                             command=lambda t=clicked_tag: self._show_line_properties([t]))
        elif tags:
            menu.add_command(label="\u270E  Line Properties...",
                             command=lambda: self._show_line_properties(list(tags)))

        menu.add_command(label="\u2699  Trend Properties...",
                         command=self._show_chart_properties)
        menu.add_separator()

        # Drag-reorder hint (isolated mode only)
        if self._isolated_mode and len(self.axes) > 1:
            menu.add_command(label="\u2195  Reorder Charts (Ctrl + Drag)",
                             state="disabled")
            menu.add_separator()

        menu.add_command(label="\u25B6  Follow Live", command=self._snap_to_live)
        menu.add_command(label="\u2302  Reset View", command=self.chart_toolbar.home)
        menu.add_separator()
        menu.add_command(label="\u2386  Save Image...", command=self.chart_toolbar.save_figure)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _style_chart(self):
        self.fig.patch.set_facecolor(resolve_color(BG_CARD))
        self._apply_tight_layout()

    def _apply_tight_layout(self):
        """Apply tight_layout with proper padding for current subplot configuration."""
        try:
            hpad = 0 if (self._isolated_mode and len(self.axes) > 1) else 0.8
            self.fig.tight_layout(pad=0.4, h_pad=hpad, w_pad=0.3)
        except Exception:
            # Fallback if tight_layout fails (e.g. no axes yet)
            self.fig.subplots_adjust(left=0.06, right=0.98, top=0.97, bottom=0.08)

    def _on_chart_resize(self, event=None):
        """Re-apply tight layout when the chart canvas is resized."""
        if hasattr(self, 'axes') and self.axes:
            self._apply_tight_layout()
            try:
                self.canvas.draw_idle()
            except Exception:
                pass

    def _style_chart_axes(self, ax=None):
        """Style a single axes object. If ax is None, styles all axes."""
        targets = [ax] if ax else self.axes
        face = resolve_color(BG_INPUT)
        text = resolve_color(TEXT_SECONDARY)
        grid = resolve_color(BORDER_COLOR)
        for a in targets:
            a.set_facecolor(face)
            a.tick_params(colors=text, labelsize=9)
            a.xaxis.label.set_color(text)
            a.yaxis.label.set_color(text)
            a.title.set_color(text)
            for spine in a.spines.values():
                spine.set_color(grid)
            a.grid(True, color=grid, alpha=0.4, linestyle="-", linewidth=0.5)
        # Only label bottom axis X and any axis Y
        if targets:
            targets[-1].set_xlabel("Time", fontsize=10, color=text)
            for a in targets:
                a.set_ylabel("Value", fontsize=10, color=text)

    # == TAG ORDER & LINE PROPERTIES ==
    def _get_ordered_tags(self):
        """Return tags in current display order.
        Uses selected_tags as primary source (live/configuring),
        falls back to trend.tags (imported historical data)."""
        if self.selected_tags:
            tags = set(self.selected_tags)
        elif self.trend.tags:
            tags = set(self.trend.tags)
        else:
            return []
        # Maintain order: keep existing ordered tags still present, append new ones
        ordered = [t for t in self._tag_order if t in tags]
        new_tags = sorted(t for t in tags if t not in set(self._tag_order))
        ordered.extend(new_tags)
        self._tag_order = ordered
        return list(self._tag_order)

    def _get_line_props(self, tag, idx):
        """Get line properties for a tag, with defaults based on index."""
        defaults = {
            "color": TRACE_COLORS[idx % len(TRACE_COLORS)],
            "width": 1.5,
            "style": "-",
        }
        props = self._line_props.get(tag, {})
        return {k: props.get(k, v) for k, v in defaults.items()}

    # == XLIM SYNC FOR ISOLATED SUBPLOTS ==
    def _connect_xlim_sync(self):
        """Connect xlim_changed callbacks so all isolated subplots stay synced."""
        self._xlim_cids = []
        if not self._isolated_mode or len(self.axes) <= 1:
            return
        for ax in self.axes:
            cid = ax.callbacks.connect("xlim_changed", self._on_xlim_changed)
            self._xlim_cids.append((ax, cid))

    def _disconnect_xlim_sync(self):
        """Remove xlim sync callbacks."""
        for ax, cid in getattr(self, "_xlim_cids", []):
            try:
                ax.callbacks.disconnect(cid)
            except Exception:
                pass
        self._xlim_cids = []

    def _on_xlim_changed(self, changed_ax):
        """Sync xlim from changed_ax to all other axes."""
        if self._syncing_xlim:
            return
        self._syncing_xlim = True
        try:
            new_xlim = changed_ax.get_xlim()
            for ax in self.axes:
                if ax is not changed_ax:
                    ax.set_xlim(new_xlim)
        finally:
            self._syncing_xlim = False

    # == DRAG/DROP REORDER FOR ISOLATED SUBPLOTS ==
    def _on_chart_press(self, event):
        """Handle mouse press for Ctrl+drag reorder of isolated subplots."""
        if not self._isolated_mode or len(self.axes) <= 1:
            return
        # Only Ctrl+left-click starts a drag
        if event.button != 1 or not hasattr(event, "guiEvent"):
            return
        gui = event.guiEvent
        if gui is None:
            return
        ctrl = bool(gui.state & 0x4)  # Ctrl modifier
        if not ctrl:
            return
        # Find which subplot was clicked
        for i, ax in enumerate(self.axes):
            if event.inaxes == ax:
                self._drag_state = {"src_idx": i, "highlight": None}
                self.canvas.get_tk_widget().config(cursor="fleur")
                # Connect motion for drag visual
                self._drag_motion_cid = self.canvas.mpl_connect(
                    "motion_notify_event", self._on_drag_motion)
                return

    def _on_drag_motion(self, event):
        """Show highlight on target subplot during drag."""
        if self._drag_state is None:
            return
        # Remove old highlight
        if self._drag_state.get("highlight"):
            try:
                self._drag_state["highlight"].remove()
            except Exception:
                pass
            self._drag_state["highlight"] = None
        # Find target axis
        for i, ax in enumerate(self.axes):
            if event.inaxes == ax and i != self._drag_state["src_idx"]:
                # Draw highlight rectangle
                highlight = ax.axhspan(
                    ax.get_ylim()[0], ax.get_ylim()[1],
                    facecolor=SAS_BLUE, alpha=0.15, zorder=0)
                self._drag_state["highlight"] = highlight
                self._drag_state["tgt_idx"] = i
                break
        else:
            self._drag_state.pop("tgt_idx", None)
        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def _on_chart_release(self, event):
        """Handle mouse release for drag-reorder completion."""
        if self._drag_state is None:
            return
        # Disconnect drag motion
        if hasattr(self, "_drag_motion_cid"):
            self.canvas.mpl_disconnect(self._drag_motion_cid)
            del self._drag_motion_cid
        # Remove highlight
        if self._drag_state.get("highlight"):
            try:
                self._drag_state["highlight"].remove()
            except Exception:
                pass
        self.canvas.get_tk_widget().config(cursor="")
        src = self._drag_state.get("src_idx")
        tgt = self._drag_state.get("tgt_idx")
        self._drag_state = None
        if src is not None and tgt is not None and src != tgt:
            tags = self._get_ordered_tags()
            if src < len(tags) and tgt < len(tags):
                # Move tag from src to tgt position
                tag = tags.pop(src)
                tags.insert(tgt, tag)
                self._tag_order = tags
                self._rebuild_chart()

    # == LINE PROPERTIES DIALOG ==
    LINE_STYLES = [
        ("-", "Solid ─────"),
        ("--", "Dashed ─ ─ ─"),
        (":", "Dotted ·······"),
        ("-.", "Dash-Dot ─·─·"),
    ]
    LINE_WIDTHS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]

    def _show_line_properties(self, tags_to_edit):
        """Open a dialog to edit line color, width, and style for the given tags."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Line Properties")
        width = 400 if len(tags_to_edit) <= 1 else 440
        height = min(140 + len(tags_to_edit) * 90, 600)
        dlg.geometry(f"{width}x{height}")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=BG_DARK)

        ctk.CTkLabel(dlg, text="Line Properties",
                     font=(FONT_FAMILY, 14, "bold"),
                     text_color=TEXT_PRIMARY).pack(padx=12, pady=(12, 6), anchor="w")

        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent",
                                          scrollbar_button_color=BG_MEDIUM,
                                          height=height - 110)
        scroll.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        all_tags = self._get_ordered_tags()
        tag_edits = {}  # {tag: {"color_var": StringVar, "width_var": StringVar, "style_var": StringVar}}

        for tag in tags_to_edit:
            idx = all_tags.index(tag) if tag in all_tags else 0
            props = self._get_line_props(tag, idx)

            card = ctk.CTkFrame(scroll, fg_color=BG_MEDIUM, corner_radius=6)
            card.pack(fill="x", pady=3)

            # Tag name header
            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=10, pady=(8, 4))

            short_name = tag.split(".")[-1] if "." in tag else tag
            ctk.CTkLabel(hdr, text=short_name,
                         font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                         text_color=TEXT_PRIMARY).pack(side="left")

            # Controls row
            ctrl = ctk.CTkFrame(card, fg_color="transparent")
            ctrl.pack(fill="x", padx=10, pady=(0, 8))

            # Color picker
            ctk.CTkLabel(ctrl, text="Color:", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY).pack(side="left")
            color_var = ctk.StringVar(value=props["color"])
            color_btn = tk.Button(ctrl, width=3, height=1,
                                   bg=props["color"], relief="solid", bd=1,
                                   activebackground=props["color"], cursor="hand2")
            color_btn.pack(side="left", padx=(4, 12))

            def make_color_picker(btn, var, t=tag):
                def pick():
                    from tkinter import colorchooser
                    result = colorchooser.askcolor(
                        color=var.get(), title=f"Line Color — {t}",
                        parent=dlg)
                    if result and result[1]:
                        var.set(result[1])
                        btn.configure(bg=result[1], activebackground=result[1])
                return pick
            color_btn.configure(command=make_color_picker(color_btn, color_var, tag))

            # Width dropdown
            ctk.CTkLabel(ctrl, text="Width:", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY).pack(side="left")
            width_var = ctk.StringVar(value=str(props["width"]))
            ctk.CTkOptionMenu(ctrl, variable=width_var,
                              values=[str(w) for w in self.LINE_WIDTHS],
                              font=(FONT_FAMILY, FONT_SIZE_SMALL),
                              fg_color=BG_INPUT, button_color=SAS_BLUE,
                              button_hover_color=SAS_BLUE_DARK,
                              dropdown_fg_color=BG_INPUT,
                              width=70, height=26).pack(side="left", padx=(4, 12))

            # Style dropdown
            ctk.CTkLabel(ctrl, text="Style:", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY).pack(side="left")
            style_labels = {s[0]: s[1] for s in self.LINE_STYLES}
            current_label = style_labels.get(props["style"], "Solid ─────")
            style_var = ctk.StringVar(value=current_label)
            ctk.CTkOptionMenu(ctrl, variable=style_var,
                              values=[s[1] for s in self.LINE_STYLES],
                              font=(FONT_FAMILY, FONT_SIZE_SMALL),
                              fg_color=BG_INPUT, button_color=SAS_BLUE,
                              button_hover_color=SAS_BLUE_DARK,
                              dropdown_fg_color=BG_INPUT,
                              width=130, height=26).pack(side="left", padx=(4, 0))

            tag_edits[tag] = {
                "color_var": color_var,
                "width_var": width_var,
                "style_var": style_var,
            }

        # Buttons
        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 12))

        def apply_and_close():
            label_to_style = {s[1]: s[0] for s in self.LINE_STYLES}
            for tag, edits in tag_edits.items():
                color = edits["color_var"].get()
                try:
                    w = float(edits["width_var"].get())
                except (ValueError, TypeError):
                    w = 1.5
                style = label_to_style.get(edits["style_var"].get(), "-")
                self._line_props[tag] = {"color": color, "width": w, "style": style}
                # Apply to live line
                if tag in self.lines:
                    self.lines[tag].set_color(color)
                    self.lines[tag].set_linewidth(w)
                    self.lines[tag].set_linestyle(style)
                    # Update legend color
                    self.lines[tag].set_label(tag)
            # Refresh legends
            for ax in self.axes:
                leg = ax.get_legend()
                if leg:
                    ax.legend(loc="upper left", fontsize=7 if self._isolated_mode else 8,
                              facecolor=resolve_color(BG_INPUT),
                              edgecolor=resolve_color(BORDER_COLOR),
                              labelcolor=resolve_color(TEXT_SECONDARY))
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
            dlg.destroy()

        ctk.CTkButton(btn_row, text="Apply & Close", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                       fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK, height=32,
                       command=apply_and_close).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Cancel", font=(FONT_FAMILY, FONT_SIZE_BODY),
                       fg_color=BG_MEDIUM, hover_color=BG_CARD_HOVER, height=32,
                       text_color=TEXT_SECONDARY,
                       command=dlg.destroy).pack(side="right")

    # == CHART LAYOUT MANAGEMENT ==
    def _rebuild_chart(self):
        """Rebuild the chart with current tags and per-tag scales."""
        self._clear_cursor_elements()
        self._disconnect_xlim_sync()
        self.fig.clear()
        tags = self._get_ordered_tags()
        text_color = resolve_color(TEXT_SECONDARY)
        face_color = resolve_color(BG_INPUT)
        grid_color = resolve_color(BORDER_COLOR)

        if not tags:
            self.ax = self.fig.add_subplot(111)
            self.axes = [self.ax]
            self._style_chart()
            self._style_chart_axes()
            self.lines = {}
            self.canvas.draw()
            return

        chart_data = self.trend.get_chart_data()
        self.lines = {}

        if self._isolated_mode and len(tags) > 1:
            n = len(tags)
            self.axes = []
            for i, tag in enumerate(tags):
                ax = self.fig.add_subplot(n, 1, i + 1)
                self.axes.append(ax)
                lp = self._get_line_props(tag, i)
                times, vals = chart_data.get(tag, ([], []))
                line, = ax.plot(times, vals, label=tag,
                                color=lp["color"], linewidth=lp["width"],
                                linestyle=lp["style"])
                self.lines[tag] = line
                short_name = tag.split(".")[-1] if "." in tag else tag
                ax.set_ylabel(short_name, fontsize=8, color=text_color)
                ax.legend(loc="upper left", fontsize=7, facecolor=face_color,
                          edgecolor=grid_color, labelcolor=text_color)
                scale = self._tag_scales.get(tag)
                if scale and not scale.get("auto", True):
                    ax.autoscale(enable=False, axis='y')
                    ax.set_ylim(scale.get("min", 0), scale.get("max", 100))
                if i < n - 1:
                    ax.tick_params(axis="x", labelbottom=False)
                    ax.set_xlabel("")
            self.ax = self.axes[0]
        else:
            self.ax = self.fig.add_subplot(111)
            self.axes = [self.ax]
            for i, tag in enumerate(tags):
                lp = self._get_line_props(tag, i)
                times, vals = chart_data.get(tag, ([], []))
                line, = self.ax.plot(times, vals, label=tag,
                                     color=lp["color"], linewidth=lp["width"],
                                     linestyle=lp["style"])
                self.lines[tag] = line
            self.ax.legend(loc="upper left", fontsize=8, facecolor=face_color,
                           edgecolor=grid_color, labelcolor=text_color)

            for tag in tags:
                scale = self._tag_scales.get(tag)
                if scale and not scale.get("auto", True):
                    self.ax.autoscale(enable=False, axis='y')
                    self.ax.set_ylim(scale.get("min", 0), scale.get("max", 100))
                    break

        self._style_chart()
        self._style_chart_axes()

        # Apply time window
        has_data = chart_data and any(times for times, _ in chart_data.values())
        if has_data:
            fmt = mdates.DateFormatter("%H:%M:%S")
            for a in self.axes:
                a.xaxis.set_major_formatter(fmt)

            if self._follow_live and self.view_mode == "live":
                now = datetime.now()
                window_start = now - timedelta(seconds=self._time_span_seconds)
                for a in self.axes:
                    a.set_xlim(window_start, now)
            else:
                t_start, t_end = self.trend.get_time_range()
                if t_start and t_end:
                    span = (t_end - t_start).total_seconds()
                    if span <= self._time_span_seconds:
                        for a in self.axes:
                            a.set_xlim(t_start, t_end)
                    else:
                        view_start = t_end - timedelta(seconds=self._time_span_seconds)
                        for a in self.axes:
                            a.set_xlim(view_start, t_end)

            # Autoscale Y only for axes without manual scales
            if self._isolated_mode and len(self.axes) > 1:
                for i, a in enumerate(self.axes):
                    tag = tags[i] if i < len(tags) else None
                    scale = self._tag_scales.get(tag) if tag else None
                    if scale and not scale.get("auto", True):
                        pass
                    else:
                        a.relim()
                        a.autoscale_view(scalex=False, scaley=True)
            else:
                has_manual = any(
                    not self._tag_scales.get(t, {}).get("auto", True) for t in tags
                )
                if not has_manual:
                    self.ax.relim()
                    self.ax.autoscale_view(scalex=False, scaley=True)

            self.fig.autofmt_xdate(rotation=0, ha="center")
            if self._isolated_mode and len(self.axes) > 1:
                for a in self.axes[:-1]:
                    a.tick_params(axis="x", labelbottom=False)
                    a.set_xlabel("")

        self._apply_tight_layout()
        self.canvas.draw()
        self._update_scrollbar()
        # Connect xlim sync AFTER draw (avoids triggering during build)
        self._connect_xlim_sync()

    def _apply_tag_scales(self):
        """Apply per-tag scale settings to current axes."""
        tags = self._get_ordered_tags()
        if self._isolated_mode and len(self.axes) > 1:
            for i, tag in enumerate(tags):
                if i < len(self.axes):
                    ax = self.axes[i]
                    scale = self._tag_scales.get(tag)
                    if scale and not scale.get("auto", True):
                        ax.autoscale(enable=False, axis='y')
                        ax.set_ylim(scale.get("min", 0), scale.get("max", 100))
                    else:
                        ax.autoscale(enable=True, axis='y')
                        ax.relim()
                        ax.autoscale_view(scaley=True, scalex=False)
        else:
            manual_ylim = None
            for tag in tags:
                scale = self._tag_scales.get(tag)
                if scale and not scale.get("auto", True):
                    manual_ylim = (scale.get("min", 0), scale.get("max", 100))
                    break
            if manual_ylim:
                self.ax.autoscale(enable=False, axis='y')
                self.ax.set_ylim(manual_ylim)
            else:
                self.ax.autoscale(enable=True, axis='y')
                self.ax.relim()
                self.ax.autoscale_view(scaley=True, scalex=False)
        try: self.canvas.draw_idle()
        except Exception: pass

    def _show_chart_properties(self):
        """Open tabbed Trend Properties dialog (X-Axis, Y-Axis, Display)."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Trend Properties")
        dlg.geometry("560x520")
        dlg.resizable(False, True)
        dlg.configure(fg_color=BG_DARK)
        dlg.transient(self)
        dlg.grab_set()

        try:
            x = self.winfo_x() + self.winfo_width() // 2 - 280
            y = self.winfo_y() + 80
            dlg.geometry(f"+{x}+{y}")
        except Exception: pass

        # Notebook with tabs
        style = ttk.Style()
        style.configure("Props.TNotebook", background=resolve_color(BG_DARK))
        style.configure("Props.TNotebook.Tab", font=(FONT_FAMILY, FONT_SIZE_BODY),
                         padding=[12, 4])
        notebook = ttk.Notebook(dlg, style="Props.TNotebook")
        notebook.pack(fill="both", expand=True, padx=12, pady=(12, 4))

        # ===== X-AXIS TAB =====
        x_tab = ctk.CTkFrame(notebook, fg_color=BG_MEDIUM)
        notebook.add(x_tab, text="X-Axis")

        # Time span
        grp1 = ctk.CTkFrame(x_tab, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        grp1.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(grp1, text="Time Span (visible window)",
                     font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(10, 4))

        span_row = ctk.CTkFrame(grp1, fg_color="transparent")
        span_row.pack(fill="x", padx=12, pady=(0, 10))

        # Parse current time span into value + unit
        cur_span = self._time_span_seconds
        if cur_span >= 3600 and cur_span % 3600 == 0:
            span_val, span_unit = cur_span // 3600, "Hour(s)"
        elif cur_span >= 60 and cur_span % 60 == 0:
            span_val, span_unit = cur_span // 60, "Minute(s)"
        else:
            span_val, span_unit = cur_span, "Second(s)"

        span_entry = ctk.CTkEntry(span_row, width=80, height=28,
                                   font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                   fg_color=BG_INPUT, border_color=BORDER_COLOR,
                                   text_color=TEXT_PRIMARY)
        span_entry.pack(side="left", padx=(0, 8))
        span_entry.insert(0, str(int(span_val)))

        span_unit_var = ctk.StringVar(value=span_unit)
        ctk.CTkOptionMenu(span_row, variable=span_unit_var,
                          values=["Second(s)", "Minute(s)", "Hour(s)"],
                          font=(FONT_FAMILY, FONT_SIZE_SMALL),
                          fg_color=BG_INPUT, button_color=SAS_BLUE,
                          button_hover_color=SAS_BLUE_DARK,
                          dropdown_fg_color=BG_MEDIUM,
                          width=120, height=28).pack(side="left")

        # X-axis display options
        grp1b = ctk.CTkFrame(x_tab, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        grp1b.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(grp1b, text="Display Options",
                     font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(10, 4))

        x_scale_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(grp1b, text="Display scale", variable=x_scale_var,
                        font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                        fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                        border_color=BORDER_COLOR).pack(anchor="w", padx=12, pady=2)

        x_grid_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(grp1b, text="Display grid lines", variable=x_grid_var,
                        font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                        fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                        border_color=BORDER_COLOR).pack(anchor="w", padx=12, pady=(2, 10))

        # ===== Y-AXIS TAB =====
        y_tab = ctk.CTkFrame(notebook, fg_color=BG_MEDIUM)
        notebook.add(y_tab, text="Y-Axis")

        # Scale options group
        grp2 = ctk.CTkFrame(y_tab, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        grp2.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(grp2, text="Scale Options",
                     font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(10, 4))

        scale_mode_var = ctk.StringVar(value=self._scale_mode)
        for val, txt in [("same", "All pens on same scale"),
                         ("independent", "Each pen on independent scale")]:
            ctk.CTkRadioButton(grp2, text=txt, variable=scale_mode_var, value=val,
                               font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                               fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                               border_color=BORDER_COLOR).pack(anchor="w", padx=12, pady=2)

        iso_var = ctk.BooleanVar(value=self._isolated_mode)
        ctk.CTkCheckBox(grp2, text="Isolated graphing (each pen on its own chart)",
                        variable=iso_var,
                        font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                        fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                        border_color=BORDER_COLOR).pack(anchor="w", padx=12, pady=(6, 10))

        # Per-tag scale cards
        tags = self._get_ordered_tags()
        if tags:
            grp3 = ctk.CTkFrame(y_tab, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
            grp3.pack(fill="x", padx=12, pady=(0, 8))

            ctk.CTkLabel(grp3, text="Per-Tag Scale Configuration",
                         font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                         text_color=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(10, 4))

            tag_scroll = ctk.CTkScrollableFrame(grp3, fg_color="transparent",
                                                  scrollbar_button_color=BG_MEDIUM,
                                                  height=180)
            tag_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

            tag_widgets = {}
            for i, tag in enumerate(tags):
                lp = self._get_line_props(tag, i)
                color = lp["color"]
                scale = self._tag_scales.get(tag, {"auto": True, "min": 0, "max": 100})

                card = ctk.CTkFrame(tag_scroll, fg_color=BG_MEDIUM, corner_radius=6)
                card.pack(fill="x", pady=2)

                row1 = ctk.CTkFrame(card, fg_color="transparent")
                row1.pack(fill="x", padx=8, pady=(6, 2))

                swatch = tk.Canvas(row1, width=12, height=12, bd=0, highlightthickness=0,
                                   bg=resolve_color(BG_MEDIUM))
                swatch.pack(side="left", padx=(0, 6))
                swatch.create_rectangle(1, 1, 11, 11, fill=color, outline=color)

                short_name = tag.split(".")[-1] if "." in tag else tag
                ctk.CTkLabel(row1, text=short_name, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                             text_color=TEXT_PRIMARY).pack(side="left")

                auto_var = ctk.BooleanVar(value=scale.get("auto", True))
                ctk.CTkCheckBox(row1, text="Auto", variable=auto_var,
                               font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                               fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                               border_color=BORDER_COLOR, width=18, height=18,
                               checkbox_width=16, checkbox_height=16).pack(side="right")

                row2 = ctk.CTkFrame(card, fg_color="transparent")
                row2.pack(fill="x", padx=8, pady=(0, 6))

                ctk.CTkLabel(row2, text="Min:", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                             text_color=TEXT_SECONDARY).pack(side="left")
                min_e = ctk.CTkEntry(row2, width=70, height=24, font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                     fg_color=BG_INPUT, border_color=BORDER_COLOR, text_color=TEXT_PRIMARY)
                min_e.pack(side="left", padx=(4, 10))
                min_e.insert(0, str(scale.get("min", 0)))

                ctk.CTkLabel(row2, text="Max:", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                             text_color=TEXT_SECONDARY).pack(side="left")
                max_e = ctk.CTkEntry(row2, width=70, height=24, font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                     fg_color=BG_INPUT, border_color=BORDER_COLOR, text_color=TEXT_PRIMARY)
                max_e.pack(side="left", padx=(4, 0))
                max_e.insert(0, str(scale.get("max", 100)))

                tag_widgets[tag] = {"auto": auto_var, "min": min_e, "max": max_e}
        else:
            tag_widgets = {}

        # ===== DISPLAY TAB =====
        d_tab = ctk.CTkFrame(notebook, fg_color=BG_MEDIUM)
        notebook.add(d_tab, text="Display")

        grp4 = ctk.CTkFrame(d_tab, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        grp4.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(grp4, text="Legend",
                     font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(10, 4))

        legend_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(grp4, text="Display line legend", variable=legend_var,
                        font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                        fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                        border_color=BORDER_COLOR).pack(anchor="w", padx=12, pady=(2, 10))

        grp5 = ctk.CTkFrame(d_tab, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        grp5.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(grp5, text="Scrolling",
                     font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(10, 4))

        scroll_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(grp5, text="Allow scrolling", variable=scroll_var,
                        font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                        fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                        border_color=BORDER_COLOR).pack(anchor="w", padx=12, pady=(2, 4))

        cursor_var = ctk.BooleanVar(value=self._cursor_enabled)
        ctk.CTkCheckBox(grp5, text="Smart cursor (crosshair + value readout)",
                        variable=cursor_var,
                        font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                        fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                        border_color=BORDER_COLOR).pack(anchor="w", padx=12, pady=(2, 10))

        # ===== BUTTONS =====
        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 12))

        def apply_and_close():
            # X-Axis: Time span
            try:
                val = float(span_entry.get())
            except (ValueError, TypeError):
                val = 30
            unit = span_unit_var.get()
            if unit == "Minute(s)":
                val *= 60
            elif unit == "Hour(s)":
                val *= 3600
            self._time_span_seconds = max(1, int(val))

            # Y-Axis: Scale mode and isolated
            self._scale_mode = scale_mode_var.get()
            old_iso = self._isolated_mode
            self._isolated_mode = iso_var.get()

            # Per-tag scales
            for tag, w in tag_widgets.items():
                auto = w["auto"].get()
                try: mn = float(w["min"].get())
                except (ValueError, TypeError): mn = 0
                try: mx = float(w["max"].get())
                except (ValueError, TypeError): mx = 100
                if mn >= mx: mx = mn + 1
                self._tag_scales[tag] = {"auto": auto, "min": mn, "max": mx}

            # Display
            self._cursor_enabled = cursor_var.get()

            # Save to settings
            self.settings["time_span"] = self._time_span_seconds
            self.settings["isolated_mode"] = self._isolated_mode
            self.settings["scale_mode"] = self._scale_mode
            self.settings["smart_cursor"] = self._cursor_enabled
            save_settings(self.settings)

            # Rebuild chart if isolated mode changed, otherwise just apply scales
            if old_iso != self._isolated_mode:
                self._rebuild_chart()
            else:
                self._apply_tag_scales()
                # Reapply time window
                if self.view_mode == "live" and self._follow_live:
                    now = datetime.now()
                    ws = now - timedelta(seconds=self._time_span_seconds)
                    for a in self.axes:
                        a.set_xlim(ws, now)
                elif self.trend.data:
                    t_start, t_end = self.trend.get_time_range()
                    if t_start and t_end:
                        vs = t_end - timedelta(seconds=self._time_span_seconds)
                        for a in self.axes:
                            a.set_xlim(max(vs, t_start), t_end)
                try: self.canvas.draw_idle()
                except Exception: pass
            dlg.destroy()

        ctk.CTkButton(btn_row, text="Apply & Close",
                      font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                      fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                      corner_radius=BUTTON_CORNER_RADIUS, height=BUTTON_HEIGHT,
                      command=apply_and_close).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      fg_color="transparent", border_width=1, border_color=BORDER_COLOR,
                      text_color=TEXT_SECONDARY, hover_color=BG_CARD_HOVER,
                      corner_radius=BUTTON_CORNER_RADIUS, height=BUTTON_HEIGHT,
                      command=dlg.destroy).pack(side="right")

    # == SMART CURSOR ==
    def _clear_cursor_elements(self):
        """Remove all existing cursor overlay artists from the chart."""
        for artist in self._cursor_annotations:
            try: artist.remove()
            except (ValueError, AttributeError): pass
        self._cursor_annotations = []
        for artist in getattr(self, "_cursor_dots", []):
            try: artist.remove()
            except (ValueError, AttributeError): pass
        self._cursor_dots = []
        if self._cursor_vline is not None:
            try: self._cursor_vline.remove()
            except (ValueError, AttributeError): pass
            self._cursor_vline = None
        # Remove vlines from isolated subplots
        for vl in getattr(self, "_cursor_vlines", []):
            try: vl.remove()
            except (ValueError, AttributeError): pass
        self._cursor_vlines = []

    def _on_chart_mouse_move(self, event):
        """Smart cursor: vertical line + value readout at mouse position."""
        if not self._cursor_enabled:
            return
        # Check if mouse is in any of our axes
        active_ax = None
        for a in self.axes:
            if event.inaxes == a:
                active_ax = a
                break
        if active_ax is None or event.xdata is None:
            return
        if not hasattr(self, "lines") or not self.lines:
            return

        # Save current axis limits BEFORE any cursor drawing
        saved_limits = [(a.get_xlim(), a.get_ylim()) for a in self.axes]

        self._clear_cursor_elements()

        # Draw vertical cursor line on ALL axes (so the crosshair spans the full chart)
        cursor_color = resolve_color(TEXT_MUTED)
        self._cursor_vlines = []
        for a in self.axes:
            vl = a.axvline(x=event.xdata, color=cursor_color,
                           linewidth=0.8, linestyle="--", alpha=0.7)
            self._cursor_vlines.append(vl)
        self._cursor_vline = self._cursor_vlines[0] if self._cursor_vlines else None

        # Get chart data
        chart_data = self.trend.get_chart_data()
        if not chart_data:
            try: self.canvas.draw_idle()
            except Exception: pass
            return

        try:
            mouse_dt = mdates.num2date(event.xdata)
        except Exception:
            try: self.canvas.draw_idle()
            except Exception: pass
            return

        # Find nearest index from first tag's time array
        first_tag = next(iter(chart_data), None)
        if not first_tag:
            try: self.canvas.draw_idle()
            except Exception: pass
            return
        times, _ = chart_data[first_tag]
        if not times:
            try: self.canvas.draw_idle()
            except Exception: pass
            return

        try:
            time_nums = mdates.date2num(times)
        except Exception:
            try: self.canvas.draw_idle()
            except Exception: pass
            return
        mouse_num = event.xdata
        idx = bisect_left(time_nums, mouse_num)
        if idx >= len(time_nums):
            idx = len(time_nums) - 1
        elif idx > 0:
            if abs(time_nums[idx] - mouse_num) > abs(time_nums[idx - 1] - mouse_num):
                idx = idx - 1

        nearest_time = times[idx]
        ts_str = nearest_time.strftime("%H:%M:%S.%f")[:-3]

        self._cursor_dots = []
        # Single tooltip with all tag values
        text_lines = [f"\u23F1 {ts_str}"]
        ordered_tags = self._get_ordered_tags()
        tags_list = list(chart_data.keys())
        for i, (tag, (t_arr, v_arr)) in enumerate(chart_data.items()):
            if idx < len(v_arr):
                val = v_arr[idx]
                # Find this tag's display index for color and axis mapping
                disp_idx = ordered_tags.index(tag) if tag in ordered_tags else i
                lp = self._get_line_props(tag, disp_idx)
                color = lp["color"]
                short_name = tag.split(".")[-1] if "." in tag else tag
                if val is not None and val == val:  # val==val is False for NaN
                    val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
                    # In isolated mode, draw dot on the tag's own axis
                    dot_ax = self.axes[disp_idx] if self._isolated_mode and disp_idx < len(self.axes) else self.ax
                    dot = dot_ax.plot(t_arr[idx], val, "o", color=color,
                                      markersize=6, markeredgecolor="white",
                                      markeredgewidth=1.0, zorder=10)
                    self._cursor_dots.extend(dot)
                    text_lines.append(f"\u25CF {short_name}: {val_str}")
                else:
                    text_lines.append(f"\u25CB {short_name}: ---")

        readout_text = "\n".join(text_lines)
        xlim = active_ax.get_xlim()
        x_range = xlim[1] - xlim[0]
        ha = "left"; x_offset = 12
        if x_range > 0 and (event.xdata - xlim[0]) / x_range > 0.65:
            ha = "right"; x_offset = -12

        ann = active_ax.annotate(
            readout_text,
            xy=(event.xdata, event.ydata),
            xytext=(x_offset, 12), textcoords="offset points",
            fontsize=9, fontfamily=FONT_FAMILY_MONO,
            color=resolve_color(TEXT_PRIMARY), ha=ha, va="bottom",
            bbox=dict(boxstyle="round,pad=0.5", facecolor=resolve_color(BG_CARD),
                      edgecolor=resolve_color(BORDER_COLOR), alpha=0.92),
            zorder=20)
        self._cursor_annotations.append(ann)

        # Restore axis limits — prevents cursor from causing zoom drift
        for a, (xl, yl) in zip(self.axes, saved_limits):
            a.set_xlim(xl)
            a.set_ylim(yl)

        try: self.canvas.draw_idle()
        except Exception: pass

    def _on_chart_mouse_leave(self, event):
        """Remove cursor elements when mouse leaves the chart area."""
        self._clear_cursor_elements()
        try: self.canvas.draw_idle()
        except Exception: pass

    def _update_storage_info(self):
        """Update the storage info label with current usage."""
        current_pts = self.trend.point_count
        max_pts = self.trend.max_points
        n_tags = len(self.trend.tags) if self.trend.tags else 0
        if current_pts > 0 and n_tags > 0:
            # Rough estimate: ~100 bytes per tag per point + overhead
            est_bytes = current_pts * (100 * n_tags + 80)
            if est_bytes > 1024 * 1024:
                est_str = f"{est_bytes / (1024*1024):.1f} MB"
            else:
                est_str = f"{est_bytes / 1024:.0f} KB"
            pct = (current_pts / max_pts) * 100 if max_pts > 0 else 0
            self._storage_info_label.configure(
                text=f"Current: {current_pts:,} / {max_pts:,} points ({pct:.0f}%)  •  Est. memory: {est_str}  •  {n_tags} tags")
        else:
            self._storage_info_label.configure(
                text=f"Current: {current_pts:,} / {max_pts:,} points  •  No active trend data")

    # == CONNECTION LOGIC ==
    def _connect(self):
        if self.plc.connected:
            self._disconnect()
            return
        ip = self.ip_entry.get().strip()
        slot = self.slot_entry.get().strip() or "0"
        ctype = self.controller_type_var.get()
        if not ip:
            self.conn_status_label.configure(text="Enter an IP address.", text_color=STATUS_ERROR)
            return
        self.connect_btn.configure(state="disabled", text="Connecting...")
        self.conn_status_label.configure(text="")
        def do_connect():
            success, message = self.plc.connect(ip, slot, ctype)
            self.after(0, lambda: self._on_connect_result(success, message))
        threading.Thread(target=do_connect, daemon=True).start()

    def _on_connect_result(self, success, message):
        if success:
            self.connect_btn.configure(state="normal", text="Disconnect", fg_color=STATUS_ERROR, hover_color="#b91c1c")
            self.conn_status_label.configure(text="\u2713 Connected", text_color=STATUS_GOOD)
            self.device_info_label.configure(
                text=f"Device: {message}\nIP: {self.plc.ip}  |  Slot: {self.plc.slot}  |  Type: {self.plc.controller_type}",
                text_color=TEXT_PRIMARY)
            self._sidebar_status.configure(text=f"\u25CF Connected -- {self.plc.ip}", text_color=STATUS_GOOD)
            self._fetch_tags()
            # Show trend view with tag panel visible
            self._show_tags_view()
        else:
            self.connect_btn.configure(state="normal", text="Connect", fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK)
            self.conn_status_label.configure(text=message, text_color=STATUS_ERROR)

    def _disconnect(self):
        if self.trend.trending:
            self._stop_trend()
        self.plc.disconnect()
        self.connect_btn.configure(text="Connect", fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK)
        self.conn_status_label.configure(text="")
        self.device_info_label.configure(text="Not connected -- connect to a PLC to see device information.", text_color=TEXT_MUTED)
        self._sidebar_status.configure(text="\u25CF Disconnected", text_color=STATUS_OFFLINE)
        self._set_tag_placeholder("Connect to a PLC to browse tags")
        self.selected_tags.clear()
        self._update_selected_count()
        self._sync_tags_to_chart()

    # == TAG BROWSER LOGIC ==
    def _set_tag_placeholder(self, text):
        for item in self.tag_tree.get_children():
            self.tag_tree.delete(item)
        self.tag_tree.insert("", "end", text=text, values=("",))
        self.tag_count_label.configure(text="")

    def _fetch_tags(self):
        self._set_tag_placeholder("Loading tags...")
        def do_fetch():
            ctrl_tags, prog_tags, error = self.plc.get_tags()
            self.after(0, lambda: self._on_tags_fetched(ctrl_tags, prog_tags, error))
        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_tags_fetched(self, ctrl_tags, prog_tags, error):
        for item in self.tag_tree.get_children():
            self.tag_tree.delete(item)
        if error:
            self.tag_tree.insert("", "end", text=f"Error: {error}", values=("",))
            return
        self.all_ctrl_tags = ctrl_tags
        self.all_prog_tags = prog_tags
        self.tag_data_types = {}
        total = 0
        muted = resolve_color(TEXT_MUTED)
        primary = resolve_color(TEXT_PRIMARY)
        if ctrl_tags:
            gid = self.tag_tree.insert("", "end", text=f"Controller Tags ({len(ctrl_tags)})", values=("",), open=True, tags=("group",))
            for tag in ctrl_tags:
                self.tag_data_types[tag["name"]] = tag["dataType"]
                prefix = "\u2611 " if tag["name"] in self.selected_tags else "\u2610 "
                tt = "trendable" if tag["trendable"] else "disabled"
                self.tag_tree.insert(gid, "end", text=prefix + tag["name"], values=(tag["dataType"],), tags=(tt, tag["name"]))
                total += 1
        for prog_name in sorted(prog_tags.keys()):
            tags = prog_tags[prog_name]
            gid = self.tag_tree.insert("", "end", text=f"{prog_name} ({len(tags)})", values=("",), open=False, tags=("group",))
            for tag in tags:
                self.tag_data_types[tag["name"]] = tag["dataType"]
                prefix = "\u2611 " if tag["name"] in self.selected_tags else "\u2610 "
                dn = tag["name"].split(".")[-1] if "." in tag["name"] else tag["name"]
                tt = "trendable" if tag["trendable"] else "disabled"
                self.tag_tree.insert(gid, "end", text=prefix + dn, values=(tag["dataType"],), tags=(tt, tag["name"]))
                total += 1
        self.tag_tree.tag_configure("group", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"))
        self.tag_tree.tag_configure("disabled", foreground=muted)
        self.tag_tree.tag_configure("trendable", foreground=primary)
        self.tag_count_label.configure(text=f"{total} tags")
        self._update_selected_count()

    def _on_tag_click(self, event):
        item = self.tag_tree.identify_row(event.y)
        if not item: return
        item_tags = self.tag_tree.item(item, "tags")
        if "group" in item_tags or "disabled" in item_tags: return
        tag_name = None
        for t in item_tags:
            if t not in ("trendable", "disabled", "group"):
                tag_name = t
                break
        if not tag_name: return
        ct = self.tag_tree.item(item, "text")
        if tag_name in self.selected_tags:
            self.selected_tags.discard(tag_name)
            self.tag_tree.item(item, text="\u2610 " + ct[2:])
        else:
            self.selected_tags.add(tag_name)
            self.tag_tree.item(item, text="\u2611 " + ct[2:])
        self._update_selected_count()
        self._sync_tags_to_chart()

    def _filter_tags(self):
        query = self.tag_search_var.get().lower().strip()
        for item in self.tag_tree.get_children(): self.tag_tree.delete(item)
        def matches(tag): return not query or query in tag["name"].lower() or query in tag["dataType"].lower()
        muted = resolve_color(TEXT_MUTED)
        primary = resolve_color(TEXT_PRIMARY)
        fc = [t for t in self.all_ctrl_tags if matches(t)]
        if fc:
            gid = self.tag_tree.insert("", "end", text=f"Controller Tags ({len(fc)})", values=("",), open=True, tags=("group",))
            for tag in fc:
                prefix = "\u2611 " if tag["name"] in self.selected_tags else "\u2610 "
                tt = "trendable" if tag["trendable"] else "disabled"
                self.tag_tree.insert(gid, "end", text=prefix + tag["name"], values=(tag["dataType"],), tags=(tt, tag["name"]))
        for pn in sorted(self.all_prog_tags.keys()):
            fp = [t for t in self.all_prog_tags[pn] if matches(t)]
            if fp or (query and query in pn.lower()):
                ts = fp if fp else self.all_prog_tags[pn]
                gid = self.tag_tree.insert("", "end", text=f"{pn} ({len(ts)})", values=("",), open=bool(query), tags=("group",))
                for tag in ts:
                    prefix = "\u2611 " if tag["name"] in self.selected_tags else "\u2610 "
                    dn = tag["name"].split(".")[-1] if "." in tag["name"] else tag["name"]
                    tt = "trendable" if tag["trendable"] else "disabled"
                    self.tag_tree.insert(gid, "end", text=prefix + dn, values=(tag["dataType"],), tags=(tt, tag["name"]))
        self.tag_tree.tag_configure("group", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"))
        self.tag_tree.tag_configure("disabled", foreground=muted)
        self.tag_tree.tag_configure("trendable", foreground=primary)

    def _select_all_visible(self):
        def walk(parent):
            for item in self.tag_tree.get_children(parent):
                tags = self.tag_tree.item(item, "tags")
                if "trendable" in tags:
                    for t in tags:
                        if t not in ("trendable", "disabled", "group"):
                            self.selected_tags.add(t)
                            ct = self.tag_tree.item(item, "text")
                            if ct.startswith("\u2610 "): self.tag_tree.item(item, text="\u2611 " + ct[2:])
                            break
                walk(item)
        walk("")
        self._update_selected_count()
        self._sync_tags_to_chart()

    def _clear_selection(self):
        self.selected_tags.clear()
        if self.all_ctrl_tags: self._filter_tags()
        self._update_selected_count()
        self._sync_tags_to_chart()

    def _update_selected_count(self):
        count = len(self.selected_tags)
        self.selected_label.configure(text=f"{count} selected")
        self.start_btn.configure(state="normal" if count > 0 and self.plc.connected else "disabled")
        # Update tag toggle button with count
        if count > 0:
            self._tag_toggle_btn.configure(text=f"\U0001F3F7 Tags ({count})")
        else:
            self._tag_toggle_btn.configure(text="\U0001F3F7 Tags")

    def _sync_tags_to_chart(self):
        """Sync selected tags to the chart immediately.
        Works pre-trend (preview with empty lines) and mid-trend (live add/remove)."""
        tags = list(self.selected_tags)

        # Initialize per-tag scales for any new tags
        for tag in tags:
            if tag not in self._tag_scales:
                self._tag_scales[tag] = {"auto": True, "min": 0, "max": 100}

        # If actively trending, update the trend manager's tag list
        if self.trend.trending:
            self.trend.update_tags(tags)
            if not tags:
                # All tags removed mid-trend — stop trending
                self._stop_trend()
                return
            self._sidebar_status.configure(
                text=f"\u25CF Trending -- {len(tags)} tags @ {self.plc.ip}",
                text_color=SAS_ORANGE)

        # Rebuild chart (works with empty data for preview)
        self._rebuild_chart()

        # Update UI state
        if tags and not self.trend.trending:
            self.view_badge_label.configure(text="\u25CF READY", fg=SAS_BLUE)
        elif not tags and not self.trend.trending:
            self.view_badge_label.configure(text="", fg=resolve_color(TEXT_MUTED))
            self.point_label.configure(text="")

    # == TRENDING LOGIC ==
    def _parse_sample_rate(self):
        rate_map = {"100 ms": 0.1, "250 ms": 0.25, "500 ms": 0.5, "1 sec": 1.0, "2 sec": 2.0,
                    "5 sec": 5.0, "10 sec": 10.0, "30 sec": 30.0, "60 sec": 60.0}
        return rate_map.get(self.rate_var.get(), 1.0)

    def _start_trend(self):
        if not self.selected_tags: return
        tags = list(self.selected_tags)
        rate = self._parse_sample_rate()

        # Scales and tag order already initialized by _sync_tags_to_chart
        self.trend.start(tags, rate)
        self.view_mode = "live"

        # Rebuild chart to reset axes for fresh data collection
        self._rebuild_chart()

        self.trend_thread = threading.Thread(target=self._trend_loop, daemon=True)
        self.trend_thread.start()
        update_interval = max(int(rate * 800), 200)
        self._schedule_chart_update(update_interval)

        self.start_btn.pack_forget()
        self.resume_btn.pack_forget()
        self.pause_btn.pack(side="left", padx=(0, 2))
        self.stop_btn.pack(side="left", padx=(0, 6))
        self._paused = False
        self._follow_live = True
        self.export_json_btn.configure(state="normal")
        self.export_csv_btn.configure(state="normal")
        self.clear_data_btn.configure(state="normal")
        self.view_badge_label.configure(text="\u25CF LIVE", fg=STATUS_GOOD)
        self._sidebar_status.configure(text=f"\u25CF Trending -- {len(tags)} tags @ {self.plc.ip}", text_color=SAS_ORANGE)
        self._show_trend_view()

    def _trend_loop(self):
        while self.trend.trending:
            if self.plc.connected:
                values = self.plc.read_tags(self.trend.tags)
                if values: self.trend.add_point(values)
            time.sleep(self.trend.sample_rate)

    def _schedule_chart_update(self, interval_ms):
        if self.chart_update_timer: self.after_cancel(self.chart_update_timer)
        self.chart_update_timer = self.after(interval_ms, lambda: self._update_display(interval_ms))

    def _update_display(self, interval_ms):
        if not self.trend.trending and self.view_mode == "live": return
        
        # When paused, keep collecting but don't update chart
        if self._paused:
            self.point_label.configure(text=f"{self.trend.point_count:,} points")
            if hasattr(self, "_storage_info_label"):
                self._update_storage_info()
            if self.trend.trending:
                self.chart_update_timer = self.after(interval_ms, lambda: self._update_display(interval_ms))
            return

        chart_data = self.trend.get_chart_data()
        any_data = False

        # Save xlim per-axis BEFORE any modifications (for manual scroll preservation)
        saved_xlims = {}
        if not self._follow_live:
            for i, a in enumerate(self.axes):
                try: saved_xlims[i] = a.get_xlim()
                except Exception: pass

        if self._isolated_mode and len(self.axes) > 1:
            ordered_tags = self._get_ordered_tags()
            for tag in ordered_tags:
                if tag in self.lines:
                    times, vals = chart_data.get(tag, ([], []))
                    if times:
                        self.lines[tag].set_data(times, vals)
                        any_data = True
            if any_data:
                for i, tag in enumerate(ordered_tags):
                    if i < len(self.axes):
                        ax = self.axes[i]
                        ax.relim()
                        scale = self._tag_scales.get(tag)
                        if scale and not scale.get("auto", True):
                            ax.autoscale(enable=False, axis='y')
                            ax.set_ylim(scale["min"], scale["max"])
                            ax.autoscale(enable=True, axis='x')
                            ax.autoscale_view(scalex=True, scaley=False)
                        else:
                            ax.autoscale(enable=True)
                            ax.autoscale_view()
        else:
            for tag, (times, vals) in chart_data.items():
                if tag in self.lines and times:
                    self.lines[tag].set_data(times, vals)
                    any_data = True
            if any_data:
                self.ax.relim()
                # Check for manual Y scale
                manual_ylim = None
                for tag in self.trend.tags:
                    scale = self._tag_scales.get(tag)
                    if scale and not scale.get("auto", True):
                        manual_ylim = (scale["min"], scale["max"])
                        break
                if manual_ylim:
                    # Autoscale X only, set Y manually
                    self.ax.autoscale(enable=False, axis='y')
                    self.ax.set_ylim(manual_ylim)
                    self.ax.autoscale(enable=True, axis='x')
                    self.ax.autoscale_view(scalex=True, scaley=False)
                else:
                    self.ax.autoscale(enable=True)
                    self.ax.autoscale_view()

        if any_data:
            # Set X range
            if self._follow_live and self.view_mode == "live":
                now = datetime.now()
                window_start = now - timedelta(seconds=self._time_span_seconds)
                for a in self.axes:
                    a.set_xlim(window_start, now)
            elif saved_xlims:
                # Restore user's scroll position (autoscale_view reset it)
                for i, a in enumerate(self.axes):
                    if i in saved_xlims:
                        a.set_xlim(saved_xlims[i])

            self._update_scrollbar()

            fmt = mdates.DateFormatter("%H:%M:%S")
            for a in self.axes:
                a.xaxis.set_major_formatter(fmt)
            self.fig.autofmt_xdate(rotation=0, ha="center")
            # Re-hide x tick labels on non-bottom subplots after autofmt_xdate
            if self._isolated_mode and len(self.axes) > 1:
                for a in self.axes[:-1]:
                    a.tick_params(axis="x", labelbottom=False)
                    a.set_xlabel("")
            try: self.canvas.draw_idle()
            except Exception: pass

        self._update_live_table()
        self.point_label.configure(text=f"{self.trend.point_count:,} points")
        if hasattr(self, "_storage_info_label"):
            self._update_storage_info()
        if self.trend.trending:
            self.chart_update_timer = self.after(interval_ms, lambda: self._update_display(interval_ms))

    def _update_scrollbar(self):
        """Update the horizontal scrollbar to reflect current view vs total data."""
        t_start, t_end = self.trend.get_time_range()
        if t_start is None or t_end is None or not self.axes:
            self._chart_scrollbar.set(0.0, 1.0)
            return
        total_seconds = max((t_end - t_start).total_seconds(), 0.001)
        try:
            xlim = self.axes[0].get_xlim()
            view_start = mdates.num2date(xlim[0]).replace(tzinfo=None)
            view_end = mdates.num2date(xlim[1]).replace(tzinfo=None)
        except Exception:
            self._chart_scrollbar.set(0.0, 1.0)
            return
        frac_start = max(0.0, (view_start - t_start).total_seconds() / total_seconds)
        frac_end = min(1.0, (view_end - t_start).total_seconds() / total_seconds)
        self._chart_scrollbar.set(frac_start, frac_end)

    def _on_chart_xscroll(self, *args):
        """Handle scrollbar drag to scroll through trend history."""
        t_start, t_end = self.trend.get_time_range()
        if t_start is None or t_end is None:
            return
        total_seconds = max((t_end - t_start).total_seconds(), 0.001)

        if args[0] == "moveto":
            fraction = float(args[1])
            view_start = t_start + timedelta(seconds=fraction * total_seconds)
            view_end = view_start + timedelta(seconds=self._time_span_seconds)
            self._follow_live = False
            for a in self.axes:
                a.set_xlim(view_start, view_end)
            try: self.canvas.draw_idle()
            except Exception: pass
            self._update_scrollbar()
        elif args[0] == "scroll":
            amount = int(args[1])
            unit = args[2] if len(args) > 2 else "units"
            step = self._time_span_seconds * 0.1 if unit == "units" else self._time_span_seconds * 0.5
            try:
                xlim = self.axes[0].get_xlim()
                view_start = mdates.num2date(xlim[0]).replace(tzinfo=None) + timedelta(seconds=amount * step)
                view_end = view_start + timedelta(seconds=self._time_span_seconds)
            except Exception:
                return
            self._follow_live = False
            for a in self.axes:
                a.set_xlim(view_start, view_end)
            try: self.canvas.draw_idle()
            except Exception: pass
            self._update_scrollbar()

    def _snap_to_live(self):
        """Snap chart back to following live data."""
        self._follow_live = True
        if self.trend.data:
            now = datetime.now() if self.trend.trending else self.trend.data[-1]["dt"]
            window_start = now - timedelta(seconds=self._time_span_seconds)
            tags = self._get_ordered_tags()
            for i, a in enumerate(self.axes):
                a.set_xlim(window_start, now)
                tag = tags[i] if self._isolated_mode and i < len(tags) else None
                if self._isolated_mode and tag:
                    scale = self._tag_scales.get(tag)
                    if scale and not scale.get("auto", True):
                        continue
                elif not self._isolated_mode:
                    has_manual = any(
                        not self._tag_scales.get(t, {}).get("auto", True) for t in tags
                    )
                    if has_manual:
                        continue
                a.relim()
                a.autoscale_view(scalex=False, scaley=True)
            try: self.canvas.draw_idle()
            except Exception: pass
            self._update_scrollbar()

    def _pause_trend(self):
        """Pause display updates (data collection continues)."""
        self._paused = True
        self.pause_btn.pack_forget()
        self.resume_btn.pack(side="left", before=self.stop_btn, padx=(0, 2))
        self.view_badge_label.configure(text="\u275A\u275A PAUSED", fg=SAS_ORANGE)

    def _resume_trend(self):
        """Resume display updates from pause."""
        self._paused = False
        self._follow_live = True
        self.resume_btn.pack_forget()
        self.pause_btn.pack(side="left", before=self.stop_btn, padx=(0, 2))
        self.view_badge_label.configure(text="\u25CF LIVE", fg=STATUS_GOOD)

    def _stop_trend(self):
        self.trend.stop()
        if self.trend_thread:
            self.trend_thread.join(timeout=3)
            self.trend_thread = None
        if self.chart_update_timer:
            self.after_cancel(self.chart_update_timer)
            self.chart_update_timer = None
        self._update_display(0)
        self.stop_btn.pack_forget()
        self.pause_btn.pack_forget()
        self.resume_btn.pack_forget()
        self._paused = False
        self.start_btn.pack(side="left", padx=(0, 6))
        self.view_badge_label.configure(text="\u25A0 STOPPED", fg=resolve_color(TEXT_MUTED))
        if self.plc.connected:
            self._sidebar_status.configure(text=f"\u25CF Connected -- {self.plc.ip}", text_color=STATUS_GOOD)
        self._update_selected_count()

    def _update_live_table(self):
        for item in self.live_tree.get_children(): self.live_tree.delete(item)
        for tag in self._get_ordered_tags():
            dt = self.tag_data_types.get(tag, "---")
            val = self.trend.live_values.get(tag)
            mn = self.trend.min_values.get(tag)
            mx = self.trend.max_values.get(tag)
            def fmt(v):
                if v is None: return "---"
                if isinstance(v, float): return f"{v:.4f}"
                return str(v)
            self.live_tree.insert("", "end", values=(tag, dt, fmt(val), fmt(mn), fmt(mx), "OK" if val is not None else "ERR"))

    def _clear_data(self):
        self.trend.clear()
        self._clear_cursor_elements()
        self._tag_scales = {}
        self._rebuild_chart()
        self._update_live_table()
        self.point_label.configure(text="0 points")
        if hasattr(self, "_storage_info_label"):
            self._update_storage_info()

    # == EXPORT / IMPORT ==
    def _export_pytrend(self):
        if self.trend.point_count == 0:
            messagebox.showwarning("Export", "No data to export.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fp = filedialog.asksaveasfilename(title="Export Trend Data", defaultextension=".pytrend",
                                           filetypes=[("PLC Trend Files", "*.pytrend"), ("JSON Files", "*.json")],
                                           initialfile=f"trend_{ts}.pytrend")
        if not fp: return
        try:
            self.trend.export_pytrend(fp, self.plc.ip, self.plc.controller_type, self.plc.slot)
            messagebox.showinfo("Export", f"Exported {self.trend.point_count:,} points to:\n{fp}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_csv(self):
        if self.trend.point_count == 0:
            messagebox.showwarning("Export", "No data to export.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fp = filedialog.asksaveasfilename(title="Export CSV", defaultextension=".csv",
                                           filetypes=[("CSV Files", "*.csv")], initialfile=f"trend_{ts}.csv")
        if not fp: return
        try:
            self.trend.export_csv(fp)
            messagebox.showinfo("Export", f"Exported {self.trend.point_count:,} points to:\n{fp}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _import_file(self):
        fp = filedialog.askopenfilename(title="Import Trend File",
                                         filetypes=[("PLC Trend Files", "*.pytrend"), ("JSON Files", "*.json"), ("All Files", "*.*")])
        if not fp: return
        try:
            if self.trend.trending: self._stop_trend()
            meta = self.trend.import_pytrend(fp)
            self.view_mode = "historical"
            self._follow_live = False
            # Set selected_tags from imported data so _get_ordered_tags works
            self.selected_tags = set(self.trend.tags)
            for tag in self.trend.tags:
                if tag not in self.tag_data_types: self.tag_data_types[tag] = "---"
                if tag not in self._tag_scales:
                    self._tag_scales[tag] = {"auto": True, "min": 0, "max": 100}
            self._rebuild_chart()
            self._update_live_table()
            self.view_badge_label.configure(text="\U0001F4C2 HISTORICAL", fg=SAS_BLUE_LIGHT)
            self.export_json_btn.configure(state="normal")
            self.export_csv_btn.configure(state="normal")
            self.clear_data_btn.configure(state="normal")
            self.point_label.configure(text=f"{self.trend.point_count:,} points (imported)")
            self._show_trend_view()
            if hasattr(self, "_storage_info_label"):
                self._update_storage_info()
            messagebox.showinfo("Import", f"Loaded {meta.get('totalPoints', 0):,} points\nPLC: {meta.get('plcIP', '?')}\nTags: {', '.join(self.trend.tags)}")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))

    # == THEME ==
    def _on_theme_selected(self, value):
        self.settings["theme"] = value
        save_settings(self.settings)
        ctk.set_appearance_mode(value)
        self.after(100, self._refresh_after_theme_change)

    def _refresh_after_theme_change(self):
        self._apply_treeview_style()
        self._style_chart()
        self._style_chart_axes()  # styles all axes
        # Update plain tk.Frame wrappers that don't auto-theme
        if hasattr(self, "_toolbar_frame"):
            tb_bg = resolve_color(BG_MEDIUM)
            tb_fg = resolve_color(TEXT_SECONDARY)
            self._toolbar_frame.configure(bg=tb_bg)
            self._toolbar_inner.configure(bg=tb_bg)
            for w in self._toolbar_inner.winfo_children():
                try: w.configure(bg=tb_bg)
                except Exception: pass
        if hasattr(self, "_trend_view_frame"):
            self._trend_view_frame.configure(bg=resolve_color(BG_DARK))
        if hasattr(self, "_chart_wrapper"):
            self._chart_wrapper.configure(bg=resolve_color(BG_CARD),
                                           highlightbackground=resolve_color(BORDER_COLOR))
        if hasattr(self, "_nav_strip"):
            self._nav_strip.configure(bg=resolve_color(BG_CARD))
            for btn in self._nav_strip.winfo_children():
                btn.configure(bg=resolve_color(BG_CARD), fg=resolve_color(TEXT_SECONDARY),
                              activebackground=resolve_color(BG_CARD_HOVER),
                              activeforeground=resolve_color(TEXT_PRIMARY))
        if hasattr(self, "_chart_ctx_menu"):
            self._chart_ctx_menu.configure(bg=resolve_color(BG_CARD), fg=resolve_color(TEXT_PRIMARY),
                                            activebackground=SAS_BLUE)
        if hasattr(self, "_scroll_frame"):
            self._scroll_frame.configure(bg=resolve_color(BG_CARD))
        if hasattr(self, "_follow_btn"):
            self._follow_btn.configure(bg=resolve_color(BG_CARD), fg=SAS_BLUE)
        if hasattr(self, "_table_wrapper"):
            self._table_wrapper.configure(bg=resolve_color(BG_CARD),
                                           highlightbackground=resolve_color(BORDER_COLOR))
        if hasattr(self, "_paned"):
            self._paned.configure(bg=resolve_color(BORDER_COLOR))
        if hasattr(self, "_h_paned"):
            self._h_paned.configure(bg=resolve_color(BORDER_COLOR))
        if hasattr(self, "_tag_panel"):
            self._tag_panel.configure(bg=resolve_color(BG_CARD),
                                       highlightbackground=resolve_color(BORDER_COLOR))
        # Update legends on all axes
        if hasattr(self, "lines") and self.lines:
            text_color = resolve_color(TEXT_SECONDARY)
            face_color = resolve_color(BG_INPUT)
            grid_color = resolve_color(BORDER_COLOR)
            for a in self.axes:
                leg = a.get_legend()
                if leg:
                    leg.get_frame().set_facecolor(face_color)
                    leg.get_frame().set_edgecolor(grid_color)
                    for txt in leg.get_texts():
                        txt.set_color(text_color)
        try: self.canvas.draw_idle()
        except Exception: pass
        if self.all_ctrl_tags:
            self.tag_tree.tag_configure("disabled", foreground=resolve_color(TEXT_MUTED))
            self.tag_tree.tag_configure("trendable", foreground=resolve_color(TEXT_PRIMARY))

    # == SETTINGS PERSISTENCE ==
    def _restore_settings(self):
        if self.settings.get("last_ip"): self.ip_entry.insert(0, self.settings["last_ip"])
        if self.settings.get("last_slot") is not None:
            self.slot_entry.delete(0, "end")
            self.slot_entry.insert(0, str(self.settings["last_slot"]))
        if self.settings.get("last_controller"): self.controller_type_var.set(self.settings["last_controller"])
        if self.settings.get("sample_rate"): self.rate_var.set(self.settings["sample_rate"])

    def _save_current_settings(self):
        self.settings["last_ip"] = self.ip_entry.get().strip()
        try: self.settings["last_slot"] = int(self.slot_entry.get().strip())
        except ValueError: self.settings["last_slot"] = 0
        self.settings["last_controller"] = self.controller_type_var.get()
        self.settings["sample_rate"] = self.rate_var.get()
        self.settings["time_span"] = self._time_span_seconds
        self.settings["isolated_mode"] = self._isolated_mode
        self.settings["scale_mode"] = self._scale_mode
        self.settings["smart_cursor"] = self._cursor_enabled
        try:
            self.settings["window_width"] = self.winfo_width()
            self.settings["window_height"] = self.winfo_height()
        except Exception: pass
        save_settings(self.settings)

    # == CLOSE ==
    def _on_close(self):
        self._paused = False
        if self.trend.trending:
            self.trend.stop()
            if self.trend_thread: self.trend_thread.join(timeout=2)
        if self.chart_update_timer: self.after_cancel(self.chart_update_timer)
        self.plc.disconnect()
        self._save_current_settings()
        self.quit()
        self.destroy()


# =========================================================================
# ENTRY POINT
# =========================================================================
if __name__ == "__main__":
    app = PLCTrendTool()
    app.mainloop()
