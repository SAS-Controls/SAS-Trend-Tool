#!/usr/bin/env python3
"""
PLC Trend Tool — Build Script
Creates a standalone Windows executable using PyInstaller.

Usage:
    python build.py

Output:
    dist/PLC_Trend_Tool.exe
"""

import os
import sys
import subprocess
import shutil

# ── Configuration ────────────────────────────────────────────────────────────
APP_NAME = "PLC_Trend_Tool"
MAIN_SCRIPT = "plc_trend_tool.py"
ICON_FILE = os.path.join("assets", "icon.ico")
ICON_PNG = os.path.join("assets", "icon.png")

BUNDLE_FILES = [
    ("assets/logo.png", "assets"),
    ("assets/logo_light.png", "assets"),
    ("assets/icon.png", "assets"),
    ("assets/icon.ico", "assets"),
    ("assets_data.py", "."),
]

HIDDEN_IMPORTS = [
    "customtkinter",
    "pylogix",
    "PIL._tkinter_finder",
    "matplotlib.backends.backend_tkagg",
    "assets_data",
]

EXCLUDES = [
    "scipy", "numpy.testing", "pandas", "pytest",
    "notebook", "IPython", "sphinx",
]


def find_customtkinter_path():
    """Find customtkinter package directory for bundling."""
    try:
        import customtkinter
        return os.path.dirname(customtkinter.__file__)
    except ImportError:
        return None


def create_icon_from_png():
    """Create .ico from .png if ico doesn't exist."""
    if os.path.exists(ICON_FILE):
        return ICON_FILE
    if not os.path.exists(ICON_PNG):
        return None
    try:
        from PIL import Image
        img = Image.open(ICON_PNG).convert("RGBA")
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        icons = [img.resize(s, Image.LANCZOS) for s in sizes]
        icons[0].save(ICON_FILE, format="ICO", sizes=sizes, append_images=icons[1:])
        print(f"  Created {ICON_FILE} from {ICON_PNG}")
        return ICON_FILE
    except Exception as e:
        print(f"  Warning: Could not create .ico: {e}")
        return None


def build():
    print(f"\n{'='*60}")
    print(f"  Building {APP_NAME}")
    print(f"{'='*60}\n")

    # Check main script exists
    if not os.path.exists(MAIN_SCRIPT):
        print(f"ERROR: {MAIN_SCRIPT} not found!")
        sys.exit(1)

    # Check dependencies
    print("[1/4] Checking dependencies...")
    pkg_imports = {
        "customtkinter": "customtkinter",
        "pylogix": "pylogix",
        "matplotlib": "matplotlib",
        "Pillow": "PIL",
        "pyinstaller": "PyInstaller",
    }
    for pkg_name, import_name in pkg_imports.items():
        try:
            __import__(import_name)
            print(f"  ✓ {pkg_name}")
        except ImportError:
            print(f"  ✗ {pkg_name} — install with: pip install {pkg_name}")
            sys.exit(1)

    # Create icon if needed
    print("\n[2/4] Preparing assets...")
    
    # Auto-extract assets from assets_data.py if folder is missing
    expected_assets = ["icon.ico", "icon.png", "logo.png", "logo_light.png"]
    assets_dir = "assets"
    if not all(os.path.exists(os.path.join(assets_dir, f)) for f in expected_assets):
        print("  Assets folder incomplete — extracting from assets_data.py...")
        try:
            import base64
            from assets_data import ASSETS
            os.makedirs(assets_dir, exist_ok=True)
            for filename, b64_parts in ASSETS.items():
                filepath = os.path.join(assets_dir, filename)
                if not os.path.exists(filepath):
                    data = base64.b64decode("".join(b64_parts))
                    with open(filepath, "wb") as f:
                        f.write(data)
                    print(f"    Extracted: {filename} ({len(data):,} bytes)")
        except ImportError:
            print("  WARNING: assets_data.py not found — icons may be missing")
    
    icon_path = create_icon_from_png()

    # Find customtkinter for bundling
    ctk_path = find_customtkinter_path()
    if ctk_path:
        print(f"  Found customtkinter at: {ctk_path}")

    # Build PyInstaller command
    print("\n[3/4] Building executable...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        f"--name={APP_NAME}",
        "--clean",
    ]

    # Add icon
    if icon_path and os.path.exists(icon_path):
        cmd.append(f"--icon={icon_path}")

    # Add assets
    sep = ";" if sys.platform == "win32" else ":"
    for src, dst in BUNDLE_FILES:
        if os.path.exists(src):
            cmd.append(f"--add-data={src}{sep}{dst}")
            print(f"  + {src}")

    # Add customtkinter package data
    if ctk_path:
        cmd.append(f"--add-data={ctk_path}{sep}customtkinter")

    # Hidden imports
    for imp in HIDDEN_IMPORTS:
        cmd.append(f"--hidden-import={imp}")

    # Excludes
    for exc in EXCLUDES:
        cmd.append(f"--exclude-module={exc}")

    cmd.append(MAIN_SCRIPT)

    print(f"\n  Running: {' '.join(cmd[:5])}...")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print(f"\nERROR: Build failed with code {result.returncode}")
        sys.exit(1)

    # Verify output
    print("\n[4/4] Verifying build...")
    exe_path = os.path.join("dist", f"{APP_NAME}.exe")
    if not os.path.exists(exe_path):
        # Check without .exe (Linux)
        exe_path = os.path.join("dist", APP_NAME)

    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n{'='*60}")
        print(f"  BUILD SUCCESS")
        print(f"  Output: {os.path.abspath(exe_path)}")
        print(f"  Size:   {size_mb:.1f} MB")
        print(f"{'='*60}\n")
    else:
        print("\nWARNING: Build completed but exe not found at expected path.")
        print("Check the dist/ folder.")


if __name__ == "__main__":
    build()
