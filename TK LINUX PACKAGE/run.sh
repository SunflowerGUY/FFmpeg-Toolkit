#!/usr/bin/env bash
# Starts FFmpeg Toolkit with the Python environment that install.sh created.
# Always runs the newest ffmpeg_toolkit_v*.py in this folder, so a new version
# only needs its .py file dropped in here.

APP_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$APP_DIR"

SCRIPT="$(ls ffmpeg_toolkit_v*.py 2>/dev/null | sort -V | tail -n 1)"
if [ -z "$SCRIPT" ]; then
    echo "No ffmpeg_toolkit_v*.py found in $APP_DIR" >&2
    exit 1
fi
if [ ! -x .venv/bin/python ]; then
    echo "Not installed yet. Run:  bash install.sh" >&2
    exit 1
fi

# Started from the menu or desktop there's no terminal to show errors, so keep
# them in a log file instead (handy for bug reports).
if [ -t 1 ]; then
    exec .venv/bin/python "$SCRIPT" "$@"
else
    LOG="$HOME/.cache/ffmpeg-toolkit.log"
    mkdir -p "$(dirname "$LOG")"
    printf '\n===== %s  %s =====\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$SCRIPT" >> "$LOG"
    exec .venv/bin/python "$SCRIPT" "$@" >> "$LOG" 2>&1
fi
