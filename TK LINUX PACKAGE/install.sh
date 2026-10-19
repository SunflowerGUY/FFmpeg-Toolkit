#!/usr/bin/env bash
# FFmpeg Toolkit -- Linux installer (Linux Mint, Ubuntu, Debian and their relatives).
#
# Run it from this folder with:   bash install.sh
#
# What it does:
#   1. Installs ffmpeg (with ffprobe and ffplay) and Python's window toolkit
#      from your distribution, using apt (asks for your password).
#   2. Creates a private Python environment in this folder (.venv) with the two
#      add-ons the app uses, CustomTkinter and Pillow. Newer Mint/Ubuntu versions
#      don't allow pip to install into the system Python, so this keeps it tidy.
#   3. Adds "FFmpeg Toolkit" to your applications menu (and a desktop icon).
#
# Safe to run again: it just refreshes everything.

set -euo pipefail

APP_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$APP_DIR"

say() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This installer uses apt (Mint, Ubuntu, Debian)."
    echo "On other Linux versions, install these yourself, then run this script again:"
    echo "  ffmpeg, python3, python3-tk, python3-venv"
    exit 1
fi

say "Installing ffmpeg and Python's window toolkit (your password may be needed)"
sudo apt-get update
sudo apt-get install -y ffmpeg python3 python3-tk python3-venv fonts-dejavu-core

say "Creating the app's Python environment in: $APP_DIR/.venv"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --upgrade customtkinter pillow tkinterdnd2

chmod +x run.sh

say "Adding FFmpeg Toolkit to the applications menu"
# Install the icon under its own name in the icon theme. The menu refers to it
# by that name, not by a file path: FFmpeg Core Tools' package also has a
# "LINUX PACKAGE/app_icon.png" in older versions, and the desktop caches icons
# by path. The file is named tk_app_icon.png so the two packages can even
# share a folder without one icon overwriting the other.
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$ICON_DIR"
cp -f tk_app_icon.png "$ICON_DIR/ffmpeg-toolkit.png"
touch "$HOME/.local/share/icons/hicolor"
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

DESKTOP_ENTRY="[Desktop Entry]
Type=Application
Name=FFmpeg Toolkit
Comment=Convert, fix and inspect video and audio files with ffmpeg
Exec=\"$APP_DIR/run.sh\"
Icon=ffmpeg-toolkit
Terminal=false
Categories=AudioVideo;Video;Audio;
StartupNotify=true
StartupWMClass=Ffmpeg-toolkit"

MENU_DIR="$HOME/.local/share/applications"
mkdir -p "$MENU_DIR"
printf '%s\n' "$DESKTOP_ENTRY" > "$MENU_DIR/ffmpeg-toolkit.desktop"
chmod +x "$MENU_DIR/ffmpeg-toolkit.desktop"
update-desktop-database "$MENU_DIR" >/dev/null 2>&1 || true

DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
    printf '%s\n' "$DESKTOP_ENTRY" > "$DESKTOP_DIR/ffmpeg-toolkit.desktop"
    chmod +x "$DESKTOP_DIR/ffmpeg-toolkit.desktop"
    # Mint/Ubuntu only launch desktop icons marked as trusted.
    gio set "$DESKTOP_DIR/ffmpeg-toolkit.desktop" metadata::trusted true >/dev/null 2>&1 || true
fi

say "Checking the install"
ffmpeg -hide_banner -version | head -n 1
.venv/bin/python -c "import tkinter, customtkinter, PIL; print('Python add-ons OK (Tk', tkinter.TkVersion, ')')"
.venv/bin/python -c "import tkinterdnd2" 2>/dev/null && echo "tkinterdnd2 OK (drag and drop)" || echo "tkinterdnd2 missing: everything works except dropping files on the input boxes"

say "Done! Start FFmpeg Toolkit from the applications menu, the desktop icon, or:  ./run.sh"
