import os
import sys
import io
import re
import json
import base64
import shutil
import pathlib
import subprocess
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image as PilImage


APP_VERSION = "4.2"
BUILD_DATE = "30 August 2026"

# ffmpeg binary name differs by platform; shutil.which() also handles
# PATHEXT resolution on Windows, so "ffmpeg" alone is enough for that path.
FFMPEG_BINARY_NAME = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

# Shared file-type filters used across panels
VIDEO_FILTERS = [
    ("Video files", "*.mp4 *.mov *.mkv *.avi *.mxf *.m4v *.wmv"),
    ("All files", "*.*"),
]


class FFmpegToolkit(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FFmpeg Toolkit")

        icon_path = (
            pathlib.Path(sys.executable).parent / "app_icon.ico"
            if getattr(sys, "frozen", False)
            else pathlib.Path(__file__).parent / "app_icon.ico"
        )
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        self.geometry("1100x720")
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        if getattr(sys, "frozen", False):
            self._app_dir = os.path.dirname(sys.executable)
        else:
            self._app_dir = os.path.dirname(os.path.abspath(__file__))
        self._settings_path = os.path.join(self._app_dir, "settings.json")

        self._settings = self._load_settings()
        self._ffmpeg_path = self._resolve_ffmpeg_path()

        self._build_ui()

    # ------------------------------------------------------------------
    # ffmpeg location
    # ------------------------------------------------------------------

    def _resolve_ffmpeg_path(self):
        """Find ffmpeg by checking, in order:
        1. Next to the app (the original, still-supported behavior) --
           auto-pinned into Settings since it's unambiguous.
        2. A path already pinned in Settings -- either browsed to
           manually, or a PATH-found copy the user previously confirmed.
           This is checked before a fresh PATH lookup so an explicit
           choice sticks even if something else shows up on PATH later.
        3. The system PATH (covers a normal ffmpeg install via winget/
           Homebrew/apt/the official installer, on Windows or Linux).
           A *new* PATH find (not yet pinned or declined) is used for
           this session but flagged via self._pending_ffmpeg_confirm so
           the caller can ask the user whether to pin it.
        Returns the resolved path, or None if ffmpeg couldn't be found
        anywhere -- callers should prompt the user via Settings.
        """
        self._pending_ffmpeg_confirm = None

        same_folder = os.path.join(self._app_dir, FFMPEG_BINARY_NAME)
        if os.path.isfile(same_folder):
            if self._settings.get("ffmpeg_path") != same_folder:
                self._settings["ffmpeg_path"] = same_folder
                self._save_settings()
            return same_folder

        saved_path = self._settings.get("ffmpeg_path", "")
        if saved_path and os.path.isfile(saved_path):
            return saved_path

        on_path = shutil.which("ffmpeg")
        if on_path:
            declined = self._settings.get("ffmpeg_declined_paths", [])
            if on_path not in declined:
                self._pending_ffmpeg_confirm = on_path
            return on_path

        return None

    def _get_ffmpeg_version(self, path):
        """Run `ffmpeg -version` and pull out just the version token from
        the first line, for display in the pin-this-copy prompt."""
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                [path, "-version"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                startupinfo=startupinfo, universal_newlines=True,
                errors="replace", timeout=5,
            )
            first_line = result.stdout.splitlines()[0] if result.stdout else ""
            match = re.search(r"ffmpeg version (\S+)", first_line)
            return match.group(1) if match else "unknown"
        except Exception:
            return "unknown"

    def _maybe_prompt_alt_ffmpeg(self):
        """If startup found a not-yet-pinned copy of ffmpeg on PATH,
        ask whether to adopt it permanently. Runs once, after the
        welcome splash is dismissed so it isn't stacked behind it."""
        path = getattr(self, "_pending_ffmpeg_confirm", None)
        if not path:
            return
        self._pending_ffmpeg_confirm = None

        version = self._get_ffmpeg_version(path)
        message = (
            "Local copy not found.\n\n"
            f"Alternate copy found at:\n{path}\n\n"
            f"Version: {version}\n\n"
            "Do you wish to set & employ this alternate copy?"
        )
        accepted = messagebox.askyesno("FFmpeg Not Found Locally", message)

        declined = self._settings.get("ffmpeg_declined_paths", [])
        if accepted:
            self._settings["ffmpeg_path"] = path
            if path in declined:
                declined.remove(path)
                self._settings["ffmpeg_declined_paths"] = declined
        else:
            if path not in declined:
                declined.append(path)
                self._settings["ffmpeg_declined_paths"] = declined
        self._save_settings()

        self._set_ffmpeg_status(True)  # already in use either way this session
        self._refresh_settings_ffmpeg_display()

    def _refresh_settings_ffmpeg_display(self):
        """Sync the Settings tab's FFmpeg Location field + status line to
        the current self._settings/self._ffmpeg_path, e.g. after the
        pin-this-copy prompt is answered. No-op if Settings hasn't been
        built yet (widgets not created)."""
        entry = getattr(self, "_settings_ffmpeg_entry", None)
        status_label = getattr(self, "_settings_ffmpeg_status_label", None)
        if entry is None or status_label is None:
            return

        entry.delete(0, "end")
        if self._settings.get("ffmpeg_path"):
            entry.insert(0, self._settings["ffmpeg_path"])

        resolved = self._ffmpeg_path if (self._ffmpeg_path and os.path.isfile(self._ffmpeg_path)) else None
        status_label.configure(
            text=(f"Currently using: {resolved}" if resolved
                  else "Not found -- checked app folder, then system PATH, then this setting."),
            text_color="#888888" if resolved else "#e8a020",
        )

    def _set_ffmpeg_status(self, found):
        """Update the top-bar status dot/label and the sidebar's enabled
        state, starting or stopping the red blink depending on whether
        ffmpeg is currently resolved."""
        self._ffmpeg_ok = found
        if found:
            self._status_dot.configure(text_color="#2ecc71")
            self._status_label.configure(text="ffmpeg found")
        else:
            self._status_label.configure(text="ffmpeg not found -- set it in Settings")
            self._blink_status_dot()
        self._set_sidebar_enabled(found)

    def _set_sidebar_enabled(self, enabled):
        """Grey out every sidebar tool except Settings when ffmpeg isn't
        resolved -- every tab, including Custom Command, ultimately runs
        an ffmpeg invocation and would just fail anyway. Settings stays
        clickable always since it's the only way out of this state."""
        if not hasattr(self, "_nav_buttons"):
            return  # sidebar not built yet
        for name, btn in self._nav_buttons.items():
            if name == "Settings":
                continue
            btn.configure(state="normal" if enabled else "disabled")

    def _blink_status_dot(self):
        """Toggle the status dot between bright and dim red every 600ms.
        Self-terminates the next time it fires after ffmpeg is found --
        no separate stop call needed, _set_ffmpeg_status(True) is enough."""
        if getattr(self, "_ffmpeg_ok", False):
            return
        self._blink_on = not getattr(self, "_blink_on", False)
        self._status_dot.configure(text_color="#e74c3c" if self._blink_on else "#4a1410")
        self.after(600, self._blink_status_dot)

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _load_settings(self):
        defaults = {
            "default_output_folder": "",
            "remember_last_folder": True,
            "last_input_folder": "",
            "ffmpeg_path": "",
            "ffmpeg_declined_paths": [],
        }
        if os.path.isfile(self._settings_path):
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                defaults.update(data)
            except Exception:
                pass
        return defaults

    def _save_settings(self):
        try:
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception:
            pass

    def _get_output_dir(self, input_path):
        """Return the output directory based on settings."""
        if self._settings.get("default_output_folder") and os.path.isdir(
            self._settings["default_output_folder"]
        ):
            return self._settings["default_output_folder"]
        return os.path.dirname(input_path)

    def _get_initial_dir(self):
        """Return initial directory for file dialogs."""
        if self._settings.get("remember_last_folder") and self._settings.get(
            "last_input_folder"
        ):
            folder = self._settings["last_input_folder"]
            if os.path.isdir(folder):
                return folder
        return ""

    def _remember_folder(self, path):
        """Remember the folder of a selected file."""
        if self._settings.get("remember_last_folder") and path:
            self._settings["last_input_folder"] = os.path.dirname(path)
            self._save_settings()

    # ------------------------------------------------------------------
    # Main UI shell: top bar, sidebar nav, content panels, welcome splash
    # ------------------------------------------------------------------

    def _build_ui(self):
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=15, pady=(10, 5))

        self._add_title_icon(top_frame)

        title_label = ctk.CTkLabel(
            top_frame, text="FFmpeg Toolkit", font=ctk.CTkFont(size=22, weight="bold")
        )
        title_label.pack(side="left")

        ctk.CTkLabel(
            top_frame,
            text=f"v{APP_VERSION}  |  {BUILD_DATE}",
            font=ctk.CTkFont(size=11),
            text_color="#666666"
        ).pack(side="left", padx=(10, 0), pady=(4, 0))

        status_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        status_frame.pack(side="right")

        self._status_dot = ctk.CTkLabel(
            status_frame, text="\u25cf", font=ctk.CTkFont(size=14)
        )
        self._status_dot.pack(side="left", padx=(0, 5))

        self._status_label = ctk.CTkLabel(
            status_frame, text="", font=ctk.CTkFont(size=12)
        )
        self._status_label.pack(side="left")

        # ffmpeg status (dot + sidebar enable/disable) is set once the
        # sidebar nav buttons exist -- see the bottom of this method.

        # -- Sidebar + Content panel --------------------------------------
        body_frame = ctk.CTkFrame(self, fg_color="transparent")
        body_frame.pack(fill="both", expand=True, padx=0, pady=0)

        sidebar = ctk.CTkFrame(body_frame, width=190, corner_radius=0,
                               fg_color=["#1a1a1a", "#1a1a1a"])
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self._content_panel = ctk.CTkFrame(body_frame, fg_color="transparent")
        self._content_panel.pack(side="left", fill="both", expand=True, padx=0, pady=0)

        self._panels = {}
        self._nav_buttons = {}

        def _build_panel(name, build_fn):
            frame = ctk.CTkFrame(self._content_panel, fg_color="transparent")
            build_fn(frame)
            self._panels[name] = frame

        def _show_panel(name):
            for panel in self._panels.values():
                panel.pack_forget()
            self._panels[name].pack(fill="both", expand=True)
            for btn_name, btn in self._nav_buttons.items():
                if btn_name == name:
                    btn.configure(fg_color="#1f538d", text_color="white")
                else:
                    btn.configure(fg_color="transparent", text_color="#cccccc")

        self._show_panel = _show_panel

        # Declarative registry: (nav label, icon, panel builder)
        # This single list drives both panel construction and sidebar nav,
        # so adding a new tool only means adding one row here plus its
        # builder method -- no duplicated wiring required.
        self._tool_sections = [
            ("VIDEO", [
                ("Quick Fix",           "\U0001F527", lambda p: self._build_fix_tab(p, "quick")),
                ("Stubborn Fix",        "\U0001F528", lambda p: self._build_fix_tab(p, "stubborn")),
                ("Fix Timestamps",      "\u23F1",     self._build_fix_timestamps_tab),
                ("Proxy Creator",       "\U0001F4E6", self._build_proxy_tab),
                ("ProRes Export",       "\U0001F3AC", self._build_prores_tab),
                ("Trim Clip",           "\u2702\uFE0F", self._build_trim_clip_tab),
                ("Still Frame",         "\U0001F5BC", self._build_still_frame_tab),
            ]),
            ("AUDIO", [
                ("Extract Audio",       "\U0001F3B5", self._build_extract_audio_tab),
                ("Strip Audio",         "\U0001F507", self._build_strip_audio_tab),
                ("Audio Accessibility", "\u267F",     self._build_audio_accessibility_tab),
                ("Batch Audio Convert", "\U0001F4C2", self._build_batch_audio_tab),
            ]),
            ("TOOLS", [
                ("Custom Command",      "\u2328\uFE0F", self._build_custom_tab),
            ]),
        ]
        self._utility_items = [
            ("Settings",     "\u2699\uFE0F", self._build_settings_tab),
            ("Inspect File", "\U0001F50D", self._build_inspect_tab),
        ]

        for _, items in self._tool_sections:
            for name, _icon, builder in items:
                _build_panel(name, builder)
        for name, _icon, builder in self._utility_items:
            _build_panel(name, builder)

        # Sidebar header
        ctk.CTkLabel(sidebar, text="FFmpeg Toolkit",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#888888").pack(pady=(14, 6), padx=12, anchor="w")

        def _add_nav_button(name, icon):
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon}  {name}",
                font=ctk.CTkFont(size=12),
                anchor="w", width=190, height=34,
                corner_radius=0,
                fg_color="transparent",
                text_color="#cccccc",
                hover_color="#2a2a2a",
                command=lambda n=name: _show_panel(n)
            )
            btn.pack(fill="x")
            self._nav_buttons[name] = btn

        for section_label, items in self._tool_sections:
            ctk.CTkLabel(sidebar, text=section_label,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#555555", anchor="w").pack(
                         fill="x", padx=12, pady=(8, 1))
            for name, icon, _builder in items:
                _add_nav_button(name, icon)

        ctk.CTkLabel(sidebar, text="\u2500" * 22,
                     text_color="#333333",
                     font=ctk.CTkFont(size=9)).pack(pady=(6, 2), padx=8)

        for name, icon, _builder in self._utility_items:
            _add_nav_button(name, icon)

        ffmpeg_found = bool(self._ffmpeg_path) and os.path.isfile(self._ffmpeg_path)
        self._set_ffmpeg_status(ffmpeg_found)
        _show_panel("Quick Fix" if ffmpeg_found else "Settings")

        self._build_welcome_splash()

    def _add_title_icon(self, top_frame):
        """Small app icon shown next to the title bar text."""
        try:
            mini_data = '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'
            mini_pil = PilImage.open(io.BytesIO(base64.b64decode(mini_data)))
            mini_img = ctk.CTkImage(light_image=mini_pil, dark_image=mini_pil, size=(28, 28))
            ctk.CTkLabel(top_frame, image=mini_img, text="").pack(side="left", padx=(0, 6))
        except Exception:
            pass

    def _build_welcome_splash(self):
        """Full-window welcome overlay shown on launch, dismissed by any click."""
        welcome_image = None
        try:
            b64_data = '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AAAAAAAAAAEAOEJJTScQAAAAAAAKAAEAAAAAAAAAAjhCSU0D9QAAAAAASAAvZmYAAQBsZmYABgAAAAAAAQAvZmYAAQChmZoABgAAAAAAAQAyAAAAAQBaAAAABgAAAAAAAQA1AAAAAQAtAAAABgAAAAAAAThCSU0D+AAAAAAAcAAA/////////////////////////////wPoAAAAAP////////////////////////////8D6AAAAAD/////////////////////////////A+gAAAAA/////////////////////////////wPoAAA4QklNBAAAAAAAAAIACjhCSU0EAgAAAAAAHgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADhCSU0EMAAAAAAADwEBAQEBAQEBAQEBAQEBAQA4QklNBC0AAAAAAAYAAQAAABQ4QklNBAgAAAAAABAAAAABAAACQAAAAkAAAAAAOEJJTQQeAAAAAAAEAAAAADhCSU0EGgAAAAADUwAAAAYAAAAAAAAAAAAAAfQAAAH0AAAADwBGAEYAIABUAG8AbwBsAGIAbwB4ACAASQBjAG8AbgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAB9AAAAfQAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAQAAAAAAAG51bGwAAAACAAAABmJvdW5kc09iamMAAAABAAAAAAAAUmN0MQAAAAQAAAAAVG9wIGxvbmcAAAAAAAAAAExlZnRsb25nAAAAAAAAAABCdG9tbG9uZwAAAfQAAAAAUmdodGxvbmcAAAH0AAAABnNsaWNlc1ZsTHMAAAABT2JqYwAAAAEAAAAAAAVzbGljZQAAABIAAAAHc2xpY2VJRGxvbmcAAAAAAAAAB2dyb3VwSURsb25nAAAAAAAAAAZvcmlnaW5lbnVtAAAADEVTbGljZU9yaWdpbgAAAA1hdXRvR2VuZXJhdGVkAAAAAFR5cGVlbnVtAAAACkVTbGljZVR5cGUAAAAASW1nIAAAAAZib3VuZHNPYmpjAAAAAQAAAAAAAFJjdDEAAAAEAAAAAFRvcCBsb25nAAAAAAAAAABMZWZ0bG9uZwAAAAAAAAAAQnRvbWxvbmcAAAH0AAAAAFJnaHRsb25nAAAB9AAA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AAAAAFcAAAABAQAAAA8AQQBkAG8AYgBlACAAUABoAG8AdABvAHMAaABvAHAAAAAUAEEAZABvAGIAZQAgAFAAaABvAHQAbwBzAGgAbwBwACAAMgAwADIAMQAAAAEAOEJJTQQGAAAAAAAHAAEAAAABAQD/4RJiaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLwA8P3hwYWNrZXQgYmVnaW49Iu+7vyIgaWQ9Ilc1TTBNcENlaGlIenJlU3pOVGN6a2M5ZCI/PiA8eDp4bXBtZXRhIHhtbG5zOng9ImFkb2JlOm5zOm1ldGEvIiB4OnhtcHRrPSJBZG9iZSBYTVAgQ29yZSA2LjAtYzAwMyA3OS4xNjQ1MjcsIDIwMjAvMTAvMTUtMTc6NDg6MzIgICAgICAgICI+IDxyZGY6UkRGIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyI+IDxyZGY6RGVzY3JpcHRpb24gcmRmOmFib3V0PSIiIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIgeG1sbnM6cGhvdG9zaG9wPSJodHRwOi8vbnMuYWRvYmUuY29tL3Bob3Rvc2hvcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdEV2dD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlRXZlbnQjIiB4bWxuczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgMjIuMSAoV2luZG93cykiIHhtcDpDcmVhdGVEYXRlPSIyMDI2LTA4LTI2VDE1OjM4OjU2KzEwOjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDI2LTA4LTI4VDE0OjM0OjQ0KzEwOjAwIiB4bXA6TW9kaWZ5RGF0ZT0iMjAyNi0wOC0yOFQxNDozNDo0NCsxMDowMCIgcGhvdG9zaG9wOkNvbG9yTW9kZT0iMyIgZGM6Zm9ybWF0PSJpbWFnZS9qcGVnIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjlkZDcwZjQ3LWY0ZDAtYTI0My05MjBkLTA3YWZjYmE5OTExNyIgeG1wTU06RG9jdW1lbnRJRD0iYWRvYmU6ZG9jaWQ6cGhvdG9zaG9wOjU5OTk4ZmNkLWYzMWQtYzk0NC05MTQyLTE5MmVhZDFhMTNjOSIgeG1wTU06T3JpZ2luYWxEb2N1bWVudElEPSJ4bXAuZGlkOjA0MmM3ZGM0LTA4MDYtODQ0MC05N2E4LTk1OTIwZTYxNWFmOSI+IDxwaG90b3Nob3A6VGV4dExheWVycz4gPHJkZjpCYWc+IDxyZGY6bGkgcGhvdG9zaG9wOkxheWVyTmFtZT0iUCIgcGhvdG9zaG9wOkxheWVyVGV4dD0iUCIvPiA8cmRmOmxpIHBob3Rvc2hvcDpMYXllck5hbWU9IkoiIHBob3Rvc2hvcDpMYXllclRleHQ9IkoiLz4gPHJkZjpsaSBwaG90b3Nob3A6TGF5ZXJOYW1lPSJmZiIgcGhvdG9zaG9wOkxheWVyVGV4dD0iZmYiLz4gPC9yZGY6QmFnPiA8L3Bob3Rvc2hvcDpUZXh0TGF5ZXJzPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjA0MmM3ZGM0LTA4MDYtODQ0MC05N2E4LTk1OTIwZTYxNWFmOSIgc3RFdnQ6d2hlbj0iMjAyNi0wOC0yNlQxNTozODo1NisxMDowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDIyLjEgKFdpbmRvd3MpIi8+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJzYXZlZCIgc3RFdnQ6aW5zdGFuY2VJRD0ieG1wLmlpZDoyOTE1NzczNy1kYjExLTFjNDYtODA1Zi1kODA1OTk5MmEyYTQiIHN0RXZ0OndoZW49IjIwMjYtMDgtMjdUMTU6MDI6NTUrMTA6MDAiIHN0RXZ0OnNvZnR3YXJlQWdlbnQ9IkFkb2JlIFBob3Rvc2hvcCAyMi4xIChXaW5kb3dzKSIgc3RFdnQ6Y2hhbmdlZD0iLyIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiIHN0RXZ0Omluc3RhbmNlSUQ9InhtcC5paWQ6NmFiMzAxZDctZDJhYi0zNDRmLWE5YWItM2E3ZTM5YmQ3Yjk5IiBzdEV2dDp3aGVuPSIyMDI2LTA4LTI4VDE0OjM0OjQ0KzEwOjAwIiBzdEV2dDpzb2Z0d2FyZUFnZW50PSJBZG9iZSBQaG90b3Nob3AgMjIuMSAoV2luZG93cykiIHN0RXZ0OmNoYW5nZWQ9Ii8iLz4gPHJkZjpsaSBzdEV2dDphY3Rpb249ImNvbnZlcnRlZCIgc3RFdnQ6cGFyYW1ldGVycz0iZnJvbSBhcHBsaWNhdGlvbi92bmQuYWRvYmUucGhvdG9zaG9wIHRvIGltYWdlL2pwZWciLz4gPHJkZjpsaSBzdEV2dDphY3Rpb249ImRlcml2ZWQiIHN0RXZ0OnBhcmFtZXRlcnM9ImNvbnZlcnRlZCBmcm9tIGFwcGxpY2F0aW9uL3ZuZC5hZG9iZS5waG90b3Nob3AgdG8gaW1hZ2UvanBlZyIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiIHN0RXZ0Omluc3RhbmNlSUQ9InhtcC5paWQ6OWRkNzBmNDctZjRkMC1hMjQzLTkyMGQtMDdhZmNiYTk5MTE3IiBzdEV2dDp3aGVuPSIyMDI2LTA4LTI4VDE0OjM0OjQ0KzEwOjAwIiBzdEV2dDpzb2Z0d2FyZUFnZW50PSJBZG9iZSBQaG90b3Nob3AgMjIuMSAoV2luZG93cykiIHN0RXZ0OmNoYW5nZWQ9Ii8iLz4gPC9yZGY6U2VxPiA8L3htcE1NOkhpc3Rvcnk+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOjZhYjMwMWQ3LWQyYWItMzQ0Zi1hOWFiLTNhN2UzOWJkN2I5OSIgc3RSZWY6ZG9jdW1lbnRJRD0iYWRvYmU6ZG9jaWQ6cGhvdG9zaG9wOmE2ZjViYzE2LWUzZmUtNzI0Yy1hMTc5LTM3YzE5NTU3M2U3MyIgc3RSZWY6b3JpZ2luYWxEb2N1bWVudElEPSJ4bXAuZGlkOjA0MmM3ZGM0LTA4MDYtODQ0MC05N2E4LTk1OTIwZTYxNWFmOSIvPiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8P3hwYWNrZXQgZW5kPSJ3Ij8+/+4ADkFkb2JlAGSAAAAAAf/bAIQADAgICAkIDAkJDBELCgsRFQ8MDA8VGBMTFRMTGBEMDAwMDAwRDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAENCwsNDg0QDg4QFA4ODhQUDg4ODhQRDAwMDAwREQwMDAwMDBEMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwM/8AAEQgB9AH0AwEiAAIRAQMRAf/dAAQAIP/EAT8AAAEFAQEBAQEBAAAAAAAAAAMAAQIEBQYHCAkKCwEAAQUBAQEBAQEAAAAAAAAAAQACAwQFBgcICQoLEAABBAEDAgQCBQcGCAUDDDMBAAIRAwQhEjEFQVFhEyJxgTIGFJGhsUIjJBVSwWIzNHKC0UMHJZJT8OHxY3M1FqKygyZEk1RkRcKjdDYX0lXiZfKzhMPTdePzRieUpIW0lcTU5PSltcXV5fVWZnaGlqa2xtbm9jdHV2d3h5ent8fX5/cRAAICAQIEBAMEBQYHBwYFNQEAAhEDITESBEFRYXEiEwUygZEUobFCI8FS0fAzJGLhcoKSQ1MVY3M08SUGFqKygwcmNcLSRJNUoxdkRVU2dGXi8rOEw9N14/NGlKSFtJXE1OT0pbXF1eX1VmZ2hpamtsbW5vYnN0dXZ3eHl6e3x//aAAwDAQACEQMRAD8A9VSSSSUpJJJJSkkkklKSSSSUpJJJJSkkkklKSSSSUpJJJJSkkkklKSSSSUpJJJJSkkkklKSSSSUpJJJJSkkkklKSSSSU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'
            pil_img = PilImage.open(io.BytesIO(base64.b64decode(b64_data)))
            welcome_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(220, 220))
        except Exception:
            pass

        def _dismiss_welcome(event=None):
            try:
                welcome_frame.place_forget()
                self.unbind("<Button-1>")
            except Exception:
                pass
            self.after(150, self._maybe_prompt_alt_ffmpeg)

        welcome_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=0)
        welcome_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        welcome_frame.lift()

        inner = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        inner.place(relx=0.5, rely=0.45, anchor="center")

        if welcome_image:
            lbl_img = ctk.CTkLabel(inner, image=welcome_image, text="")
            lbl_img.pack(pady=(0, 18))
            lbl_img.bind("<Button-1>", _dismiss_welcome)

        lbl_title = ctk.CTkLabel(inner, text="FFmpeg Toolkit",
            font=ctk.CTkFont(size=28, weight="bold"), text_color="#ffffff")
        lbl_title.pack()
        lbl_title.bind("<Button-1>", _dismiss_welcome)

        lbl_click = ctk.CTkLabel(inner, text="Click anywhere to begin",
            font=ctk.CTkFont(size=14), text_color="#888888")
        lbl_click.pack(pady=(8, 0))
        lbl_click.bind("<Button-1>", _dismiss_welcome)

        ffmpeg_found = bool(self._ffmpeg_path) and os.path.isfile(self._ffmpeg_path)
        if not ffmpeg_found:
            lbl_warn = ctk.CTkLabel(inner,
                text="\u26A0\uFE0F  ffmpeg not found -- place it next to this app, add it to PATH, or set it in Settings",
                font=ctk.CTkFont(size=12), text_color="#e8a020")
            lbl_warn.pack(pady=(12, 0))

        ctk.CTkButton(
            inner,
            text="Click here to begin  \u25B6",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c0392b",
            hover_color="#e74c3c",
            corner_radius=8,
            command=_dismiss_welcome
        ).pack(pady=(22, 0), ipadx=10, ipady=4)

        ctk.CTkLabel(
            inner,
            text=f"Version {APP_VERSION}  \u2022  Built {BUILD_DATE}",
            font=ctk.CTkFont(size=11),
            text_color="#555555"
        ).pack(pady=(14, 0))

        ctk.CTkLabel(
            inner,
            text="Developed by Adrian Newington  |  Coding by Emergent.ai",
            font=ctk.CTkFont(size=11),
            text_color="#555555"
        ).pack(pady=(4, 0))

    # ------------------------------------------------------------------
    # Generic single-file-in / single-file-out tool panel
    #
    # Every "pick a file, tweak a couple of options, run ffmpeg" tab
    # (Quick Fix, Proxy Creator, Trim Clip, Extract Audio, etc.) shares
    # the same input/output rows, run button, progress bar and log box.
    # Building that layout by hand in each tab method is how the file
    # ended up 2000+ lines long with the same ~50 lines repeated a dozen
    # times. This method captures the shared shape once; each tab then
    # only needs to describe what makes it different: its help text, its
    # extra option widgets (if any), how to name the output file, and
    # how to turn the chosen options into an ffmpeg argv list.
    # ------------------------------------------------------------------

    def _build_tool_panel(
        self,
        parent,
        *,
        help_text,
        cmd_builder,
        output_namer,
        options_builder=None,
        file_filters=None,
        output_filetypes=None,
        run_label="Run",
        validate=None,
    ):
        """Build a standard input/output ffmpeg tool panel.

        cmd_builder(ffmpeg_path, input_path, output_path, opts) -> list[str]
        output_namer(input_path, opts) -> str (full output path)
        options_builder(options_frame, opts, on_option_change) -> None
            Populates `opts` with whatever widgets/vars the panel needs;
            call on_option_change() whenever a change should refresh the
            auto-generated output path.
        validate(opts) -> str | None
            Return an error message to abort the run, or None to proceed.
        """
        file_filters = file_filters or VIDEO_FILTERS
        output_filetypes = output_filetypes or file_filters
        opts = {}

        # Input file row
        input_frame = ctk.CTkFrame(parent, fg_color="transparent")
        input_frame.pack(fill="x", pady=(10, 5))

        ctk.CTkLabel(input_frame, text="Input File:", width=80, anchor="w").pack(
            side="left", padx=(0, 5)
        )
        input_entry = ctk.CTkEntry(input_frame, placeholder_text="Select input file...")
        input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # Output file row
        output_frame = ctk.CTkFrame(parent, fg_color="transparent")
        output_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(output_frame, text="Output File:", width=80, anchor="w").pack(
            side="left", padx=(0, 5)
        )
        output_entry = ctk.CTkEntry(output_frame, placeholder_text="Auto-generated or browse...")
        output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def update_output(*_args):
            input_path = input_entry.get().strip()
            if not input_path:
                return
            new_path = output_namer(input_path, opts)
            output_entry.delete(0, "end")
            output_entry.insert(0, new_path)

        def browse_input():
            init_dir = self._get_initial_dir()
            path = filedialog.askopenfilename(
                filetypes=file_filters, initialdir=init_dir if init_dir else None
            )
            if path:
                self._remember_folder(path)
                input_entry.delete(0, "end")
                input_entry.insert(0, path)
                update_output()

        ctk.CTkButton(input_frame, text="Browse", width=80, command=browse_input).pack(
            side="left"
        )

        def browse_output():
            path = filedialog.asksaveasfilename(filetypes=output_filetypes)
            if path:
                output_entry.delete(0, "end")
                output_entry.insert(0, path)

        ctk.CTkButton(output_frame, text="Browse", width=80, command=browse_output).pack(
            side="left"
        )

        input_entry.bind("<FocusOut>", update_output)

        # Panel-specific option widgets (dropdowns, sliders, time entries...)
        if options_builder:
            options_frame = ctk.CTkFrame(parent, fg_color="transparent")
            options_frame.pack(fill="x", pady=5)
            options_builder(options_frame, opts, update_output)

        # Run button + progress bar
        run_btn = ctk.CTkButton(
            parent, text=run_label, height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        run_btn.pack(fill="x", pady=(10, 5))

        progress = ctk.CTkProgressBar(parent, mode="indeterminate")
        progress.pack(fill="x", pady=(0, 5))
        progress.set(0)

        # Log area
        log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))
        log_box.pack(fill="both", expand=True, pady=(5, 0))
        log_box.configure(state="disabled")
        self._log(log_box, help_text)

        def run_command():
            input_path = input_entry.get().strip()
            output_path = output_entry.get().strip()

            if not input_path:
                self._log(log_box, "Error: No input file selected.\n")
                return

            if not output_path:
                update_output()
                output_path = output_entry.get().strip()

            if validate:
                error = validate(opts)
                if error:
                    self._log(log_box, f"Error: {error}\n")
                    return

            if not self._ffmpeg_path or not os.path.isfile(self._ffmpeg_path):
                self._log(log_box, "Error: ffmpeg not found. Set its location in Settings.\n")
                return

            cmd = cmd_builder(self._ffmpeg_path, input_path, output_path, opts)
            self._run_ffmpeg(cmd, log_box, run_btn, progress)

        run_btn.configure(command=run_command)

    # ------------------------------------------------------------------
    # Output naming helpers, shared by output_namer callbacks above
    # ------------------------------------------------------------------

    def _suffixed_output(self, input_path, suffix, ext=None):
        directory = self._get_output_dir(input_path)
        basename = os.path.basename(input_path)
        name, orig_ext = os.path.splitext(basename)
        return os.path.join(directory, f"{name}{suffix}{ext if ext else orig_ext}")

    # ------------------------------------------------------------------
    # Video tools
    # ------------------------------------------------------------------

    def _build_fix_tab(self, parent, mode):
        is_quick = mode == "quick"
        suffix = "_fixed" if is_quick else "_stubborn_fixed"

        def cmd_builder(ffmpeg, inp, out, opts):
            if is_quick:
                return [ffmpeg, "-i", inp, "-map", "0:v:0", "-map", "0:a?",
                        "-c", "copy", out, "-y"]
            return [ffmpeg, "-i", inp, "-map", "0:v:0", "-map", "0:a?",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out, "-y"]

        if is_quick:
            help_text = (
                "\u2139\ufe0f  Quick Fix\n"
                "Remuxes your video into a new container, copying all streams without re-encoding.\n"
                "Use this first for files that won't import into DaVinci Resolve.\n\n"
                "\U0001F4CB FFmpeg command:\n"
                "ffmpeg -i input.mp4 -map 0:v:0 -map 0:a? -c copy output.mov -y\n\n"
                "Select a file above and click Run to begin.\n"
            )
        else:
            help_text = (
                "\u2139\ufe0f  Stubborn Fix\n"
                "Same as Quick Fix but re-encodes the audio track to AAC 192k.\n"
                "Use this when Quick Fix doesn't solve the problem \u2014 often fixes incompatible audio codecs.\n\n"
                "Select a file above and click Run to begin.\n"
            )

        self._build_tool_panel(
            parent,
            help_text=help_text,
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, suffix),
        )

    def _build_proxy_tab(self, parent):
        SCALES = {
            "Half (1/2)": "scale=iw/2:ih/2",
            "Quarter (1/4)": "scale=iw/4:ih/4",
            "720p": "scale=1280:720",
            "480p": "scale=854:480",
        }

        def options_builder(frame, opts, on_change):
            ctk.CTkLabel(frame, text="Resolution:", anchor="w").pack(side="left", padx=(0, 5))
            opts["resolution"] = ctk.StringVar(value="Half (1/2)")
            ctk.CTkOptionMenu(
                frame, variable=opts["resolution"], values=list(SCALES.keys()), width=130
            ).pack(side="left", padx=(0, 15))

            ctk.CTkLabel(frame, text="Codec:", anchor="w").pack(side="left", padx=(0, 5))
            opts["codec"] = ctk.StringVar(value="H.264")
            ctk.CTkOptionMenu(
                frame, variable=opts["codec"], values=["H.264", "H.265"], width=100
            ).pack(side="left", padx=(0, 15))

            ctk.CTkLabel(frame, text="Quality (CRF):", anchor="w").pack(side="left", padx=(0, 5))
            crf_label = ctk.CTkLabel(frame, text="23", width=30)
            opts["crf"] = ctk.IntVar(value=23)

            def on_crf_change(value):
                opts["crf"].set(int(value))
                crf_label.configure(text=str(int(value)))

            crf_slider = ctk.CTkSlider(frame, from_=18, to=28, number_of_steps=10,
                                        command=on_crf_change)
            crf_slider.set(23)
            crf_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
            crf_label.pack(side="right", padx=(5, 0))

        def cmd_builder(ffmpeg, inp, out, opts):
            scale = SCALES[opts["resolution"].get()]
            codec = "libx264" if opts["codec"].get() == "H.264" else "libx265"
            crf = str(opts["crf"].get())
            return [ffmpeg, "-i", inp, "-vf", scale,
                    "-c:v", codec, "-crf", crf, "-preset", "fast",
                    "-c:a", "copy", out, "-y"]

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  Proxy Creator\n"
                "Creates a lightweight, lower-resolution copy of your footage for smooth editing in DaVinci Resolve.\n"
                "Resolve edits using the proxy, then switches back to the full-quality original at export \u2014 no quality loss.\n\n"
                "Select a file above and click Run to begin.\n"
            ),
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_proxy"),
            options_builder=options_builder,
        )

    def _build_prores_tab(self, parent):
        PROFILES = {
            "ProRes 422 LT": "1",
            "ProRes 422": "2",
            "ProRes 422 HQ": "3",
            "ProRes 4444": "4",
        }

        def options_builder(frame, opts, on_change):
            ctk.CTkLabel(frame, text="Profile:", anchor="w").pack(side="left", padx=(0, 5))
            opts["profile"] = ctk.StringVar(value="ProRes 422")
            ctk.CTkOptionMenu(
                frame, variable=opts["profile"], values=list(PROFILES.keys()), width=160
            ).pack(side="left")

        def cmd_builder(ffmpeg, inp, out, opts):
            profile_val = PROFILES.get(opts["profile"].get(), "2")
            return [ffmpeg, "-i", inp, "-c:v", "prores_ks", "-profile:v", profile_val,
                    "-c:a", "pcm_s16le", out, "-y"]

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  ProRes Export\n"
                "Converts your file to Apple ProRes \u2014 DaVinci Resolve's preferred high-quality ingest format.\n"
                "ProRes 422 is a great all-rounder; HQ for maximum quality; LT for smaller file sizes.\n\n"
                "\U0001F4CB FFmpeg command:\n"
                "ffmpeg -i input.mp4 -c:v prores_ks -profile:v 2 -c:a pcm_s16le output.mov -y\n\n"
                "Select a file above and click Run to begin.\n"
            ),
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_prores", ext=".mov"),
            options_builder=options_builder,
            output_filetypes=[("MOV files", "*.mov"), ("All files", "*.*")],
        )

    def _build_fix_timestamps_tab(self, parent):
        def cmd_builder(ffmpeg, inp, out, opts):
            return [ffmpeg, "-fflags", "+genpts", "-i", inp,
                    "-map", "0:v:0", "-map", "0:a?", "-c", "copy", out, "-y"]

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  Fix Timestamps\n"
                "Regenerates missing or corrupt presentation timestamps (PTS) in the file.\n"
                "Use this when footage plays back with stuttering, freezing, or skipping in DaVinci Resolve.\n\n"
                "\U0001F4CB FFmpeg command:\n"
                "ffmpeg -fflags +genpts -i input.mp4 -map 0:v:0 -map 0:a? -c copy output.mp4 -y\n\n"
                "Select a file above and click Run to begin.\n"
            ),
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_fixed_ts"),
        )

    def _build_trim_clip_tab(self, parent):
        def options_builder(frame, opts, on_change):
            ctk.CTkLabel(frame, text="Start (HH:MM:SS or seconds):", anchor="w").pack(
                side="left", padx=(0, 5)
            )
            opts["start"] = ctk.CTkEntry(frame, width=120)
            opts["start"].insert(0, "00:00:00")
            opts["start"].pack(side="left", padx=(0, 20))

            ctk.CTkLabel(frame, text="Duration (HH:MM:SS or seconds):", anchor="w").pack(
                side="left", padx=(0, 5)
            )
            opts["duration"] = ctk.CTkEntry(frame, width=120)
            opts["duration"].insert(0, "00:00:10")
            opts["duration"].pack(side="left")

        def cmd_builder(ffmpeg, inp, out, opts):
            start = opts["start"].get().strip()
            duration = opts["duration"].get().strip()
            return [ffmpeg, "-ss", start, "-i", inp, "-t", duration,
                    "-map", "0:v:0", "-map", "0:a?", "-c", "copy", out, "-y"]

        def validate(opts):
            if not opts["start"].get().strip():
                return "Start time is required."
            if not opts["duration"].get().strip():
                return "Duration is required."
            return None

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  Trim Clip\n"
                "Cuts a section of your video by start time and duration without re-encoding.\n"
                "Extremely fast \u2014 it simply copies the frames within your chosen range.\n\n"
                "\U0001F4CB FFmpeg command:\n"
                "ffmpeg -ss 00:00:30 -i input.mp4 -t 00:01:00 -map 0:v:0 -map 0:a? -c copy output.mp4 -y\n\n"
                "Select a file above and click Run to begin.\n"
            ),
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_trim"),
            options_builder=options_builder,
            validate=validate,
        )

    def _build_still_frame_tab(self, parent):
        EXT = {"PNG": ".png", "JPEG": ".jpg"}

        def options_builder(frame, opts, on_change):
            ctk.CTkLabel(frame, text="Timecode (HH:MM:SS or seconds):", anchor="w").pack(
                side="left", padx=(0, 5)
            )
            opts["timecode"] = ctk.CTkEntry(frame, width=120)
            opts["timecode"].insert(0, "00:00:01")
            opts["timecode"].pack(side="left", padx=(0, 20))

            ctk.CTkLabel(frame, text="Format:", anchor="w").pack(side="left", padx=(0, 5))
            opts["format"] = ctk.StringVar(value="PNG")
            ctk.CTkOptionMenu(
                frame, variable=opts["format"], values=list(EXT.keys()), width=100,
                command=lambda _v: on_change()
            ).pack(side="left")

        def cmd_builder(ffmpeg, inp, out, opts):
            timecode = opts["timecode"].get().strip()
            return [ffmpeg, "-ss", timecode, "-i", inp, "-frames:v", "1", out, "-y"]

        def validate(opts):
            if not opts["timecode"].get().strip():
                return "Timecode is required."
            return None

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  Still Frame Export\n"
                "Extracts a single frame from your video at the specified timecode and saves it as an image.\n"
                "Useful for thumbnails, reference shots, or grabbing a frame for colour grading.\n\n"
                "\U0001F4CB FFmpeg command:\n"
                "ffmpeg -ss 00:01:30 -i input.mp4 -frames:v 1 output.png -y\n\n"
                "Select a file above and click Run to begin.\n"
            ),
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(
                inp, "_frame", ext=EXT[opts["format"].get()]
            ),
            options_builder=options_builder,
            validate=validate,
            output_filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
        )

    # ------------------------------------------------------------------
    # Audio tools
    # ------------------------------------------------------------------

    def _build_extract_audio_tab(self, parent):
        FORMATS = {
            "WAV (PCM)": (".wav", ["-c:a", "pcm_s16le"]),
            "AAC (192k)": (".aac", ["-c:a", "aac", "-b:a", "192k"]),
        }

        def options_builder(frame, opts, on_change):
            ctk.CTkLabel(frame, text="Format:", anchor="w").pack(side="left", padx=(0, 5))
            opts["format"] = ctk.StringVar(value="WAV (PCM)")
            ctk.CTkOptionMenu(
                frame, variable=opts["format"], values=list(FORMATS.keys()), width=140,
                command=lambda _v: on_change()
            ).pack(side="left")

        def cmd_builder(ffmpeg, inp, out, opts):
            _ext, codec_args = FORMATS[opts["format"].get()]
            return [ffmpeg, "-i", inp, "-map", "0:a:0", *codec_args, out, "-y"]

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  Extract Audio\n"
                "Pulls the audio track out of your video file as a standalone audio file.\n"
                "WAV gives you uncompressed audio; AAC gives you a smaller compressed file.\n\n"
                "\U0001F4CB FFmpeg commands:\n"
                "WAV: ffmpeg -i input.mp4 -map 0:a:0 -c:a pcm_s16le output.wav -y\n"
                "AAC: ffmpeg -i input.mp4 -map 0:a:0 -c:a aac -b:a 192k output.m4a -y\n\n"
                "Select a file above and click Run to begin.\n"
            ),
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(
                inp, "", ext=FORMATS[opts["format"].get()][0]
            ),
            options_builder=options_builder,
            output_filetypes=[("Audio files", "*.wav *.aac"), ("All files", "*.*")],
        )

    def _build_strip_audio_tab(self, parent):
        def cmd_builder(ffmpeg, inp, out, opts):
            return [ffmpeg, "-i", inp, "-map", "0:v:0", "-c:v", "copy", "-an", out, "-y"]

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  Strip Audio\n"
                "Removes all audio tracks from the file, keeping video only.\n"
                "Useful for music-licensed footage or when you plan to replace the audio in Resolve.\n\n"
                "\U0001F4CB FFmpeg command:\n"
                "ffmpeg -i input.mp4 -map 0:v:0 -c:v copy -an output.mp4 -y\n\n"
                "Select a file above and click Run to begin.\n"
            ),
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_noaudio"),
        )

    def _build_audio_accessibility_tab(self, parent):
        LOUDNESS_OPTIONS = [
            "-14 LUFS  (YouTube / Spotify)",
            "-16 LUFS  (Apple Music)",
            "-23 LUFS  (Broadcast / EBU R128)",
            "-27 LUFS  (Netflix / Amazon)",
        ]

        def options_builder(frame, opts, on_change):
            ctk.CTkLabel(frame, text="Mode:", anchor="w").pack(side="left", padx=(0, 5))
            opts["mode"] = ctk.StringVar(value="Dynamic Normaliser")

            loudness_frame = ctk.CTkFrame(frame.master, fg_color="transparent")
            ctk.CTkLabel(loudness_frame, text="Target Loudness:", width=130, anchor="w").pack(
                side="left"
            )
            opts["loudness"] = ctk.StringVar(value="-16 LUFS  (Apple Music)")
            ctk.CTkOptionMenu(
                loudness_frame, values=LOUDNESS_OPTIONS, variable=opts["loudness"], width=260
            ).pack(side="left")

            def toggle_loudness(mode):
                if mode == "Loudness Compression":
                    loudness_frame.pack(fill="x", padx=15, pady=(0, 4))
                else:
                    loudness_frame.pack_forget()

            ctk.CTkSegmentedButton(
                frame,
                values=["Dynamic Normaliser", "Loudness Compression"],
                variable=opts["mode"],
                command=toggle_loudness,
            ).pack(side="left")

        def cmd_builder(ffmpeg, inp, out, opts):
            if opts["mode"].get() == "Dynamic Normaliser":
                af = "dynaudnorm"
            else:
                lufs = opts["loudness"].get().split()[0]
                af = f"loudnorm=I={lufs}:LRA=7:TP=-2"
            return [ffmpeg, "-i", inp, "-c:v", "copy", "-af", af, out, "-y"]

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  Audio Accessibility\n"
                "Reduce harsh dynamic range or normalise loudness before importing into DaVinci Resolve.\n"
                "Designed for editors who are hard of hearing or working in dialogue-heavy productions.\n\n"
                "Commands:\n"
                "  Dynamic Normaliser:   ffmpeg.exe -i <input> -c:v copy -af dynaudnorm <o> -y\n"
                "  Loudness Compression: ffmpeg.exe -i <input> -c:v copy -af \"loudnorm=I=-16:LRA=7:TP=-2\" <o> -y\n\n"
                "Select a file above and click Run to begin.\n"
            ),
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_audio_fixed"),
            options_builder=options_builder,
        )

    # ------------------------------------------------------------------
    # Bespoke tabs
    #
    # These four don't fit the generic input/output panel shape closely
    # enough to be worth forcing into it: Inspect has no output file,
    # Custom Command runs an arbitrary shell string, Batch Audio Convert
    # operates on a whole folder of files, and Settings isn't an ffmpeg
    # tool at all. Each stays a dedicated method.
    # ------------------------------------------------------------------

    def _build_inspect_tab(self, parent):
        input_frame = ctk.CTkFrame(parent, fg_color="transparent")
        input_frame.pack(fill="x", pady=(10, 5))

        ctk.CTkLabel(input_frame, text="Input File:", width=80, anchor="w").pack(
            side="left", padx=(0, 5)
        )
        input_entry = ctk.CTkEntry(input_frame, placeholder_text="Select file to inspect...")
        input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_input():
            path = filedialog.askopenfilename(filetypes=VIDEO_FILTERS)
            if path:
                input_entry.delete(0, "end")
                input_entry.insert(0, path)

        ctk.CTkButton(input_frame, text="Browse", width=80, command=browse_input).pack(
            side="left"
        )

        inspect_btn = ctk.CTkButton(
            parent, text="Inspect", height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        inspect_btn.pack(fill="x", pady=(10, 5))

        progress = ctk.CTkProgressBar(parent, mode="indeterminate")
        progress.pack(fill="x", pady=(0, 5))
        progress.set(0)

        log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))
        log_box.pack(fill="both", expand=True, pady=(5, 0))
        log_box.configure(state="disabled")
        self._log(log_box, (
            "\u2139\ufe0f  Inspect File\n"
            "Reads and displays all stream information from the file \u2014 codec, resolution, "
            "bitrate, audio format \u2014 without modifying it.\n\n"
            "Select a file above and click Inspect to begin.\n"
        ))

        def run_inspect():
            input_path = input_entry.get().strip()
            if not input_path:
                self._log(log_box, "Error: No input file selected.\n")
                return
            if not self._ffmpeg_path or not os.path.isfile(self._ffmpeg_path):
                self._log(log_box, "Error: ffmpeg not found. Set its location in Settings.\n")
                return
            cmd = [self._ffmpeg_path, "-i", input_path]
            self._run_ffmpeg(cmd, log_box, inspect_btn, progress, expect_error=True)

        inspect_btn.configure(command=run_inspect)

    def _build_custom_tab(self, parent):
        file_filters = [
            ("Video files", "*.mp4 *.mov *.mkv *.avi *.mxf *.m4v *.wmv"),
            ("Audio files", "*.wav *.mp3 *.aac *.flac *.ogg *.m4a"),
            ("All files", "*.*"),
        ]

        input_frame = ctk.CTkFrame(parent, fg_color="transparent")
        input_frame.pack(fill="x", pady=(10, 5))
        ctk.CTkLabel(input_frame, text="Input File:", width=80, anchor="w").pack(
            side="left", padx=(0, 5)
        )
        input_entry = ctk.CTkEntry(input_frame, placeholder_text="Select input file...")
        input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_input():
            init_dir = self._get_initial_dir()
            path = filedialog.askopenfilename(
                filetypes=file_filters, initialdir=init_dir if init_dir else None
            )
            if path:
                self._remember_folder(path)
                input_entry.delete(0, "end")
                input_entry.insert(0, path)

        ctk.CTkButton(input_frame, text="Browse", width=80, command=browse_input).pack(
            side="left"
        )

        output_frame = ctk.CTkFrame(parent, fg_color="transparent")
        output_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(output_frame, text="Output File:", width=80, anchor="w").pack(
            side="left", padx=(0, 5)
        )
        output_entry = ctk.CTkEntry(output_frame, placeholder_text="Select output file...")
        output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_output():
            path = filedialog.asksaveasfilename(filetypes=file_filters)
            if path:
                output_entry.delete(0, "end")
                output_entry.insert(0, path)

        ctk.CTkButton(output_frame, text="Browse", width=80, command=browse_output).pack(
            side="left"
        )

        quick_frame = ctk.CTkFrame(parent, fg_color="transparent")
        quick_frame.pack(fill="x", pady=(10, 5))
        ctk.CTkLabel(quick_frame, text="Quick Build:", width=80, anchor="w").pack(
            side="left", padx=(0, 5)
        )

        video_only_var = ctk.BooleanVar(value=False)
        audio_only_var = ctk.BooleanVar(value=False)
        hw_accel_var = ctk.BooleanVar(value=False)
        copy_codec_var = ctk.BooleanVar(value=False)
        overwrite_var = ctk.BooleanVar(value=True)

        ctk.CTkCheckBox(quick_frame, text="Video Only", variable=video_only_var, width=100).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkCheckBox(quick_frame, text="Audio Only", variable=audio_only_var, width=100).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkCheckBox(quick_frame, text="HW Accel", variable=hw_accel_var, width=100).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkCheckBox(quick_frame, text="Copy Codec", variable=copy_codec_var, width=110).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkCheckBox(
            quick_frame, text="Overwrite (-y)", variable=overwrite_var, width=120
        ).pack(side="left", padx=(0, 10))

        cmd_label_frame = ctk.CTkFrame(parent, fg_color="transparent")
        cmd_label_frame.pack(fill="x", pady=(10, 2))
        ctk.CTkLabel(
            cmd_label_frame,
            text="Command (use <input> and <output> as placeholders):",
            anchor="w"
        ).pack(side="left")

        def insert_quick_build():
            parts = ["ffmpeg.exe"]
            if hw_accel_var.get():
                parts.extend(["-hwaccel", "auto"])
            parts.extend(["-i", "<input>"])
            if video_only_var.get() and not audio_only_var.get():
                parts.append("-an")
            elif audio_only_var.get() and not video_only_var.get():
                parts.append("-vn")
            if copy_codec_var.get():
                parts.extend(["-c", "copy"])
            if overwrite_var.get():
                parts.append("-y")
            parts.append("<output>")
            cmd_box.delete("1.0", "end")
            cmd_box.insert("1.0", " ".join(parts))

        ctk.CTkButton(
            cmd_label_frame, text="Build from Checkboxes", width=160,
            command=insert_quick_build
        ).pack(side="right")

        cmd_box = ctk.CTkTextbox(parent, height=80, font=ctk.CTkFont(family="Consolas", size=12))
        cmd_box.pack(fill="x", pady=(0, 5))
        cmd_box.insert("1.0", "ffmpeg.exe -i <input> -c copy -y <output>")

        run_btn = ctk.CTkButton(
            parent, text="Run Custom Command", height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        run_btn.pack(fill="x", pady=(10, 5))

        progress = ctk.CTkProgressBar(parent, mode="indeterminate")
        progress.pack(fill="x", pady=(0, 5))
        progress.set(0)

        log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))
        log_box.pack(fill="both", expand=True, pady=(5, 0))
        log_box.configure(state="disabled")
        self._log(log_box, (
            "\U0001F6E0\ufe0f  Custom Command\n"
            "Build and run any FFmpeg command you like.\n\n"
            "\u2022 Use <input> and <output> as placeholders \u2014 they will be replaced with your selected files.\n"
            "\u2022 Tick the Quick Build checkboxes and click 'Build from Checkboxes' for a head start.\n"
            "\u2022 Or type/paste your own full command string directly.\n\n"
            "\u26A0\ufe0f  The command runs via shell \u2014 double-check before executing!\n\n"
            "Select your files, write your command, and click Run.\n"
        ))

        def run_command():
            input_path = input_entry.get().strip()
            output_path = output_entry.get().strip()
            raw_cmd = cmd_box.get("1.0", "end").strip()

            if not raw_cmd:
                self._log(log_box, "Error: No command entered.\n")
                return
            if "<input>" in raw_cmd and not input_path:
                self._log(log_box, "Error: Command uses <input> but no input file selected.\n")
                return
            if "<output>" in raw_cmd and not output_path:
                self._log(log_box, "Error: Command uses <output> but no output file selected.\n")
                return

            final_cmd = raw_cmd.replace("<input>", f'"{input_path}"')
            final_cmd = final_cmd.replace("<output>", f'"{output_path}"')

            # This tab intentionally runs a shell string (not an argv list)
            # since the whole point is letting the user type an arbitrary
            # command -- it can't reuse _run_ffmpeg's list-based Popen call.
            self._clear_log(log_box)
            run_btn.configure(state="disabled")
            progress.start()

            def worker():
                try:
                    self._log(log_box, f"Running: {final_cmd}\n{'=' * 60}\n")

                    startupinfo = None
                    if sys.platform == "win32":
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                    process = subprocess.Popen(
                        final_cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        startupinfo=startupinfo,
                        universal_newlines=True,
                        errors="replace",
                    )

                    for line in process.stdout:
                        self._log(log_box, line)

                    process.wait()
                    returncode = process.returncode

                    self._log(log_box, f"\n{'=' * 60}\n")
                    if returncode == 0:
                        self._log(log_box, "Done!\n")
                    else:
                        self._log(log_box, f"Error \u2014 check log (exit code: {returncode})\n")

                except Exception as e:
                    self._log(log_box, f"Error: {e}\n")
                finally:
                    self.after(0, lambda: run_btn.configure(state="normal"))
                    self.after(0, lambda: progress.stop())
                    self.after(0, lambda: progress.set(0))

            threading.Thread(target=worker, daemon=True).start()

        run_btn.configure(command=run_command)

    def _build_batch_audio_tab(self, parent):
        import glob

        FORMATS = ["WAV", "MP3", "FLAC", "M4A", "OGG", "AC3"]
        EXT = {"WAV": "wav", "MP3": "mp3", "FLAC": "flac", "M4A": "m4a", "OGG": "ogg", "AC3": "ac3"}
        CODEC = {
            "WAV": ["-c:a", "pcm_s16le"], "MP3": ["-c:a", "libmp3lame"],
            "FLAC": ["-c:a", "flac"], "M4A": ["-c:a", "aac"],
            "OGG": ["-c:a", "libvorbis"], "AC3": ["-c:a", "ac3"],
        }
        SEP = "=" * 52

        log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))

        r1 = ctk.CTkFrame(parent, fg_color="transparent")
        r1.pack(fill="x", padx=15, pady=(12, 4))
        ctk.CTkLabel(r1, text="Input Format:", width=110, anchor="w").pack(side="left")
        in_fmt = ctk.StringVar(value="WAV")
        ctk.CTkOptionMenu(r1, values=FORMATS, variable=in_fmt, width=120,
                          command=lambda v: parent.after(150, scan)).pack(side="left")

        r2 = ctk.CTkFrame(parent, fg_color="transparent")
        r2.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(r2, text="Source Folder:", width=110, anchor="w").pack(side="left")
        folder_ent = ctk.CTkEntry(r2, placeholder_text="Select folder -- scans automatically...")
        folder_ent.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_folder():
            p = filedialog.askdirectory()
            if p:
                folder_ent.delete(0, "end")
                folder_ent.insert(0, p)
                parent.after(150, scan)

        ctk.CTkButton(r2, text="Browse", width=80, command=browse_folder).pack(side="left")

        r3 = ctk.CTkFrame(parent, fg_color="transparent")
        r3.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(r3, text="Output Format:", width=110, anchor="w").pack(side="left")
        out_fmt = ctk.StringVar(value="MP3")
        ctk.CTkOptionMenu(r3, values=FORMATS, variable=out_fmt, width=120,
                          command=lambda v: _toggle_mp3(v)).pack(side="left")

        mp3_wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        mp3_wrapper.pack(fill="x", padx=15, pady=(0, 4))

        mp3_fr = ctk.CTkFrame(mp3_wrapper, fg_color="transparent")
        ctk.CTkLabel(mp3_fr, text="Bitrate:", width=110, anchor="w").pack(side="left")
        bitrate = ctk.StringVar(value="192k")
        ctk.CTkOptionMenu(mp3_fr, values=["128k", "192k", "256k", "320k"],
                          variable=bitrate, width=100).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(mp3_fr, text="Quality (VBR):", anchor="w").pack(side="left")
        quality = ctk.StringVar(value="None (CBR)")
        ctk.CTkOptionMenu(mp3_fr,
                          values=["None (CBR)", "V0 (best)", "V2", "V4", "V6", "V9 (smallest)"],
                          variable=quality, width=140).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(mp3_fr, text="<-- overrides bitrate",
                     text_color="#888888", font=ctk.CTkFont(size=11)).pack(side="left")
        mp3_fr.pack(fill="x")

        def _toggle_mp3(fmt):
            if fmt == "MP3":
                mp3_fr.pack(fill="x")
            else:
                mp3_fr.pack_forget()

        run_btn = ctk.CTkButton(parent, text="  Convert All",
                                font=ctk.CTkFont(size=14, weight="bold"),
                                fg_color="#1f538d", hover_color="#2980b9",
                                height=40, state="disabled")
        run_btn.pack(fill="x", padx=15, pady=(8, 4))

        progress = ctk.CTkProgressBar(parent, mode="indeterminate")
        progress.pack(fill="x", padx=15, pady=(0, 6))
        progress.stop()

        log_box.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        log_box.configure(state="disabled")
        self._log(log_box, (
            "i  Batch Audio Convert\n"
            "Converts all audio files of a chosen format in a folder to a new format.\n"
            "Converted files are saved into a CONVERTED subfolder.\n\n"
            "1. Choose input audio format\n"
            "2. Browse to source folder -- files are scanned automatically\n"
            "3. Choose output format (and bitrate/quality if MP3)\n"
            "4. Click Convert All to begin\n"
        ))

        files = []

        def scan():
            nonlocal files
            folder = folder_ent.get().strip()
            if not folder or not os.path.isdir(folder):
                return
            ext = EXT[in_fmt.get()]
            seen, files = set(), []
            for f in sorted(glob.glob(os.path.join(folder, "*." + ext)) +
                            glob.glob(os.path.join(folder, "*." + ext.upper()))):
                k = f.lower()
                if k not in seen:
                    seen.add(k)
                    files.append(f)
            self._clear_log(log_box)
            if not files:
                self._log(log_box, "No ." + ext.upper() + " files found in:\n" + folder + "\n")
                run_btn.configure(state="disabled")
                return
            self._log(log_box, "Found " + str(len(files)) + " ." + ext.upper() + " file(s) in:\n" + folder + "\n\n")
            for i, f in enumerate(files, 1):
                self._log(log_box, "  " + str(i).rjust(3) + ".  " + os.path.basename(f) + "\n")
            self._log(log_box, "\nSelect output format and click Convert All to begin.\n")
            run_btn.configure(state="normal")

        def convert_all():
            if not files:
                self._log(log_box, "\nERROR: No files. Select a folder first.\n")
                return
            folder = folder_ent.get().strip()
            fmt = out_fmt.get()
            ext = EXT[fmt]
            out_dir = os.path.join(folder, "CONVERTED")
            os.makedirs(out_dir, exist_ok=True)
            args = list(CODEC[fmt])
            if fmt == "MP3":
                q = quality.get()
                if q == "None (CBR)":
                    args += ["-b:a", bitrate.get()]
                else:
                    args += ["-q:a", {"V0 (best)": "0", "V2": "2", "V4": "4",
                                       "V6": "6", "V9 (smallest)": "9"}.get(q, "2")]
            run_btn.configure(state="disabled")
            progress.start()

            def worker():
                self._log(log_box, "\n" + SEP + "\n")
                self._log(log_box, "Converting " + str(len(files)) + " file(s) -> " + fmt + "\n")
                self._log(log_box, "Output: CONVERTED/\n" + SEP + "\n\n")
                ok = fail = 0
                startupinfo = None
                if sys.platform == "win32":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                for i, inp in enumerate(files, 1):
                    base = os.path.splitext(os.path.basename(inp))[0]
                    outp = os.path.join(out_dir, base + "." + ext)
                    self._log(log_box, "[" + str(i) + "/" + str(len(files)) + "]  " + os.path.basename(inp) + "\n")
                    self._log(log_box, "         -> " + base + "." + ext + "\n")
                    cmd = [self._ffmpeg_path, "-i", inp] + args + [outp, "-y"]
                    try:
                        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           startupinfo=startupinfo)
                        if r.returncode == 0:
                            self._log(log_box, "         OK Done\n")
                            ok += 1
                        else:
                            err = r.stderr.decode(errors="replace").strip().split("\n")[-1]
                            self._log(log_box, "         FAILED: " + err + "\n")
                            fail += 1
                    except Exception as e:
                        self._log(log_box, "         ERROR: " + str(e) + "\n")
                        fail += 1
                self._log(log_box, "\n" + SEP + "\n")
                self._log(log_box, "Complete -- " + str(ok) + " converted, " + str(fail) + " failed\n")
                if ok > 0:
                    self._log(log_box, "\nSaved to:\n" + out_dir + "\n\nContents of CONVERTED/:\n")
                    for f in sorted(os.listdir(out_dir)):
                        sz = os.path.getsize(os.path.join(out_dir, f)) // 1024
                        self._log(log_box, "    " + f + "  (" + str(sz) + " KB)\n")
                self._log(log_box, SEP + "\n")
                parent.after(0, lambda: progress.stop())
                parent.after(0, lambda: run_btn.configure(state="normal"))

            threading.Thread(target=worker, daemon=True).start()

        run_btn.configure(command=convert_all)

    def _build_settings_tab(self, parent):
        ffmpeg_frame = ctk.CTkFrame(parent, fg_color="transparent")
        ffmpeg_frame.pack(fill="x", pady=(15, 5))

        ctk.CTkLabel(
            ffmpeg_frame, text="FFmpeg Location:", width=160, anchor="w"
        ).pack(side="left", padx=(0, 5))

        ffmpeg_entry = ctk.CTkEntry(
            ffmpeg_frame,
            placeholder_text="Auto-detected next to app or on PATH -- browse to override"
        )
        ffmpeg_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        if self._settings.get("ffmpeg_path"):
            ffmpeg_entry.insert(0, self._settings["ffmpeg_path"])

        def browse_ffmpeg():
            filetypes = (
                [("ffmpeg.exe", "ffmpeg.exe"), ("All files", "*.*")]
                if sys.platform == "win32"
                else [("ffmpeg", "ffmpeg"), ("All files", "*.*")]
            )
            path = filedialog.askopenfilename(filetypes=filetypes)
            if path:
                ffmpeg_entry.delete(0, "end")
                ffmpeg_entry.insert(0, path)

        ctk.CTkButton(ffmpeg_frame, text="Browse", width=80, command=browse_ffmpeg).pack(
            side="left"
        )

        resolved = self._ffmpeg_path if (self._ffmpeg_path and os.path.isfile(self._ffmpeg_path)) else None
        ffmpeg_status_label = ctk.CTkLabel(
            parent,
            text=(f"Currently using: {resolved}" if resolved
                  else "Not found -- checked app folder, then system PATH, then this setting."),
            font=ctk.CTkFont(size=11),
            text_color="#888888" if resolved else "#e8a020",
            anchor="w",
        )
        ffmpeg_status_label.pack(fill="x", padx=5, pady=(0, 10))

        # Kept as instance attrs so _maybe_prompt_alt_ffmpeg() can refresh
        # this panel live after the user answers the pin-this-copy prompt,
        # without needing to rebuild the whole tab.
        self._settings_ffmpeg_entry = ffmpeg_entry
        self._settings_ffmpeg_status_label = ffmpeg_status_label

        folder_frame = ctk.CTkFrame(parent, fg_color="transparent")
        folder_frame.pack(fill="x", pady=(5, 5))

        ctk.CTkLabel(
            folder_frame, text="Default Output Folder:", width=160, anchor="w"
        ).pack(side="left", padx=(0, 5))

        folder_entry = ctk.CTkEntry(
            folder_frame, placeholder_text="Leave empty to use input file's folder"
        )
        folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        if self._settings.get("default_output_folder"):
            folder_entry.insert(0, self._settings["default_output_folder"])

        def browse_folder():
            path = filedialog.askdirectory()
            if path:
                folder_entry.delete(0, "end")
                folder_entry.insert(0, path)

        ctk.CTkButton(folder_frame, text="Browse", width=80, command=browse_folder).pack(
            side="left"
        )

        remember_var = ctk.BooleanVar(value=self._settings.get("remember_last_folder", True))
        ctk.CTkCheckBox(
            parent, text="Remember last input folder", variable=remember_var
        ).pack(anchor="w", pady=(10, 5), padx=5)

        def save_settings():
            self._settings["default_output_folder"] = folder_entry.get().strip()
            self._settings["remember_last_folder"] = remember_var.get()
            self._settings["ffmpeg_path"] = ffmpeg_entry.get().strip()
            self._save_settings()

            self._ffmpeg_path = self._resolve_ffmpeg_path()
            found = bool(self._ffmpeg_path) and os.path.isfile(self._ffmpeg_path)

            ffmpeg_status_label.configure(
                text=(f"Currently using: {self._ffmpeg_path}" if found
                      else "Not found -- checked app folder, then system PATH, then this setting."),
                text_color="#888888" if found else "#e8a020",
            )
            self._set_ffmpeg_status(found)

            status_label.configure(text="Settings saved!", text_color="#2ecc71")
            self.after(3000, lambda: status_label.configure(text=""))

        ctk.CTkButton(
            parent, text="Save Settings", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=save_settings
        ).pack(fill="x", pady=(15, 5))

        status_label = ctk.CTkLabel(parent, text="", font=ctk.CTkFont(size=12))
        status_label.pack(anchor="w", padx=5)

    # ------------------------------------------------------------------
    # Logging + subprocess execution, shared by every tab
    # ------------------------------------------------------------------

    def _log(self, textbox, text):
        textbox.configure(state="normal")
        textbox.insert("end", text)
        textbox.see("end")
        textbox.configure(state="disabled")

    def _clear_log(self, textbox):
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.configure(state="disabled")

    def _run_ffmpeg(self, cmd, log_box, btn, progress, expect_error=False):
        self._clear_log(log_box)
        btn.configure(state="disabled")
        progress.start()

        def worker():
            try:
                self._log(log_box, f"Running: {' '.join(cmd)}\n{'=' * 60}\n")

                startupinfo = None
                if sys.platform == "win32":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    startupinfo=startupinfo,
                    universal_newlines=True,
                    errors="replace",
                )

                for line in process.stdout:
                    if expect_error and "At least one output file must be specified" in line:
                        continue
                    self._log(log_box, line)

                process.wait()
                returncode = process.returncode

                self._log(log_box, f"\n{'=' * 60}\n")

                if returncode == 0:
                    self._log(log_box, "Done!\n")
                elif expect_error and returncode == 1:
                    self._log(log_box, "Inspection complete.\n")
                else:
                    self._log(log_box, f"Error \u2014 check log (exit code: {returncode})\n")

            except FileNotFoundError:
                self._log(log_box, "Error: ffmpeg not found. Set its location in Settings.\n")
            except Exception as e:
                self._log(log_box, f"Error: {e}\n")
            finally:
                self.after(0, lambda: btn.configure(state="normal"))
                self.after(0, lambda: progress.stop())
                self.after(0, lambda: progress.set(0))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()


if __name__ == "__main__":
    app = FFmpegToolkit()
    app.mainloop()