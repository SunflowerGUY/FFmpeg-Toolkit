# Changelog

## Version 4.2 — 30 August 2026

**Added**
- Status dot in the top bar now blinks red when ffmpeg can't be resolved, instead of showing a static color, making the problem harder to miss at a glance.
- All sidebar tools are automatically disabled when ffmpeg isn't found, except **Settings** — the only tab that doesn't depend on ffmpeg being present. The app now opens directly on Settings in this state instead of a non-functional Quick Fix screen.
- When ffmpeg is found on the system PATH (rather than next to the app), the user is now prompted after the welcome screen:
  > *"Local copy not found. Alternate copy found at `<path>`, version `<version>`. Do you wish to set & employ this alternate copy?"*
  - **Yes** — pins that copy into Settings for all future launches.
  - **No** — uses it for the current session only; the same path won't be asked about again on subsequent launches.

**Changed**
- FFmpeg Location field in Settings now auto-populates when ffmpeg is detected next to the app (previously stayed blank even though ffmpeg was working).
- FFmpeg resolution order updated: app folder ? a path already pinned in Settings ? system PATH. A previously confirmed/pinned copy now takes priority over a fresh PATH lookup, so a deliberate choice won't get silently overridden if another install shows up on PATH later.
- Sidebar/tool state and the Settings display now update live the moment ffmpeg is resolved or re-resolved (e.g. right after fixing the path in Settings) — no restart required.

**Fixed**
- The welcome-splash warning about ffmpeg only appears when ffmpeg is genuinely not found, rather than unconditionally on every launch.

---
## v4 — 30 August 2026
- Code efficiency improvements and refactoring (no functional changes)

## v3.0.1 — 29 August 2026
- Fixed Batch Audio Convert: Bitrate/Quality row now stays in correct position when switching output formats or revisiting the panel

## v3.0 — 29 August 2026
- Batch Audio Convert: folder-based bulk audio conversion (WAV/MP3/FLAC/M4A/OGG/AC3)
- Audio Accessibility: selectable Target Loudness (-14/-16/-23/-27 LUFS)
- Sidebar reorganised into VIDEO / AUDIO / TOOLS groups
- Fixed duplicate file listing in Batch Audio Convert
- Fixed CMD window flash on batch conversions (Windows)

## v2.0 — 28 August 2026
- Left sidebar navigation replacing horizontal tab bar
- Audio Accessibility tab (Dynamic Normaliser + Loudness Compression)
- New FF Toolbox icon, mini icon in title bar
- Credits: Developed by Adrian Newington | Coding by Emergent.ai

## v1.0 — 27 August 2026
- Initial release with 12 tools
