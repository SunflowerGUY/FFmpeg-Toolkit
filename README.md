# FFmpeg Toolkit 🎬🔧

A Vibe Coded, feature-rich, dark-themed desktop GUI for [FFmpeg](https://ffmpeg.org/) built with Python and CustomTkinter.  
Designed for content creators who work with Audio Editors, and Video Editors such as [DaVinci Resolve](https://www.blackmagicdesign.com/products/davinciresolve) — fix, convert, inspect and process video files without touching the command line.

---

## 📸 Screenshots

**Splash Screen**  
![Splash Screen](https://customer-assets-lqy194kg.emergentagent.net/wingman/81f10f81-6deb-4b51-8f1e-8ec1c413df5e/attachments/ce6ba3c9640340aab0d69c3edad7f063_image.png)

**Main Interface — v3.0 with grouped sidebar**  
![Main Interface](https://customer-assets-lqy194kg.emergentagent.net/wingman/81f10f81-6deb-4b51-8f1e-8ec1c413df5e/attachments/c52dc08e55e446308d4ca859d4ee73db_image.png)

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

<details>
<summary>🐧 <strong>Linux Installation Guide (click to expand)</strong></summary>

### Linux Prerequisites
First, make sure FFmpeg and Python are installed:
```bash
sudo apt update
sudo apt install python3 python3-venv ffmpeg
```

---

### Linux Step 1 — Get the files
Download `ffmpeg_toolkit.py` from this repository and place it in a folder of your choice:
```bash
mkdir ~/FFmpeg-Toolkit
cd ~/FFmpeg-Toolkit
# copy or download ffmpeg_toolkit.py into this folder
```

---

### Linux Step 2 — Create a virtual environment
```bash
python3 -m venv ~/ffmpeg-build-env
```
> 💡 A virtual environment is an isolated Python workspace — it keeps your project's packages separate from the rest of your system. You only need to create it once.

---

### Linux Step 3 — Activate the virtual environment
```bash
source ~/ffmpeg-build-env/bin/activate
```
> Your terminal prompt will change to show `(ffmpeg-build-env)` — this confirms it is active.

---

### Linux Step 4 — Install required packages
```bash
pip install customtkinter Pillow pyinstaller
```

---

### Linux Step 5 — Navigate to your app folder
```bash
cd ~/FFmpeg-Toolkit
```
> ⚠️ You must be inside the folder containing `ffmpeg_toolkit.py` before running the build command.

---

### Linux Step 6 — Build the executable
```bash
python -m PyInstaller --onefile --windowed --name FFmpeg_Toolkit --collect-data customtkinter ffmpeg_toolkit.py
```
> This may take a minute or two. When complete, your executable will be at `dist/FFmpeg_Toolkit`.

---

### Linux Step 7 — Link FFmpeg
```bash
ln -s $(which ffmpeg) ~/FFmpeg-Toolkit/dist/ffmpeg.exe
```
> This creates a shortcut so the app can find FFmpeg in the same folder as the executable.

---

### Linux Step 8 — Run the app
```bash
~/FFmpeg-Toolkit/dist/FFmpeg_Toolkit
```
Or double-click `FFmpeg_Toolkit` in your file manager.

---

> **Next time you want to run it** — just launch the executable directly. No need to repeat the build steps.

</details>

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
