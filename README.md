# FFmpeg Toolkit 🎬🔧

A feature-rich, dark-themed desktop GUI for [FFmpeg](https://ffmpeg.org/) built with Python and CustomTkinter.  
Designed for video editors and content creators who work with [DaVinci Resolve](https://www.blackmagicdesign.com/products/davinciresolve) and need a fast, no-fuss way to fix, convert, and inspect video files — without touching the command line.

---

## ✨ Features

| Tab | Description |
|-----|-------------|
| **Quick Fix** | Remux video into a new container — copy all streams, no re-encode. First fix for files that won't import into DaVinci Resolve. |
| **Stubborn Fix** | Same as Quick Fix but re-encodes audio to AAC 192k. Fixes incompatible audio codecs. |
| **Fix Timestamps** | Regenerates corrupt/missing presentation timestamps (`-fflags +genpts`). Fixes stuttering or freezing footage. |
| **Inspect File** | Displays all stream info (codec, resolution, bitrate, audio format) without modifying the file. |
| **Proxy Creator** | Creates a lightweight lower-resolution copy for smooth editing. Resolve switches back to original at export. |
| **ProRes Export** | Converts to Apple ProRes (LT / 422 / HQ / 4444) — DaVinci Resolve's preferred ingest format. |
| **Extract Audio** | Pulls the audio track as WAV (uncompressed) or AAC. |
| **Strip Audio** | Removes all audio tracks, keeping video only. |
| **Trim Clip** | Fast lossless trim by start time + duration — no re-encode. |
| **Still Frame** | Exports a single frame at any timecode as PNG or JPEG. |
| **Custom Command** | Build your own FFmpeg command with a checkbox builder, or type/paste directly. |
| **Settings** | Set a default output folder and remember last-used input folder. |

---

## 🖥️ Requirements

- **Windows** (tested on Windows 10/11)
- **Python 3.10+** (only needed to build the `.exe`)
- **FFmpeg** — place `ffmpeg.exe` in the same folder as the app

> Download a static FFmpeg build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)

---

## 🚀 Quick Start

### Option A — Run from source
```bash
pip install customtkinter Pillow
python ffmpeg_toolkit.py
```

### Option B — Build a standalone `.exe`
1. Place `ffmpeg.exe` in the project folder
2. Double-click `build.bat`
3. Find `FFmpeg_Toolkit.exe` in the `dist/` folder
4. Copy `FFmpeg_Toolkit.exe` + `ffmpeg.exe` anywhere — no installation needed

---

## 📁 File Structure

```
FFmpeg-Toolkit/
├── ffmpeg_toolkit.py   # Main application
├── build.bat           # PyInstaller build script (Windows)
├── app_icon.ico        # Application icon
├── README.md           # This file
└── requirements.txt    # Python dependencies
```

---

## 🔧 Built With

- [Python](https://www.python.org/)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — modern dark-themed UI
- [Pillow](https://python-pillow.org/) — image handling
- [FFmpeg](https://ffmpeg.org/) — the powerhouse underneath

---

## 📄 License

MIT License — free to use, modify and distribute.

---

## 👨‍💻 Credits

**Developed by Adrian Newington**  
[github.com/SunflowerGUY](https://github.com/SunflowerGUY)

> Built to solve real-world DaVinci Resolve import headaches — and grown into a full FFmpeg toolbox.
