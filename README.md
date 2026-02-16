# PLC Trend Tool

**Real-Time Tag Trending for Allen-Bradley PLCs**

A portable Windows desktop application for trending PLC tag data in real time. Connects to ControlLogix, CompactLogix, and Micro800 controllers via Ethernet/IP using [pylogix](https://github.com/dmroeder/pylogix), discovers tags automatically, and charts live values with full data export capability.

Built by [Southern Automation Solutions](https://southernautomationsolutions.com) — Valdosta, GA

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Quick Start (End User)

1. Copy `PLC_Trend_Tool.exe` to any Windows 10/11 PC
2. Double-click to run — no installation required
3. Enter the controller IP address and click **Connect**
4. Select tags from the built-in tag browser panel
5. Click **▶ Start Trend** to begin collecting data

No Python, no drivers, no admin rights required. Single `.exe`, fully portable.

---

## Features

### PLC Connection
- Supports Allen-Bradley **ControlLogix**, **CompactLogix**, and **Micro800** controllers
- Configurable processor slot for multi-slot ControlLogix chassis
- Validates connection with device identity query
- Displays device name, firmware revision, and connection details

### Live Tag Browser
- Retrieves full controller and program-scoped tag lists with data types
- Search and filter tags by name or data type
- Checkbox selection with Select All / Clear controls
- **Tags panel is embedded in the trend view** — select tags and watch the chart update in real time, before or during a trend
- Collapsible tag panel with resizable splitter to maximize chart area
- Tags can be added or removed mid-trend without stopping data collection

### Real-Time Trending
- Background polling thread at configurable sample rates (100 ms to 60 sec)
- Matplotlib chart with auto-scaling, zoom, pan, and home controls
- Live data table showing current value, min, max, and status per tag
- Pause/resume display updates while data continues collecting in the background
- Rolling time window with horizontal scrollbar for history navigation
- Snap-to-live button to jump back to the latest data
- **Unlimited data points by default** — trend for hours or days without losing data. An optional memory limit can be configured in Settings to cap storage when running unattended

### Chart Modes
- **Overlay mode** — all tags plotted on a shared axis
- **Isolated mode** — each tag gets its own subplot with synchronized pan/zoom across all subplots
- **Drag-reorder** — Ctrl+drag subplots to rearrange chart order in isolated mode

### Chart Customization
- **Trend Properties dialog** with tabs for X-Axis, Y-Axis, and Display settings
- Per-tag Y-axis scaling (auto or manual min/max)
- Configurable time span (30 sec to 1 hour)
- **Line Properties** — right-click any trace to change color, line width, and line style (solid, dashed, dotted, dash-dot)
- **Smart cursor** — crosshair with snap-to-nearest-point and value readout

### Data Export & Import
- **`.pytrend`** — JSON format with full metadata (PLC IP, controller type, tags, timestamps, sample rate)
- **`.csv`** — standard CSV with timestamp column and one column per tag
- **Import** `.pytrend` files for offline analysis with full chart interactivity
- View mode badge shows **LIVE**, **PAUSED**, **STOPPED**, or **HISTORICAL**

### Theme Support
- Dark and Light modes with SAS brand identity
- Theme toggle in Settings
- Logo automatically swaps between dark/light variants
- All settings persist between sessions

---

## Installation (Development)

### Prerequisites

- **Python 3.10** or newer — [Download Python](https://www.python.org/downloads/)
  - Check the **"Add Python to PATH"** checkbox during installation
- **pip** (included with Python)
- **Windows 10 or 11** (required for CustomTkinter and pylogix networking)

### Clone the Repository

```bash
git clone https://github.com/your-org/plc-trend-tool.git
cd plc-trend-tool
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Version | Purpose |
|---------|---------|---------|
| `customtkinter` | ≥ 5.2.0 | Modern themed UI framework |
| `pylogix` | ≥ 0.8.0 | Allen-Bradley PLC communication via Ethernet/IP |
| `matplotlib` | ≥ 3.7.0 | Chart rendering and interactive plotting |
| `Pillow` | ≥ 9.0.0 | Image handling for logos and icons |
| `pyinstaller` | ≥ 6.0.0 | Builds standalone Windows executable |

### Run from Source

```bash
python plc_trend_tool.py
```

---

## Building the Executable

The included build script handles PyInstaller configuration, asset bundling, and CustomTkinter packaging automatically.

### Build Steps

```bash
pip install -r requirements.txt
python build.py
```

The executable is created at:

```
dist\PLC_Trend_Tool.exe
```

Copy the `.exe` to a USB drive — it runs standalone on any Windows 10/11 machine with no installation.

### What the Build Script Does

1. Verifies all dependencies are installed
2. Extracts assets from the embedded `assets_data.py` if the `assets/` folder is incomplete
3. Generates `icon.ico` from `icon.png` if needed
4. Locates the CustomTkinter package directory for bundling
5. Runs PyInstaller in `--onefile --windowed` mode with all required hidden imports and data files
6. Reports the output path and file size

### Build Notes

- The resulting `.exe` is typically 20–30 MB (CustomTkinter + matplotlib)
- No external files or DLLs are needed — everything is bundled
- Assets are embedded in `assets_data.py` as base64, so the app is fully self-contained even without the `assets/` folder

---

## Project Structure

```
plc-trend-tool/
├── plc_trend_tool.py      # Main application (single-file)
├── assets_data.py         # Embedded assets (base64-encoded logos, icons)
├── build.py               # PyInstaller build script
├── requirements.txt       # Python dependencies
├── LICENSE                 # MIT License
├── README.md              # This file
├── .gitignore
└── assets/
    ├── logo.png           # SAS logo — white text (dark mode)
    ├── logo_light.png     # SAS logo — blue text (light mode)
    ├── icon.png           # App icon source (PNG)
    └── icon.ico           # App icon (Windows ICO)
```

---

## Usage Guide

### Connecting to a PLC

1. Open the app and go to the **PLC Connection** view
2. Enter the PLC's IP address (e.g., `192.168.1.10`)
3. Select the controller type (ControlLogix, CompactLogix, or Micro800)
4. Set the processor slot (usually `0` for CompactLogix/Micro800)
5. Click **Connect**

Once connected, the app automatically fetches the tag list and opens the trend view with the tag panel visible.

### Selecting Tags and Trending

1. Browse or search for tags in the left panel
2. Click tags to select them — the chart updates immediately with empty axes as a preview
3. Adjust the sample rate from the toolbar dropdown
4. Click **▶ Start Trend** to begin data collection
5. Tags can be added or removed while the trend is running — new tags start collecting on the next poll cycle (historical data won't exist for newly added tags)

### Chart Interaction

- **Pan** — click the pan tool (✥) in the chart toolbar, then click-drag on the chart
- **Zoom** — click the zoom tool then drag a rectangle to zoom into
- **Home** — click the home button to reset the view
- **Right-click** — access line properties and chart options from the context menu
- **Ctrl+Drag** (isolated mode) — reorder subplots by dragging them up or down

### Exporting Data

- Click **`.pytrend`** to save a JSON file with full metadata for later import
- Click **`CSV`** to save a standard CSV file compatible with Excel or other tools
- Click **Import** to load a previously saved `.pytrend` file for offline analysis

### Memory Management

By default the app collects data with no point limit — you can trend for as long as needed. If you plan to leave the app running unattended for extended periods, you can set a maximum data point limit in **Settings → Data Storage** to cap memory usage. Options range from 100,000 points (~50 MB) up to 5,000,000 points (~2.5 GB), or Unlimited.

---

## Troubleshooting

**Can't connect to PLC**
- Verify the IP address is correct and the PLC is powered on
- Ensure your PC is on the same subnet (e.g., PLC: `192.168.1.10`, PC: `192.168.1.x`)
- Check that the PLC's Ethernet module is configured and has a valid IP
- Try pinging the PLC from a command prompt: `ping 192.168.1.10`

**Tags show "Path segment error"**
- Verify the processor slot number — usually `0` for CompactLogix, check the physical chassis slot for ControlLogix

**"ModuleNotFoundError" when running from source**
- Run `pip install -r requirements.txt` to install all dependencies
- Verify Python is version 3.10 or newer: `python --version`

**Executable won't start or crashes immediately**
- Run from a command prompt to see error output: `PLC_Trend_Tool.exe`
- Ensure you're on Windows 10 or 11
- Try rebuilding with `python build.py`

**Chart shows black space or doesn't resize properly**
- Try clicking the Home button in the chart toolbar
- Toggle the tag panel off and on to force a layout refresh

---

## License

This project is licensed under the [MIT License](LICENSE) — free to use, modify, and distribute.

## Dependencies & Acknowledgments

- [pylogix](https://github.com/dmroeder/pylogix) — Allen-Bradley PLC communication
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — Modern tkinter UI framework
- [matplotlib](https://matplotlib.org/) — Scientific plotting library
- [Pillow](https://python-pillow.org/) — Python Imaging Library
- [PyInstaller](https://pyinstaller.org/) — Executable packaging

---

*Southern Automation Solutions — 111 Hemlock St. Ste A, Valdosta, GA 31601*
