# FFmpeg Toolkit 🎬🔧

A feature-rich, dark-themed desktop GUI for [FFmpeg](https://ffmpeg.org/) built with Python and CustomTkinter.  
Designed for video editors and content creators who work with [DaVinci Resolve](https://www.blackmagicdesign.com/products/davinciresolve) — fix, convert, inspect and process video files without touching the command line.

---

## 📸 Screenshots

**Splash Screen**  
![Splash Screen](https://customer-assets-lqy194kg.emergentagent.net/wingman/81f10f81-6deb-4b51-8f1e-8ec1c413df5e/attachments/dff13501513d49eab59c1b2d1a3878e1_FF%20Toolbox%20v2%20Screen%20Grab%201.jpg)

**Main Interface**  
![Main Interface](https://customer-assets-lqy194kg.emergentagent.net/wingman/81f10f81-6deb-4b51-8f1e-8ec1c413df5e/attachments/46618b75f8b24c7190b3338d46e20384_FF%20Toolbox%20v2%20Screen%20Grab%202.jpg)

---

## ✨ Features

### 🎬 Video
| Tool | Description |
|------|-------------|
| **Quick Fix** | Remux video into a new container — copy all streams, no re-encode. First fix for files that won't import into DaVinci Resolve. |
| **Stubborn Fix** | Same as Quick Fix but re-encodes audio to AAC 192k. Fixes incompatible audio codecs. |
| **Fix Timestamps** | Regenerates corrupt/missing presentation timestamps (`-fflags +genpts`). Fixes stuttering or freezing footage. |
| **Proxy Creator** | Creates a lightweight lower-resolution copy for smooth editing. Resolve switches back to the original at export — no quality loss. |
| **ProRes Export** | Converts to Apple ProRes (LT / 422 / HQ / 4444) — DaVinci Resolve's preferred ingest format. |
| **Trim Clip** | Fast lossless trim by start time + duration — no re-encode. |
| **Still Frame** | Exports a single frame at any timecode as PNG or JPEG. |

### 🎵 Audio
| Tool | Description |
|------|-------------|
| **Extract Audio** | Pulls the audio track as WAV (uncompressed) or AAC. |
| **Strip Audio** | Removes all audio tracks, keeping video only. |
| **Audio Accessibility** | Normalises or compresses audio dynamic range. Supports **Dynamic Normaliser** (`dynaudnorm`) and **Loudness Compression** with selectable target (-14 LUFS Spotify/YouTube, -16 LUFS Apple Music, -23 LUFS Broadcast, -27 LUFS Netflix). |
| **Batch Audio Convert** | Converts all audio files of a chosen format in a folder to a new format (WAV, MP3, FLAC, M4A, OGG, AC3). Auto-scans on folder select. MP3 output includes bitrate and VBR quality options. Saves results to a `CONVERTED/` subfolder. |

### ⚙️ Tools
| Tool | Description |
|------|-------------|
| **Custom Command** | Build your own FFmpeg command using a checkbox builder, or type/paste any command directly. |
| **Inspect File** | Displays all stream info (codec, resolution, bitrate, audio format) without modifying the file. |
| **Settings** | Set a default output folder and remember last-used input folder. |

---

## 🖥️ Requirements

- **Windows** (tested on Windows 10/11) or **Linux**
- **Python 3.10+** (only needed to build the executable)
- **FFmpeg** — place `ffmpeg.exe` (Windows) or `ffmpeg` (Linux) in the same folder as the app

> Download a static FFmpeg build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)

---

## 🚀 Quick Start

### Option A — Run from source
```bash
pip install customtkinter Pillow
python ffmpeg_toolkit.py
```

### Option B — Build a standalone executable (Windows)
1. Place `ffmpeg.exe` in the project folder
2. Double-click `build.bat`
3. Find `FFmpeg_Toolkit.exe` in the `dist/` folder
4. Copy `FFmpeg_Toolkit.exe` + `ffmpeg.exe` anywhere — no installation needed

### Option C — Build on Linux (e.g. Linux Mint)
```bash
python3 -m venv ~/ffmpeg-build-env
source ~/ffmpeg-build-env/bin/activate
pip install customtkinter Pillow pyinstaller
python -m PyInstaller --onefile --windowed --name FFmpeg_Toolkit --collect-data customtkinter ffmpeg_toolkit.py
```

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

**Developed by Adrian Newington** | **Coding by [Emergent.ai](https://emergent.ai)**  
[github.com/SunflowerGUY](https://github.com/SunflowerGUY)

> Built to solve real-world DaVinci Resolve import headaches — and grown into a full FFmpeg toolbox.

---

## 📋 Changelog

**v3.0** — 29 August 2026
- Batch Audio Convert: folder-based bulk audio conversion (WAV/MP3/FLAC/M4A/OGG/AC3)
- Audio Accessibility: selectable Target Loudness (-14/-16/-23/-27 LUFS)
- Sidebar reorganised into VIDEO / AUDIO / TOOLS groups
- Fixed duplicate file listing in Batch Audio Convert
- Fixed CMD window flash on batch conversions (Windows)

**v2.0** — 28 August 2026
- Left sidebar navigation replacing horizontal tab bar
- Audio Accessibility tab (Dynamic Normaliser + Loudness Compression)
- New FF Toolbox icon, mini icon in title bar
- Credits: Developed by Adrian Newington | Coding by Emergent.ai

**v1.0** — 27 August 2026
- Initial release with 12 tools
