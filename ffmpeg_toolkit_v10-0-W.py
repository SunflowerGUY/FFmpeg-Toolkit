import os
import sys
import io
import re
import math
import time
import json
import base64
import shutil
import pathlib
import subprocess
import tempfile
import threading
import queue
import webbrowser
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu, ttk
from PIL import Image as PilImage, ImageDraw, ImageTk


APP_VERSION = "10.0.W"
BUILD_DATE = "29 September 2026"

# ---------------------------------------------------------------- dashboard look
# Palette from JJ's Battery Health Analyser (ui_theme.py), so the apps match.
BG = "#0b1020"          # window background
CARD = "#151c33"        # panels ("cards")
CARD_2 = "#1b2442"      # raised items inside cards: buttons, headers
INSET = "#0f1529"       # sunken areas: log boxes
BORDER = "#2a3458"
TEXT = "#e6e9f5"
MUTED = "#8b93b5"
DISABLED = "#566086"
BLUE = "#3d8bff"
BLUE_HOVER = "#5a9dff"
PURPLE = "#8b5cf6"
GREEN = "#34d399"
AMBER = "#fbbf24"
RED = "#f87171"
SELECTED = "#223b6c"    # blue tint on CARD: selected sidebar item, dropdown hover
HOVER = "#24305a"
SCROLL = "#353c56"
SCROLL_HOVER = "#4c5370"
ABORT = "#b4234a"
ABORT_HOVER = "#db2777"
WARN_FILL = "#3e3930"   # amber tint on CARD, for warning buttons
WARN_HOVER = "#554a33"
FAINT = "#6b7599"       # small print (credits, trademark lines)
LINK = "#8fb8ff"        # links and hint text
UI_FONT = "Segoe UI" if sys.platform == "win32" else None


def apply_dashboard_theme():
    """Load CustomTkinter's dark-blue theme, then recolour it with the dashboard
    palette. Every widget made afterwards picks it up, so all tools share the look
    without each one being edited. Must run before the main window is created."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    theme = ctk.ThemeManager.theme

    def put(widget, **values):
        for key, value in values.items():
            theme[widget][key] = [value, value] if isinstance(value, str) and value != "transparent" else value

    put("CTk", fg_color=BG)
    put("CTkToplevel", fg_color=BG)
    put("CTkFrame", corner_radius=12, fg_color=CARD, top_fg_color=CARD_2, border_color=BORDER)
    put("CTkButton", corner_radius=8, border_width=1, fg_color=CARD_2, hover_color=HOVER,
        border_color=BORDER, text_color=TEXT, text_color_disabled=DISABLED)
    put("CTkLabel", text_color=TEXT)
    put("CTkEntry", corner_radius=8, border_width=1, fg_color=CARD, border_color=BORDER,
        text_color=TEXT, placeholder_text_color=MUTED)
    put("CTkCheckBox", corner_radius=5, border_width=2, fg_color=BLUE, border_color=MUTED,
        hover_color=BLUE_HOVER, checkmark_color="#ffffff", text_color=TEXT, text_color_disabled=DISABLED)
    put("CTkSwitch", fg_color=BORDER, progress_color=BLUE, button_color=TEXT,
        button_hover_color="#ffffff", text_color=TEXT, text_color_disabled=DISABLED)
    put("CTkRadioButton", fg_color=BLUE, border_color=MUTED, hover_color=BLUE_HOVER,
        text_color=TEXT, text_color_disabled=DISABLED)
    put("CTkProgressBar", fg_color=CARD_2, progress_color=BLUE, border_color=BORDER)
    put("CTkSlider", fg_color=CARD_2, progress_color=BLUE, button_color=BLUE, button_hover_color=BLUE_HOVER)
    put("CTkOptionMenu", corner_radius=8, fg_color=CARD_2, button_color=CARD_2, button_hover_color=HOVER,
        text_color=TEXT, text_color_disabled=DISABLED)
    put("CTkComboBox", corner_radius=8, border_width=1, fg_color=CARD, border_color=BORDER,
        button_color=BORDER, button_hover_color=MUTED, text_color=TEXT, text_color_disabled=DISABLED)
    put("CTkScrollbar", button_color=SCROLL, button_hover_color=SCROLL_HOVER)
    put("CTkSegmentedButton", corner_radius=8, border_width=2, fg_color=CARD_2, selected_color=BLUE,
        selected_hover_color=BLUE_HOVER, unselected_color=CARD_2, unselected_hover_color=HOVER,
        text_color=TEXT, text_color_disabled=DISABLED)
    put("CTkTextbox", corner_radius=10, border_width=1, fg_color=INSET, border_color=BORDER, text_color=TEXT,
        scrollbar_button_color=SCROLL, scrollbar_button_hover_color=SCROLL_HOVER)
    put("CTkScrollableFrame", label_fg_color=CARD_2)
    put("DropdownMenu", fg_color=CARD_2, hover_color=SELECTED, text_color=TEXT)
    if UI_FONT:
        theme["CTkFont"]["family"] = UI_FONT


def dashboard_card(parent, title=None, **pack):
    """A rounded dark panel like the Battery Monitor's cards. Returns (card, body):
    put widgets in body. The card is packed with `pack` (default: fill x)."""
    card = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
    card.pack(**(pack or {"fill": "x", "pady": (0, 10)}))
    body = ctk.CTkFrame(card, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=16, pady=(10 if title else 12, 12))
    if title:
        ctk.CTkLabel(body, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x", pady=(0, 6))
    return card, body


def status_chip(parent):
    """Pill holding a status dot and its text (e.g. "ffmpeg found"). Returns (dot, label)."""
    chip = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
    chip.pack(side="left", padx=(8, 0))
    dot = ctk.CTkLabel(chip, text="\u25cf", font=ctk.CTkFont(size=12), width=14)
    dot.pack(side="left", padx=(10, 4), pady=2)
    label = ctk.CTkLabel(chip, text="", font=ctk.CTkFont(size=12), text_color=MUTED)
    label.pack(side="left", padx=(0, 12), pady=2)
    return dot, label


class ActivityBar(ctk.CTkProgressBar):
    """Indeterminate progress bar that is invisible while idle: at rest a CTk
    indeterminate bar still shows a bright segment, which looks like activity."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._idle()

    def _idle(self):
        # Only an idle *indeterminate* bar is hidden; a determinate one shows its %.
        if self.cget("mode") == "indeterminate":
            super().configure(progress_color=self.cget("fg_color"))
        else:
            super().configure(progress_color=BLUE)

    def configure(self, require_redraw=False, **kwargs):
        super().configure(require_redraw=require_redraw, **kwargs)
        if "mode" in kwargs:
            self._idle()

    def start(self):
        super().configure(progress_color=BLUE)
        super().start()

    def stop(self):
        super().stop()
        self._idle()


class AccentButton(ctk.CTkButton):
    """Coloured action button (Run = blue, Abort = crimson) that turns dark
    while disabled, like the Battery Monitor's buttons, so it doesn't look
    clickable when it isn't."""

    COLOURS = {"primary": (BLUE, BLUE_HOVER), "danger": (ABORT, ABORT_HOVER)}

    def __init__(self, *args, kind="primary", **kwargs):
        self._accent, hover = self.COLOURS[kind]
        kwargs.setdefault("font", ctk.CTkFont(size=14, weight="bold"))
        kwargs.setdefault("height", 36)
        super().__init__(*args, hover_color=hover, border_width=0, text_color="#ffffff",
                         text_color_disabled=DISABLED, **kwargs)
        self._apply_state()

    def _apply_state(self):
        disabled = self.cget("state") == "disabled"
        super().configure(fg_color="#232b4a" if disabled else self._accent)

    def configure(self, require_redraw=False, **kwargs):
        super().configure(require_redraw=require_redraw, **kwargs)
        if "state" in kwargs:
            self._apply_state()


MIN_RECOMMENDED_FFMPEG_MAJOR = 4
OLD_FFMPEG_ERROR_SIGNATURES = ("Unrecognized option", "Option not found", "Unrecognised option")

# Standard window-suppression flags for Windows compiled GUI EXEs (e.g. PyInstaller --noconsole)
SUBPROCESS_WINDOW_KWARGS = {}
if sys.platform == "win32":
    _startupinfo = subprocess.STARTUPINFO()
    _startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _startupinfo.wShowWindow = 0  # SW_HIDE
    SUBPROCESS_WINDOW_KWARGS = {
        "startupinfo": _startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
    }

# ffplay needs its own SDL window to actually be visible (unlike the hidden
# background ffmpeg calls above). CREATE_NO_WINDOW alone only suppresses the
# text console -- it does not hide windows the process creates itself -- so
# omit the STARTUPINFO/SW_HIDE override used for silent conversions.
PLAYER_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    PLAYER_SUBPROCESS_KWARGS = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
    }

ASPECT_RATIO_STANDARDS = {
    1.0: "1:1 (Square)",
    1.333: "4:3 (Legacy / Academy)",
    1.5: "3:2 (Photography)",
    1.6: "16:10 (Widescreen Monitor)",
    1.778: "16:9 (Standard Widescreen / HD)",
    1.85: "1.85:1 (Theatrical Widescreen)",
    2.35: "2.35:1 (Cinemascope)",
    2.39: "2.39:1 (Theatrical Anamorphic)",
    2.4: "2.40:1 (Anamorphic Widescreen)",
    3.556: "32:9 (Ultra-Ultrawide)",
    0.562: "9:16 (Vertical Video / Shorts)",
    0.75: "3:4 (Vertical Multi-image)",
}


def calculate_aspect_ratio(width, height, tolerance=0.015, near_tolerance=0.06):
    gcd = math.gcd(width, height)
    raw_ratio_str = f"{width // gcd}:{height // gcd}" if gcd else "N/A"
    decimal_ratio = width / height if height else 0

    closest_match = "Unknown Custom Ratio"
    smallest_difference = tolerance
    nearest_label = None
    nearest_difference = None

    for standard_decimal, label in ASPECT_RATIO_STANDARDS.items():
        difference = abs(decimal_ratio - standard_decimal)
        if nearest_difference is None or difference < nearest_difference:
            nearest_difference = difference
            nearest_label = label
        if difference < smallest_difference:
            smallest_difference = difference
            closest_match = label

    near_miss_standard = None
    if (
        closest_match == "Unknown Custom Ratio"
        and nearest_difference is not None
        and nearest_difference < near_tolerance
    ):
        near_miss_standard = nearest_label

    return {
        "dimensions": f"{width}x{height}",
        "raw_mathematical_ratio": raw_ratio_str,
        "industry_standard_match": closest_match,
        "near_miss_standard": near_miss_standard,
    }


FFMPEG_BINARY_NAME = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
FFPROBE_BINARY_NAME = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
FFPLAY_BINARY_NAME = "ffplay.exe" if sys.platform == "win32" else "ffplay"
EASTER_EGG_VIDEO = "Ffffreddy.mp4"  # loose file shipped next to the app

VIDEO_FILTERS = [
    ("Video files", "*.mp4 *.mov *.mkv *.avi *.mxf *.m4v *.wmv"),
    ("All files", "*.*"),
]

# Friendlier labels for the common ffprobe subtitle codec names.
SUBTITLE_CODEC_NAMES = {
    "subrip": "SRT", "ass": "ASS", "ssa": "SSA", "webvtt": "WebVTT",
    "mov_text": "mov_text", "hdmv_pgs_subtitle": "PGS",
    "dvd_subtitle": "VobSub", "dvb_subtitle": "DVB",
}
# Subtitles stored as pictures rather than text.
PICTURE_SUBTITLE_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}

# Names for the ISO 639-2 language codes most often found in video files.
LANGUAGE_NAMES = {
    "eng": "English", "fre": "French", "fra": "French", "ger": "German",
    "deu": "German", "spa": "Spanish", "ita": "Italian", "por": "Portuguese",
    "dut": "Dutch", "nld": "Dutch", "swe": "Swedish", "nor": "Norwegian",
    "nob": "Norwegian", "dan": "Danish", "fin": "Finnish", "pol": "Polish",
    "cze": "Czech", "ces": "Czech", "hun": "Hungarian", "gre": "Greek",
    "ell": "Greek", "tur": "Turkish", "rus": "Russian", "ukr": "Ukrainian",
    "ara": "Arabic", "heb": "Hebrew", "hin": "Hindi", "jpn": "Japanese",
    "kor": "Korean", "chi": "Chinese", "zho": "Chinese", "tha": "Thai",
    "vie": "Vietnamese", "ind": "Indonesian", "may": "Malay", "msa": "Malay",
    "rum": "Romanian", "ron": "Romanian", "bul": "Bulgarian", "hrv": "Croatian",
    "srp": "Serbian", "slv": "Slovenian", "slo": "Slovak", "slk": "Slovak",
    "est": "Estonian", "lav": "Latvian", "lit": "Lithuanian", "ice": "Icelandic",
    "isl": "Icelandic", "per": "Persian", "fas": "Persian", "und": "Undefined",
}


class CTkRangeSlider(ctk.CTkFrame):
    def __init__(
        self,
        master,
        min_val=0.0,
        max_val=100.0,
        start_val=None,
        end_val=None,
        command=None,
        width=400,
        height=36,
        track_color=BORDER,
        range_color=BLUE,
        handle_color="#ffffff",
        handle_radius=9,
        **kwargs,
    ):
        super().__init__(master, width=width, height=height, fg_color="transparent", **kwargs)

        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.start_val = float(start_val if start_val is not None else min_val)
        self.end_val = float(end_val if end_val is not None else max_val)
        self.command = command
        self.width = width
        self.height = height
        self.radius = handle_radius
        self.padding = self.radius + 4
        self.track_color = track_color
        self.range_color = range_color
        self.handle_color = handle_color
        self.enabled = True

        canvas_color = self._apply_appearance_mode(master.cget("fg_color"))
        if canvas_color == "transparent":
            canvas_color = self._apply_appearance_mode(
                ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
            )
        self.canvas = tk.Canvas(
            self, width=width, height=height, bg=canvas_color, highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        self.active_handle = None
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _value_to_x(self, value):
        usable_width = max(1, self.width - 2 * self.padding)
        ratio = ((value - self.min_val) / (self.max_val - self.min_val)) if self.max_val > self.min_val else 0
        return self.padding + ratio * usable_width

    def _x_to_value(self, x):
        usable_width = max(1, self.width - 2 * self.padding)
        ratio = max(0.0, min(1.0, (x - self.padding) / usable_width))
        return self.min_val + ratio * (self.max_val - self.min_val)

    def _draw_slider(self):
        self.canvas.delete("all")
        center_y = self.height // 2
        track_height = 6
        start_x = self._value_to_x(self.start_val)
        end_x = self._value_to_x(self.end_val)
        self.canvas.create_line(
            self.padding, center_y, self.width - self.padding, center_y,
            width=track_height, fill=self.track_color, capstyle="round",
        )
        self.canvas.create_line(
            start_x, center_y, end_x, center_y,
            width=track_height, fill=self.range_color, capstyle="round",
        )
        for x in (start_x, end_x):
            self.canvas.create_oval(
                x - self.radius, center_y - self.radius,
                x + self.radius, center_y + self.radius,
                fill=self.handle_color, outline=self.range_color, width=2,
            )

    def _on_resize(self, event):
        self.width = max(1, event.width)
        self.height = max(1, event.height)
        self._draw_slider()

    def _on_press(self, event):
        if not self.enabled:
            return
        start_x = self._value_to_x(self.start_val)
        end_x = self._value_to_x(self.end_val)
        start_distance = abs(event.x - start_x)
        end_distance = abs(event.x - end_x)
        if start_distance < end_distance and start_distance <= self.radius * 2.5:
            self.active_handle = "start"
        elif end_distance <= self.radius * 2.5:
            self.active_handle = "end"
        else:
            self.active_handle = None

    def _on_drag(self, event):
        if not self.enabled or not self.active_handle:
            return
        minimum_gap = min(0.1, max(0.001, (self.max_val - self.min_val) / 1000))
        new_value = self._x_to_value(event.x)
        if self.active_handle == "start":
            self.start_val = max(self.min_val, min(new_value, self.end_val - minimum_gap))
        else:
            self.end_val = min(self.max_val, max(new_value, self.start_val + minimum_gap))
        self._draw_slider()
        if self.command:
            self.command(self.start_val, self.end_val)

    def _on_release(self, _event):
        self.active_handle = None

    def get_range(self):
        return self.start_val, self.end_val

    def set_range(self, start, end):
        if self.max_val < self.min_val:
            self.max_val = self.min_val
        self.start_val = max(self.min_val, min(float(start), self.max_val))
        self.end_val = max(self.start_val, min(float(end), self.max_val))
        self._draw_slider()


# Baked-in base64 copy of icon_source.jpg -- used for the splash-screen
# logo so it's always present in the compiled EXE, with no dependency on
# a loose file being shipped alongside it.
ICON_SOURCE_JPG_B64 = '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ZWN0VG9wbG9uZwAAAAAAOEJJTQPtAAAAAAAQAF/8kgABAAIAX/ySAAEAAjhCSU0EJgAAAAAADgAAAAAAAAAAAAA/gAAAOEJJTQQNAAAAAAAEAAAAWjhCSU0EGQAAAAAABAAAAB44QklNA/MAAAAAAAkAAAAAAAAAAAEAOEJJTScQAAAAAAAKAAEAAAAAAAAAAjhCSU0D9QAAAAAASAAvZmYAAQBsZmYABgAAAAAAAQAvZmYAAQChmZoABgAAAAAAAQAyAAAAAQBaAAAABgAAAAAAAQA1AAAAAQAtAAAABgAAAAAAAThCSU0D+AAAAAAAcAAA/////////////////////////////wPoAAAAAP////////////////////////////8D6AAAAAD/////////////////////////////A+gAAAAA/////////////////////////////wPoAAA4QklNBAAAAAAAAAIAADhCSU0EAgAAAAAAAgAAOEJJTQQwAAAAAAABAQA4QklNBC0AAAAAAAYAAQAAACg4QklNBAgAAAAAABAAAAABAAACQAAAAkAAAAAAOEJJTQQeAAAAAAAEAAAAADhCSU0EGgAAAAADSwAAAAYAAAAAAAAAAAAAAfQAAAH0AAAACwBpAGMAbwBuAF8AcwBvAHUAcgBjAGUAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAfQAAAH0AAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAEAAAAAAABudWxsAAAAAgAAAAZib3VuZHNPYmpjAAAAAQAAAAAAAFJjdDEAAAAEAAAAAFRvcCBsb25nAAAAAAAAAABMZWZ0bG9uZwAAAAAAAAAAQnRvbWxvbmcAAAH0AAAAAFJnaHRsb25nAAAB9AAAAAZzbGljZXNWbExzAAAAAU9iamMAAAABAAAAAAAFc2xpY2UAAAASAAAAB3NsaWNlSURsb25nAAAAAAAAAAdncm91cElEbG9uZwAAAAAAAAAGb3JpZ2luZW51bQAAAAxFU2xpY2VPcmlnaW4AAAANYXV0b0dlbmVyYXRlZAAAAABUeXBlZW51bQAAAApFU2xpY2VUeXBlAAAAAEltZyAAAAAGYm91bmRzT2JqYwAAAAEAAAAAAABSY3QxAAAABAAA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rsPDfe+os9Xa1u1nrepsQ+i/UP6rdDyBlYOE37S36N9rnWub/wAV6pcyp38utvqJKa/+Lj6vX9A+q9OPlAsysp7srIrM+x1ga1lR3Bu17KaqvVb/AKb1F1CSSSn/2QA4QklNBCEAAAAAAFcAAAABAQAAAA8AQQBkAG8AYgBlACAAUABoAG8AdABvAHMAaABvAHAAAAAUAEEAZABvAGIAZQAgAFAAaABvAHQAbwBzAGgAbwBwACAAMgAwADIAMQAAAAEAOEJJTQQGAAAAAAAHAAIBAQABAQD/4RKRaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLwA8P3hwYWNrZXQgYmVnaW49Iu+7vyIgaWQ9Ilc1TTBNcENlaGlIenJlU3pOVGN6a2M5ZCI/PiA8eDp4bXBtZXRhIHhtbG5zOng9ImFkb2JlOm5zOm1ldGEvIiB4OnhtcHRrPSJBZG9iZSBYTVAgQ29yZSA2LjAtYzAwMyA3OS4xNjQ1MjcsIDIwMjAvMTAvMTUtMTc6NDg6MzIgICAgICAgICI+IDxyZGY6UkRGIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyI+IDxyZGY6RGVzY3JpcHRpb24gcmRmOmFib3V0PSIiIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIgeG1sbnM6cGhvdG9zaG9wPSJodHRwOi8vbnMuYWRvYmUuY29tL3Bob3Rvc2hvcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdEV2dD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlRXZlbnQjIiB4bWxuczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgMjIuMSAoV2luZG93cykiIHhtcDpDcmVhdGVEYXRlPSIyMDI2LTA4LTI2VDE1OjM4OjU2KzEwOjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDI2LTA5LTIzVDE2OjM4OjU1KzEwOjAwIiB4bXA6TW9kaWZ5RGF0ZT0iMjAyNi0wOS0yM1QxNjozODo1NSsxMDowMCIgcGhvdG9zaG9wOkxlZ2FjeUlQVENEaWdlc3Q9IkU4RjE1Q0YzMkZDMTE4QTFBMjdCNjdBREM1NjRENUJBIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiBwaG90b3Nob3A6SUNDUHJvZmlsZT0iIiBkYzpmb3JtYXQ9ImltYWdlL2pwZWciIHhtcE1NOkluc3RhbmNlSUQ9InhtcC5paWQ6YTQxYjI2ZGQtODQ4Yi03ZDQwLWJjN2UtOWY1NjU3Mzc3ZTRmIiB4bXBNTTpEb2N1bWVudElEPSJhZG9iZTpkb2NpZDpwaG90b3Nob3A6ZTM1NjBjNTctN2ZmOC0yNDQ3LWJkOTEtNjhhOTNjNjQwYjIwIiB4bXBNTTpPcmlnaW5hbERvY3VtZW50SUQ9InhtcC5kaWQ6MDQyYzdkYzQtMDgwNi04NDQwLTk3YTgtOTU5MjBlNjE1YWY5Ij4gPHhtcE1NOkhpc3Rvcnk+IDxyZGY6U2VxPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0iY3JlYXRlZCIgc3RFdnQ6aW5zdGFuY2VJRD0ieG1wLmlpZDowNDJjN2RjNC0wODA2LTg0NDAtOTdhOC05NTkyMGU2MTVhZjkiIHN0RXZ0OndoZW49IjIwMjYtMDgtMjZUMTU6Mzg6NTYrMTA6MDAiIHN0RXZ0OnNvZnR3YXJlQWdlbnQ9IkFkb2JlIFBob3Rvc2hvcCAyMi4xIChXaW5kb3dzKSIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiIHN0RXZ0Omluc3RhbmNlSUQ9InhtcC5paWQ6MjkxNTc3MzctZGIxMS0xYzQ2LTgwNWYtZDgwNTk5OTJhMmE0IiBzdEV2dDp3aGVuPSIyMDI2LTA4LTI3VDE1OjAyOjU1KzEwOjAwIiBzdEV2dDpzb2Z0d2FyZUFnZW50PSJBZG9iZSBQaG90b3Nob3AgMjIuMSAoV2luZG93cykiIHN0RXZ0OmNoYW5nZWQ9Ii8iLz4gPHJkZjpsaSBzdEV2dDphY3Rpb249InNhdmVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjQ2ZWIwYzkzLWEwY2EtMTk0My04YmY0LWE2OWEwZWUyNjQ4ZiIgc3RFdnQ6d2hlbj0iMjAyNi0wOS0xMVQxMDoyODozMSsxMDowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDIyLjEgKFdpbmRvd3MpIiBzdEV2dDpjaGFuZ2VkPSIvIi8+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjb252ZXJ0ZWQiIHN0RXZ0OnBhcmFtZXRlcnM9ImZyb20gYXBwbGljYXRpb24vdm5kLmFkb2JlLnBob3Rvc2hvcCB0byBpbWFnZS9qcGVnIi8+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJkZXJpdmVkIiBzdEV2dDpwYXJhbWV0ZXJzPSJjb252ZXJ0ZWQgZnJvbSBhcHBsaWNhdGlvbi92bmQuYWRvYmUucGhvdG9zaG9wIHRvIGltYWdlL2pwZWciLz4gPHJkZjpsaSBzdEV2dDphY3Rpb249InNhdmVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjM2ZDZjNzdkLTU1Y2ItYmU0NS05MTg2LTNjY2FiY2MwNTI4YSIgc3RFdnQ6d2hlbj0iMjAyNi0wOS0xMVQxMDoyODozMSsxMDowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDIyLjEgKFdpbmRvd3MpIiBzdEV2dDpjaGFuZ2VkPSIvIi8+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJzYXZlZCIgc3RFdnQ6aW5zdGFuY2VJRD0ieG1wLmlpZDphNDFiMjZkZC04NDhiLTdkNDAtYmM3ZS05ZjU2NTczNzdlNGYiIHN0RXZ0OndoZW49IjIwMjYtMDktMjNUMTY6Mzg6NTUrMTA6MDAiIHN0RXZ0OnNvZnR3YXJlQWdlbnQ9IkFkb2JlIFBob3Rvc2hvcCAyMi4xIChXaW5kb3dzKSIgc3RFdnQ6Y2hhbmdlZD0iLyIvPiA8L3JkZjpTZXE+IDwveG1wTU06SGlzdG9yeT4gPHhtcE1NOkRlcml2ZWRGcm9tIHN0UmVmOmluc3RhbmNlSUQ9InhtcC5paWQ6NDZlYjBjOTMtYTBjYS0xOTQzLThiZjQtYTY5YTBlZTI2NDhmIiBzdFJlZjpkb2N1bWVudElEPSJhZG9iZTpkb2NpZDpwaG90b3Nob3A6YTZmNWJjMTYtZTNmZS03MjRjLWExNzktMzdjMTk1NTczZTczIiBzdFJlZjpvcmlnaW5hbERvY3VtZW50SUQ9InhtcC5kaWQ6MDQyYzdkYzQtMDgwNi04NDQwLTk3YTgtOTU5MjBlNjE1YWY5Ii8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDw/eHBhY2tldCBlbmQ9InciPz7/7gAhQWRvYmUAZIAAAAABAwAQAwIDBgAAAAAAAAAAAAAAAP/bAIQACAYGBgYGCAYGCAwIBwgMDgoICAoOEA0NDg0NEBEMDAwMDAwRDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAEJCAgJCgkLCQkLDgsNCw4RDg4ODhERDAwMDAwREQwMDAwMDBEMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwM/8IAEQgB9AH0AwEiAAIRAQMRAf/EAPsAAQACAgMBAAAAAAAAAAAAAAAHCAUGAQIEAwEBAAIDAQEAAAAAAAAAAAAAAAQGAgUHAwEQAAAFAgUCBAYCAwEBAAAAAAIDBAUGAQcAECAwNkAWMxU1CFAREhM0FzEycIAhIiMRAAIBAgIEBgoLDQgDAQEAAAECAxEEEgUAITETIDAiMkIGQEFRUmJy0rN0NRBQYXGCoiMzUxSUgZGhsZJDY5PThKS0FcGywnODoyQ0cEQl0WQSAAIAAwIHCgsHAwQDAAAAAAECABEDEgQgMCExkbFyEEBBUXEiMpJzNGHBQlJigrITM7N0gaHRosLS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'


# Baked-in base64 copies of generic-info.png and multi-language.png --
# same reasoning as ICON_SOURCE_JPG_B64 above: guarantees these icons
# exist in the compiled EXE with no loose files to forget to ship.
GENERIC_INFO_PNG_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAU0SURBVHhe7VtdbFRFFD6PPvLoo4888ugbPNDd7u7dbcEghgSjUQhEQEIK2oS47Ha79+6WoiDpQ4MJyK9AVAwEJYYfE6MxGhJ5IPBAbCKRH9uytkJDH8Z8c3Olc+623Z+ZO7fQL/le9s7OnXNm5sz5mUu0iEVEg5X5VylR7KaOwh7JjPsTOd51hcGzjuIblOxbwbtYWFief0kK4rhnqLP0mF77ZJzWDT2iraeF5EffCypcVhk8e3O4Rq8fGKdk3zQ57gXZz/L8Ev6KeAKz7LiXKdX/RAqy67ygj38TdPD35rn/uqDei75CUqUpuWo6im/xV8YDWOJYxpjl3d/5g+cCtUusmrc/m6CMe4cSfZ18CHaQzL8iZxxLHMuYD9oE+38QtPbguFQ4FG8NjreXHG9CzjgfZBSEwqH4rPeltDmRAS/Lut/S5hMToUHZ4M5vnlKueoPS+Zf5UPUDL8lWb9MH55+GBmKTxauCuvaOUEd+GR+yPqDz3MBfcg/yAcSB1Z8Frd73N2Wqa/jQ2weMzap9D2jwl/CLW+KIuCJU/PHrrTrtmiROHxjIdGU9F6F1wNJ3D941KXwAbUpYs/+hnhNCGrzqba3L/lKNyz0DNdHD27dCTBa2a9uG0fGuUe9FvQZvLgWM3RedvH2rhGHE6dDyEZmrDNGWL/4Jddw2b4lDY1xyH1cu8bZtEkck/ISmAYvfPfgo1KFG9tyZKfqUOHQq3EYL4Z4jRmkKcG9teXi6CfuF+KFhwHrCxeQdLWSuHx5r/GiEtnRa/TgQp0LaHZ3fIGKvYM/wDp4Hbjg6SelyDxdZBULMqMLaqAlXOVV+yEV+BqSdUuVJI8kMhbMdgwZPgoC5gRol8ku56D6QbkLGhf9JOy0q4L1T05TsK3HRfSABiRwc/5N2WlQAvMOMd5OL7vv8SGQaX/6gRQWAyGIhwFOAJCPCSN7YCC0r4J3D/9LKwiZVAfgBD3hjI7SsgPfPCkqWBlQFoCKDogRvbISWFYBaBQo2CvADHvDGRmhZAfBz4O8oQNUFhQfe2AgtK8D7UVC6fJcrIEL/37ICUKpDvVJBqr+mL+c3Hy0rAEwUhaoALAksDd7QCC0rAL4OKs8KIg2CLCugblD0wp8CcAzgIPDGRmhZAYh3EPcoSBS208ZjU6HGRmhZATu+whYYUhWAayi4icEbG6FlBWw+MU2JwoeqAmQypPRirACk++tWkSM7CSwqoO4JECAyO2BRAXX3fwB538d7vlNi/vW7Oe4gRhITWFJA3RiAA3lz5M/5n7XSkgK2n52mtDvMRVaB3CAqKEYDIwsKgP+f8WqN3RcwvgosKGDb6SfkeAe4qLPDqC2IWAEN1wVnwmiNMGIFNFQTrIfIHCODRI4jWxlpbvYDwD3OVv6U3hPveCEQx17XwINwEaQZoJC4avBey1febXJep6dR5Co5WvvpaOgFceaGz2uUKfdyUVoHOnv3sIEbYwa44+vHlK2c5CK0D6faT+uGRmO9HTDzXdVzfOj6gIvIsAlxM4yYFOx5rct+NsAw4nSIyxGJow6TosXgNQockfATcKPEaNwwBzHrm45PynN+1msvpoFrNXAzMZCobAMCG/j2aXecMu6e1pwcncAAMBAMCCGnKUVAcNQuENUhsIndt4QYEOJtJB1gkHrO+Tk4LkgzxPZCP4hL/A8pzzQW0toGDJJTPiITkMjCIhWNfFzwlWi9u0jBMwiMyxq4rouiLfpp+rJznIAUNPLwSEYG3wljNlGhncn/vyMuH5E3VrR88bGIOfEfNzM3Xr0DPioAAAAASUVORK5CYII='
MULTI_LANGUAGE_PNG_B64 = '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'


class CTkToolTip:
    """Small hover tooltip -- a borderless Toplevel that tracks the cursor
    over `widget` and shows a single line of `text` after a short delay."""

    def __init__(self, widget, text, delay_ms=400):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip_window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip_window is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        widget_top = self.widget.winfo_rooty()

        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass

        label = tk.Label(
            tw, text=self.text, justify="left",
            background=CARD_2, foreground=TEXT,
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BORDER,
            font=("Segoe UI", 9), padx=8, pady=4,
        )
        label.pack()

        tw.update_idletasks()
        x -= tw.winfo_width() // 2
        # Positioned above the widget (rather than below) so the cursor,
        # which sits over the widget to trigger the hover, doesn't obscure it.
        y = widget_top - tw.winfo_height() - 6
        tw.wm_geometry(f"+{max(0, x)}+{max(0, y)}")
        self._tip_window = tw

    def _hide(self, _event=None):
        self._cancel()
        if self._tip_window is not None:
            self._tip_window.destroy()
            self._tip_window = None


class FFmpegToolkit(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"FFmpeg Toolkit - (ver: {APP_VERSION} - build: {BUILD_DATE})")

        # The .exe carries its own copy of the icon (build.bat bundles it with
        # --add-data), unpacked to sys._MEIPASS; a loose app_icon.ico next to
        # the .exe is still used if the bundled one is missing.
        if getattr(sys, "frozen", False):
            icon_path = pathlib.Path(getattr(sys, "_MEIPASS", "")) / "app_icon.ico"
            if not icon_path.exists():
                icon_path = pathlib.Path(sys.executable).parent / "app_icon.ico"
        else:
            icon_path = pathlib.Path(__file__).parent / "app_icon.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        self.geometry("1150x720")
        self.minsize(950, 600)

        # The dashboard theme is applied before this window is created (see __main__).

        if getattr(sys, "frozen", False):
            self._app_dir = os.path.dirname(sys.executable)
        else:
            self._app_dir = os.path.dirname(os.path.abspath(__file__))
        self._settings_path = os.path.join(self._app_dir, "FFT-settings.json")

        self._info_icon_pil = None
        self._info_icon_image = None
        self._info_icon_image_lg = None
        self._inline_icon_refs = []
        try:
            info_pil = PilImage.open(io.BytesIO(base64.b64decode(GENERIC_INFO_PNG_B64)))
            self._info_icon_pil = info_pil
            self._info_icon_image = ctk.CTkImage(
                light_image=info_pil, dark_image=info_pil, size=(20, 20)
            )
            self._info_icon_image_lg = ctk.CTkImage(
                light_image=info_pil, dark_image=info_pil, size=(40, 40)
            )
        except Exception:
            self._info_icon_pil = None
            self._info_icon_image = None
            self._info_icon_image_lg = None

        self._multi_lang_icon_image = None
        try:
            multi_lang_pil = PilImage.open(io.BytesIO(base64.b64decode(MULTI_LANGUAGE_PNG_B64)))
            icon_h = 28
            icon_w = round(multi_lang_pil.width * icon_h / multi_lang_pil.height)
            self._multi_lang_icon_image = ctk.CTkImage(
                light_image=multi_lang_pil, dark_image=multi_lang_pil, size=(icon_w, icon_h)
            )
        except Exception:
            self._multi_lang_icon_image = None

        self._app_logo_image = None
        try:
            logo_pil = PilImage.open(io.BytesIO(base64.b64decode(ICON_SOURCE_JPG_B64)))
            self._app_logo_image = ctk.CTkImage(
                light_image=logo_pil, dark_image=logo_pil, size=(110, 110)
            )
        except Exception:
            self._app_logo_image = None

        self._settings = self._load_settings()

        # Shared by the splash-screen checkbox and the Settings tab checkbox,
        # so both always agree; either one saves the choice immediately.
        self._show_splash_var = ctk.BooleanVar(value=self._settings.get("show_splash", True))

        def _save_show_splash(*_args):
            self._settings["show_splash"] = self._show_splash_var.get()
            self._save_settings()

        self._show_splash_var.trace_add("write", _save_show_splash)

        self._ffmpeg_path = self._resolve_ffmpeg_path()
        self._ffprobe_path = self._resolve_ffprobe_path()
        self._ffplay_path = self._resolve_ffplay_path()
        self._active_process = None
        self._trim_play_process = None
        self._trim_play_window_title = None
        self._trim_play_hwnd = None
        self._abort_event = threading.Event()
        # Worker threads must never touch Tk widgets directly (on Linux/X11
        # that crashes the app). They queue callables here instead, and
        # _pump_ui_queue runs them on the main thread.
        self._ui_queue = queue.Queue()
        self._operation_running = False
        self._old_ffmpeg_warning_shown = False
        self._last_run_suspected_old_ffmpeg = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)
        self._pump_job = self.after(30, self._pump_ui_queue)

    def _run_on_main(self, fn):
        """Thread-safe way to run fn on the Tk main thread."""
        self._ui_queue.put(fn)

    def _pump_ui_queue(self):
        # Cap the work per tick so a flood of ffmpeg output can't freeze the UI.
        for _ in range(500):
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception as exc:
                print(f"UI callback error: {exc}", file=sys.stderr)
        self._pump_job = self.after(30, self._pump_ui_queue)

    def _on_app_close(self):
        self._stop_trim_playback()
        try:
            self.after_cancel(self._pump_job)
        except (AttributeError, tk.TclError):
            pass
        self.destroy()

    def _stop_trim_playback(self):
        """Terminate any ffplay range-preview process that is still running."""
        process = self._trim_play_process
        self._trim_play_process = None
        self._trim_play_window_title = None
        self._trim_play_hwnd = None
        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

            def wait_and_kill():
                try:
                    process.wait(timeout=2)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

            threading.Thread(target=wait_and_kill, daemon=True).start()

    def _find_ffplay_hwnd(self, window_title):
        if sys.platform != "win32" or not window_title:
            return None
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, window_title)
            if hwnd:
                return hwnd
            found = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            def enum_handler(candidate, _lparam):
                length = user32.GetWindowTextLengthW(candidate)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(candidate, buf, length + 1)
                    if buf.value.startswith(window_title):
                        found.append(candidate)
                return True

            user32.EnumWindows(enum_handler, 0)
            return found[0] if found else None
        except Exception:
            return None

    def _embed_external_window(self, hwnd, container):
        """Reparent an external top-level window (ffplay's SDL window) into a
        Tk widget so it renders inside our own preview area. Windows-only."""
        if sys.platform != "win32":
            return False
        try:
            import ctypes

            user32 = ctypes.windll.user32
            GWL_STYLE = -16
            WS_CHILD = 0x40000000
            WS_POPUP = 0x80000000
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000
            WS_BORDER = 0x00800000
            WS_DLGFRAME = 0x00400000
            SWP_FRAMECHANGED = 0x0020
            SWP_NOZORDER = 0x0004
            SWP_SHOWWINDOW = 0x0040

            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_BORDER | WS_DLGFRAME)
            style |= WS_CHILD
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            container_hwnd = container.winfo_id()
            user32.SetParent(hwnd, container_hwnd)

            width = max(container.winfo_width(), 1)
            height = max(container.winfo_height(), 1)
            user32.SetWindowPos(
                hwnd, 0, 0, 0, width, height,
                SWP_FRAMECHANGED | SWP_NOZORDER | SWP_SHOWWINDOW,
            )
            return True
        except Exception:
            return False

    def _bring_ffplay_to_front(self, window_title, attempts=10):
        if sys.platform != "win32":
            return

        def worker():
            import ctypes

            user32 = ctypes.windll.user32
            for _ in range(attempts):
                hwnd = self._find_ffplay_hwnd(window_title)
                if hwnd:
                    try:
                        SW_RESTORE = 9
                        user32.ShowWindow(hwnd, SW_RESTORE)
                        user32.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                    return
                time.sleep(0.2)

        threading.Thread(target=worker, daemon=True).start()

    def _send_ffplay_pause_toggle(self, hwnd):
        """Best-effort: post a Spacebar keypress to the ffplay preview window
        to toggle play/pause. Windows-only; returns False if it can't be done.
        Takes the hwnd directly rather than searching by title, because once
        a window is embedded (reparented as a child) it's no longer a
        top-level window and FindWindow/EnumWindows can no longer see it."""
        return self._send_ffplay_key(hwnd, 0x20)  # VK_SPACE

    def _send_ffplay_key(self, hwnd, vk_code):
        """Post a virtual-key press to the given window. Windows-only."""
        if sys.platform != "win32" or not hwnd:
            return False
        try:
            import ctypes

            user32 = ctypes.windll.user32
            WM_KEYDOWN = 0x0100
            WM_KEYUP = 0x0101
            MAPVK_VK_TO_VSC = 0
            scan_code = user32.MapVirtualKeyW(vk_code, MAPVK_VK_TO_VSC)
            lparam_down = 1 | (scan_code << 16)
            lparam_up = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)
            user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, lparam_down)
            user32.PostMessageW(hwnd, WM_KEYUP, vk_code, lparam_up)
            return True
        except Exception:
            return False

    def _unembed_window(self, hwnd):
        """Reverse of _embed_external_window: restore the window as a normal,
        bordered top-level window and bring it to the front. Windows-only."""
        if sys.platform != "win32" or not hwnd:
            return False
        try:
            import ctypes

            user32 = ctypes.windll.user32
            GWL_STYLE = -16
            WS_CHILD = 0x40000000
            WS_POPUP = 0x80000000
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000
            WS_SYSMENU = 0x00080000
            WS_MINIMIZEBOX = 0x00020000
            WS_MAXIMIZEBOX = 0x00010000
            SWP_FRAMECHANGED = 0x0020
            SWP_NOZORDER = 0x0004
            SWP_SHOWWINDOW = 0x0040
            SW_RESTORE = 9

            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~WS_CHILD
            style |= (
                WS_POPUP | WS_CAPTION | WS_THICKFRAME
                | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
            )
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            user32.SetParent(hwnd, None)
            user32.SetWindowPos(
                hwnd, 0, 100, 100, 960, 600,
                SWP_FRAMECHANGED | SWP_NOZORDER | SWP_SHOWWINDOW,
            )
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False

    def _resolve_ffmpeg_path(self):
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

    def _resolve_ffprobe_path(self):
        candidates = [os.path.join(self._app_dir, FFPROBE_BINARY_NAME)]
        if self._ffmpeg_path:
            candidates.append(os.path.join(os.path.dirname(self._ffmpeg_path), FFPROBE_BINARY_NAME))
        saved_path = self._settings.get("ffprobe_path", "")
        if saved_path:
            candidates.append(saved_path)
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return shutil.which("ffprobe")

    def _resolve_ffplay_path(self):
        candidates = [os.path.join(self._app_dir, FFPLAY_BINARY_NAME)]
        if self._ffmpeg_path:
            candidates.append(os.path.join(os.path.dirname(self._ffmpeg_path), FFPLAY_BINARY_NAME))
        saved_path = self._settings.get("ffplay_path", "")
        if saved_path:
            candidates.append(saved_path)
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return shutil.which("ffplay")

    def _get_ffmpeg_version(self, path):
        try:
            result = subprocess.run(
                [path, "-version"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True,
                errors="replace", timeout=5,
                **SUBPROCESS_WINDOW_KWARGS
            )
            first_line = result.stdout.splitlines()[0] if result.stdout else ""
            match = re.search(r"ffmpeg version (\S+)", first_line)
            return match.group(1) if match else "unknown"
        except Exception:
            return "unknown"

    def _maybe_prompt_alt_ffmpeg(self):
        path = getattr(self, "_pending_ffmpeg_confirm", None)
        if not path:
            self._check_ffmpeg_version_and_warn()
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

        self._set_ffmpeg_status(True)
        self._refresh_settings_ffmpeg_display()
        self._check_ffmpeg_version_and_warn()

    def _check_ffmpeg_version_and_warn(self):
        if not self._ffmpeg_path or not os.path.isfile(self._ffmpeg_path):
            return
        version_str = self._get_ffmpeg_version(self._ffmpeg_path)
        match = re.match(r"(\d+)\.(\d+)", version_str)
        if not match:
            return
        if int(match.group(1)) < MIN_RECOMMENDED_FFMPEG_MAJOR:
            self._show_old_ffmpeg_warning(f"Detected version: {version_str}")

    def _show_old_ffmpeg_warning(self, detail=None):
        if self._old_ffmpeg_warning_shown:
            return
        self._old_ffmpeg_warning_shown = True

        dialog = ctk.CTkToplevel(self)
        dialog.title("Old FFmpeg Version Detected")
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text="\u26A0\uFE0F", font=ctk.CTkFont(size=32)).pack(pady=(20, 5))
        ctk.CTkLabel(
            dialog,
            text=(
                "It seems you're running an old version of FFmpeg, which is "
                "incompatible with some operations in the Toolkit."
            ),
            wraplength=380, justify="center",
        ).pack(padx=25, pady=(0, 8))

        if detail:
            ctk.CTkLabel(
                dialog, text=detail, wraplength=380, justify="center",
                font=ctk.CTkFont(size=11), text_color=MUTED,
            ).pack(padx=25, pady=(0, 10))

        ctk.CTkButton(
            dialog, text="Download the latest FFmpeg (ffmpeg.org)",
            command=lambda: webbrowser.open("https://www.ffmpeg.org")
        ).pack(padx=25, pady=(5, 5), fill="x")

        ctk.CTkButton(
            dialog, text="Dismiss", fg_color="transparent", border_width=1,
            command=dialog.destroy
        ).pack(padx=25, pady=(0, 20), fill="x")

        dialog.transient(self)
        dialog.after(10, dialog.lift)
        dialog.grab_set()

    def _refresh_settings_ffmpeg_display(self):
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
            text_color=MUTED if resolved else AMBER,
        )

    def _set_ffmpeg_status(self, found):
        self._ffmpeg_ok = found
        if found:
            self._status_dot.configure(text_color=GREEN)
            self._status_label.configure(text="ffmpeg found")
        else:
            self._status_label.configure(text="ffmpeg not found -- set it in Settings")
            self._blink_status_dot()
        self._set_sidebar_enabled(found)

    def _set_ffprobe_status(self, found):
        if found:
            self._ffprobe_status_dot.configure(text_color=GREEN)
            self._ffprobe_status_label.configure(text="ffprobe found")
        else:
            self._ffprobe_status_dot.configure(text_color=AMBER)
            self._ffprobe_status_label.configure(text="ffprobe not found")

    def _set_sidebar_enabled(self, enabled):
        if not hasattr(self, "_nav_buttons"):
            return
        for name, btn in self._nav_buttons.items():
            if name == "Settings":
                continue
            btn.configure(state="normal" if enabled else "disabled")

    def _set_operation_running(self, running):
        self._operation_running = running
        if running:
            for btn in self._nav_buttons.values():
                btn.configure(state="disabled")
        else:
            self._set_sidebar_enabled(getattr(self, "_ffmpeg_ok", False))
            self._close_abort_popup()

    def _show_abort_popup(self):
        if getattr(self, "_abort_popup", None) is not None:
            return

        try:
            popup = ctk.CTkToplevel(self)
            popup.title("Please Wait")
            popup.geometry("320x140")
            popup.resizable(False, False)

            self.update_idletasks()
            parent_x = self.winfo_x()
            parent_y = self.winfo_y()
            parent_w = self.winfo_width()
            parent_h = self.winfo_height()
            pos_x = parent_x + (parent_w - 320) // 2
            pos_y = parent_y + (parent_h - 140) // 2
            popup.geometry(f"320x140+{max(0, pos_x)}+{max(0, pos_y)}")

            popup.transient(self)
            popup.protocol("WM_DELETE_WINDOW", lambda: None)

            # On Linux, grab_set() fails on a window that isn't mapped yet,
            # which used to leave this popup orphaned. Grab once it's visible.
            def safe_grab():
                try:
                    if popup.winfo_exists():
                        popup.grab_set()
                except tk.TclError:
                    pass
            popup.after(100, safe_grab)

            lbl = ctk.CTkLabel(
                popup,
                text="Aborting operation...\nPlease wait.",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#ffffff",
            )
            lbl.pack(pady=(20, 10))

            progress = ctk.CTkProgressBar(popup, mode="indeterminate", width=240)
            progress.pack(pady=(0, 15))
            progress.start()

            self._abort_popup = popup
            self.update_idletasks()
        except Exception:
            self._abort_popup = None

    def _close_abort_popup(self):
        popup = getattr(self, "_abort_popup", None)
        if popup is not None:
            try:
                popup.grab_release()
                popup.destroy()
            except Exception:
                pass
            self._abort_popup = None

    def _abort_current_operation(self):
        if not self._operation_running:
            return

        self._abort_event.set()
        self._show_abort_popup()

        def kill_worker():
            process = self._active_process
            if process is not None and process.poll() is None:
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/f", "/t", "/pid", str(process.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                            **SUBPROCESS_WINDOW_KWARGS
                        )
                    else:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

            start_time = time.time()
            while self._operation_running and (time.time() - start_time < 5.0):
                time.sleep(0.05)

            self._run_on_main(self._close_abort_popup)

        threading.Thread(target=kill_worker, daemon=True).start()

    def _blink_status_dot(self):
        if getattr(self, "_ffmpeg_ok", False):
            return
        self._blink_on = not getattr(self, "_blink_on", False)
        self._status_dot.configure(text_color=RED if self._blink_on else "#4a1a28")
        self.after(600, self._blink_status_dot)

    def _load_settings(self):
        defaults = {
            "default_output_folder": "",
            "remember_last_folder": True,
            "last_input_folder": "",
            "ffmpeg_path": "",
            "ffprobe_path": "",
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
        if self._settings.get("default_output_folder") and os.path.isdir(
            self._settings["default_output_folder"]
        ):
            return self._settings["default_output_folder"]
        return os.path.dirname(input_path)

    def _get_initial_dir(self):
        if self._settings.get("remember_last_folder") and self._settings.get(
            "last_input_folder"
        ):
            folder = self._settings["last_input_folder"]
            if os.path.isdir(folder):
                return folder
        return ""

    def _remember_folder(self, path):
        if self._settings.get("remember_last_folder") and path:
            self._settings["last_input_folder"] = os.path.dirname(path)
            self._save_settings()

    def _dark_menu(self):
        """A drop-down / right-click menu in the dashboard colours."""
        return Menu(
            self, tearoff=0, bg=CARD_2, fg=TEXT, activebackground=SELECTED,
            activeforeground="#ffffff", disabledforeground=DISABLED,
            borderwidth=1, relief="flat", activeborderwidth=0,
            font=(UI_FONT or "TkMenuFont", 10),
        )

    def _build_menu_bar(self):
        # Windows draws the native menu bar itself, always light, so the menu
        # bar is a strip of buttons that open dark drop-down menus instead.
        strip = self._menu_strip

        def add_menu(label, menu, key):
            btn = ctk.CTkButton(
                strip, text=label, width=10, height=26, corner_radius=6,
                fg_color="transparent", hover_color=CARD_2, border_width=0,
                text_color=TEXT, font=ctk.CTkFont(size=13),
            )
            btn.pack(side="left", padx=(0, 2))

            def open_menu(_event=None):
                btn.configure(fg_color=CARD_2)
                try:
                    menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height() + 2)
                    menu.grab_release()
                    btn.configure(fg_color="transparent")
                except tk.TclError:
                    pass  # the window was closed while the menu was open
                return "break"

            btn.configure(command=open_menu)
            self.bind_all(f"<Alt-{key}>", open_menu)
            self.bind_all(f"<Alt-{key.upper()}>", open_menu)

        file_menu = self._dark_menu()
        file_menu.add_command(label="About",
                              command=lambda: self._build_welcome_splash(at_startup=False))
        file_menu.add_separator()
        # Close after the menu has finished closing, not from inside it.
        file_menu.add_command(label="Exit", command=lambda: self.after(10, self._on_app_close))
        add_menu("File", file_menu, "f")

        operations_menu = self._dark_menu()
        mnemonic_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        item_index = 0
        for section_index, (_section_label, items) in enumerate(self._tool_sections):
            if section_index > 0:
                operations_menu.add_separator()
            for name, _icon, _builder in items:
                letter = mnemonic_letters[item_index % len(mnemonic_letters)]
                item_index += 1
                label = f"{letter}. {name}"
                operations_menu.add_command(
                    label=label, underline=0,
                    command=lambda n=name: self._show_panel(n)
                )
        add_menu("Operations", operations_menu, "o")

    def _build_ui(self):
        self._menu_strip = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._menu_strip.pack(fill="x", padx=8, pady=(4, 0))

        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=16, pady=(6, 10))

        self._add_title_icon(top_frame)

        title_label = ctk.CTkLabel(
            top_frame,
            text="FFmpeg Toolkit",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(side="left")

        version_label = ctk.CTkLabel(
            top_frame,
            text=f"  {APP_VERSION} - {BUILD_DATE}",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        )
        version_label.pack(side="left", anchor="s", pady=(0, 3))

        status_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        status_frame.pack(side="right")

        self._status_dot, self._status_label = status_chip(status_frame)
        self._ffprobe_status_dot, self._ffprobe_status_label = status_chip(status_frame)

        body_frame = ctk.CTkFrame(self, fg_color="transparent")
        body_frame.pack(fill="both", expand=True, padx=0, pady=0)

        sidebar = ctk.CTkScrollableFrame(
            body_frame, width=190, corner_radius=14,
            fg_color=CARD, border_width=1, border_color=BORDER,
        )
        sidebar.pack(side="left", fill="y", padx=(12, 0), pady=(0, 12))

        self._content_panel = ctk.CTkFrame(body_frame, fg_color="transparent")
        self._content_panel.pack(side="left", fill="both", expand=True, padx=12, pady=(0, 12))

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
            self._restore_empty_help(self._panels[name])
            for btn_name, btn in self._nav_buttons.items():
                if btn_name == name:
                    btn.configure(fg_color=SELECTED, text_color="#ffffff")
                else:
                    btn.configure(fg_color="transparent", text_color=TEXT)

        self._show_panel = _show_panel

        self._tool_sections = [
            ("VIDEO", [
                ("Inspect File",        "\U0001F50D", self._build_inspect_tab),
                ("Remux to MP4",        "\U0001F3A5", self._build_remux_mp4_tab),
                ("Quick Fix",           "\U0001F527", lambda p: self._build_fix_tab(p, "quick")),
                ("Stubborn Fix",        "\U0001F528", lambda p: self._build_fix_tab(p, "stubborn")),
                ("Fix Timestamps",      "\u23F1",     self._build_fix_timestamps_tab),
                ("Proxy Creator",       "\U0001F4E6", self._build_proxy_tab),
                ("Video Scaler",        "\U0001F4D0", self._build_scaler_tab),
                ("ProRes Export",       "\U0001F3AC", self._build_prores_tab),
                ("Batch ProRes Export", "\U0001F4C2", self._build_batch_prores_tab),
                ("Clip & Track Editor", "\u2702\uFE0F", self._build_trim_clip_tab),
                ("Still Frame",         "\U0001F5BC", self._build_still_frame_tab),
            ]),
            ("AUDIO", [
                ("Extract Audio",       "\U0001F3B5", self._build_extract_audio_tab),
                ("Strip Audio",         "\U0001F507", self._build_strip_audio_tab),
                ("Audio Accessibility", "\u267F",     self._build_audio_accessibility_tab),
                ("Batch Audio Convert", "\U0001F4C2", self._build_batch_audio_tab),
            ]),
            ("SUBTITLES", [
                ("Subtitles Extractor", "\U0001F4AC", self._build_subtitles_extractor_tab),
            ]),
            ("TOOLS", [
                ("Custom Command",      "\u2328\uFE0F", self._build_custom_tab),
            ]),
        ]
        self._utility_items = [
            ("Settings", "\u2699\uFE0F", self._build_settings_tab),
        ]

        self._build_menu_bar()

        for _, items in self._tool_sections:
            for name, _icon, builder in items:
                _build_panel(name, builder)
        for name, _icon, builder in self._utility_items:
            _build_panel(name, builder)

        ctk.CTkLabel(sidebar, text="Tools",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 2), padx=10, anchor="w")

        def _add_nav_button(name, icon):
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon}  {name}",
                font=ctk.CTkFont(size=12),
                anchor="w", width=180, height=32,
                corner_radius=8, border_width=0,
                fg_color="transparent",
                text_color=TEXT,
                hover_color=CARD_2,
                command=lambda n=name: _show_panel(n)
            )
            btn.pack(fill="x", padx=4, pady=1)
            self._nav_buttons[name] = btn

        for section_label, items in self._tool_sections:
            ctk.CTkLabel(sidebar, text=section_label,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=MUTED, anchor="w").pack(
                         fill="x", padx=10, pady=(10, 2))
            for name, icon, _builder in items:
                _add_nav_button(name, icon)

        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER, corner_radius=0).pack(
            fill="x", padx=10, pady=(10, 6))

        for name, icon, _builder in self._utility_items:
            _add_nav_button(name, icon)

        ffmpeg_found = bool(self._ffmpeg_path) and os.path.isfile(self._ffmpeg_path)
        self._set_ffmpeg_status(ffmpeg_found)
        self._set_ffprobe_status(
            bool(self._ffprobe_path) and os.path.isfile(self._ffprobe_path)
        )
        _show_panel("Quick Fix" if ffmpeg_found else "Settings")
        if self._show_splash_var.get():
            self._build_welcome_splash()
        else:
            # Dismissing the splash normally triggers this, so do it directly.
            self.after(150, self._maybe_prompt_alt_ffmpeg)

    def _add_title_icon(self, top_frame):
        try:
            mini_data = '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'
            mini_pil = PilImage.open(io.BytesIO(base64.b64decode(mini_data)))
            mini_img = ctk.CTkImage(light_image=mini_pil, dark_image=mini_pil, size=(28, 28))
            lbl_icon = ctk.CTkLabel(top_frame, image=mini_img, text="")
            lbl_icon.pack(side="left", padx=(0, 6))
            lbl_icon.bind("<Double-Button-1>", self._play_easter_egg)
        except Exception:
            pass

    def _play_easter_egg(self, event=None):
        """Easter egg: double-clicking the title-bar icon plays the loose
        EASTER_EGG_VIDEO file shipped next to the app in the system's default
        player. Silently does nothing if the file is missing or won't open."""
        try:
            path = os.path.join(self._app_dir, EASTER_EGG_VIDEO)
            if not os.path.isfile(path):
                return
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _build_welcome_splash(self, at_startup=True):
        """The welcome screen, overlaid on the whole window. Shown at startup
        (unless turned off) and again from File > About (at_startup=False),
        which skips the startup ffmpeg checks when it's closed."""
        existing = getattr(self, "_welcome_frame", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return

        welcome_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        welcome_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        welcome_frame.lift()
        self._welcome_frame = welcome_frame

        def _dismiss_welcome(event=None):
            if self._welcome_frame is None:
                return
            self._welcome_frame = None
            try:
                self.unbind("<Escape>")
                welcome_frame.destroy()
            except Exception:
                pass
            if at_startup:
                self.after(150, self._maybe_prompt_alt_ffmpeg)

        self.bind("<Escape>", _dismiss_welcome)
        # Clicks on the background count as "anywhere"; Tk doesn't pass clicks
        # on the checkbox or link up to their parents, so those stay usable.
        welcome_frame.bind("<Button-1>", _dismiss_welcome)

        inner = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        inner.place(relx=0.5, rely=0.45, anchor="center")
        inner.bind("<Button-1>", _dismiss_welcome)
        verb = "begin" if at_startup else "continue"

        if self._app_logo_image is not None:
            lbl_logo = ctk.CTkLabel(inner, text="", image=self._app_logo_image)
            lbl_logo.pack(pady=(0, 10))
            lbl_logo.bind("<Button-1>", _dismiss_welcome)

        lbl_title = ctk.CTkLabel(inner, text="FFmpeg Toolkit",
            font=ctk.CTkFont(size=28, weight="bold"), text_color="#ffffff")
        lbl_title.pack()
        lbl_title.bind("<Button-1>", _dismiss_welcome)

        lbl_click = ctk.CTkLabel(inner, text=f"Click anywhere to {verb}",
            font=ctk.CTkFont(size=14), text_color=MUTED)
        lbl_click.pack(pady=(8, 0))
        lbl_click.bind("<Button-1>", _dismiss_welcome)

        ffmpeg_found = bool(self._ffmpeg_path) and os.path.isfile(self._ffmpeg_path)
        if not ffmpeg_found:
            lbl_warn = ctk.CTkLabel(inner,
                text="\u26A0\uFE0F  ffmpeg not found -- place it next to this app, add it to PATH, or set it in Settings",
                font=ctk.CTkFont(size=12), text_color=AMBER)
            lbl_warn.pack(pady=(12, 0))

        ctk.CTkButton(
            inner,
            text=f"Click here to {verb}  \u25B6",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=BLUE,
            hover_color=BLUE_HOVER,
            border_width=0,
            text_color="#ffffff",
            corner_radius=8,
            command=_dismiss_welcome
        ).pack(pady=(22, 0), ipadx=10, ipady=4)

        ctk.CTkLabel(
            inner,
            text=f"Version {APP_VERSION}  \u2022  Built {BUILD_DATE}",
            font=ctk.CTkFont(size=11),
            text_color=FAINT
        ).pack(pady=(14, 0))

        ctk.CTkLabel(
            inner,
            text="Developed by Adrian Newington  |  Optimized Build",
            font=ctk.CTkFont(size=11),
            text_color=FAINT
        ).pack(pady=(4, 0))

        ctk.CTkLabel(
            inner,
            text="JELLY-JAZZ SOFTWARE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=FAINT
        ).pack(pady=(2, 0))

        lbl_github = ctk.CTkLabel(
            inner,
            text="github.com/SunflowerGUY",
            font=ctk.CTkFont(size=11, underline=True),
            text_color=LINK,
            cursor="hand2"
        )
        lbl_github.pack(pady=(2, 0))
        lbl_github.bind("<Button-1>", lambda _e: webbrowser.open("https://github.com/SunflowerGUY"))

        # Acknowledgement: this app is a front end -- FFmpeg does the real work.
        powered = ctk.CTkFrame(inner, fg_color="transparent")
        powered.pack(pady=(20, 0))
        # Plain U+2665 heart: Tk can't draw the colour emoji version.
        ctk.CTkLabel(
            powered, text="♥", font=ctk.CTkFont(size=14), text_color=RED
        ).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            powered,
            text="Powered by FFmpeg",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=MUTED
        ).pack(side="left")

        ctk.CTkLabel(
            inner,
            text="This toolkit is simply a wrapper. The real magic is the work of the FFmpeg\n"
                 "developers and community, whose generous open-source efforts have opened\n"
                 "doors for developers everywhere to build tools like this one. Thank you.",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
            justify="center"
        ).pack(pady=(4, 0))

        lbl_link = ctk.CTkLabel(
            inner,
            text="ffmpeg.org",
            font=ctk.CTkFont(size=11, underline=True),
            text_color=LINK,
            cursor="hand2"
        )
        lbl_link.pack(pady=(2, 0))
        lbl_link.bind("<Button-1>", lambda _e: webbrowser.open("https://ffmpeg.org"))

        ctk.CTkLabel(
            inner,
            text="FFmpeg is a trademark of Fabrice Bellard, originator of the FFmpeg project.",
            font=ctk.CTkFont(size=9),
            text_color=FAINT
        ).pack(pady=(2, 0))

        ctk.CTkCheckBox(
            inner,
            text="Show this screen at startup",
            variable=self._show_splash_var,
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
            checkbox_width=16, checkbox_height=16,
        ).pack(pady=(18, 0))

    def _make_info_icon(self, parent, title, body_text):
        """A small (i) icon that shows a 'Click here for more info' tooltip
        on hover and opens a help dialog with `body_text` when clicked."""
        icon = ctk.CTkButton(
            parent,
            text="" if self._info_icon_image else "ℹ️",
            image=self._info_icon_image,
            width=26, height=26, corner_radius=13,
            fg_color="transparent", hover_color=HOVER, border_width=0,
            font=ctk.CTkFont(size=15),
            command=lambda: self._show_info_dialog(title, body_text),
        )
        CTkToolTip(icon, "Click here for more info")
        return icon

    def _center_next_messagebox(self, title, text_width=None):
        """Windows centres native message boxes on the screen, not the app.
        Call just before messagebox.show*(title, ...): a watcher thread finds
        the box by its title as soon as it opens and moves it over the app.

        Windows also wraps message box text at a fixed, narrow width, so long
        messages come out tall and skinny. Pass text_width (pixels) to widen
        the box so its text wraps at that width instead."""
        if sys.platform != "win32":
            return
        self.update_idletasks()
        cx = self.winfo_rootx() + self.winfo_width() // 2
        cy = self.winfo_rooty() + self.winfo_height() // 2

        def widen(ctypes, wintypes, user32, hwnd):
            gdi32 = ctypes.windll.gdi32
            user32.GetDlgItem.restype = wintypes.HWND
            user32.FindWindowExW.restype = wintypes.HWND
            user32.GetDC.restype = wintypes.HDC
            user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
            user32.SendMessageW.restype = ctypes.c_ssize_t
            user32.DrawTextW.argtypes = [
                wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
                ctypes.POINTER(wintypes.RECT), wintypes.UINT,
            ]
            gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
            gdi32.SelectObject.restype = wintypes.HGDIOBJ

            text = user32.GetDlgItem(hwnd, 0xFFFF)  # the message's static text
            if not text:
                return False

            def rect_in_dialog(ctl):
                r = wintypes.RECT()
                user32.GetWindowRect(ctl, ctypes.byref(r))
                user32.MapWindowPoints(None, hwnd, ctypes.byref(r), 2)
                return r

            old = rect_in_dialog(text)
            old_w = old.right - old.left
            if text_width <= old_w:
                return False

            length = user32.GetWindowTextLengthW(text)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(text, buf, length + 1)
            hdc = user32.GetDC(text)
            font = user32.SendMessageW(text, 0x0031, 0, 0)  # WM_GETFONT
            prev = gdi32.SelectObject(hdc, font)

            def wrapped_height(width):
                r = wintypes.RECT(0, 0, width, 0)
                # DT_CALCRECT | DT_WORDBREAK | DT_EXPANDTABS | DT_NOPREFIX
                user32.DrawTextW(hdc, buf.value, -1, ctypes.byref(r), 0x400 | 0x10 | 0x40 | 0x800)
                return r.bottom - r.top

            dh = wrapped_height(text_width) - wrapped_height(old_w)
            gdi32.SelectObject(hdc, prev)
            user32.ReleaseDC(text, hdc)
            dw = text_width - old_w

            SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0004, 0x0010
            user32.SetWindowPos(
                text, 0, old.left, old.top, text_width, old.bottom - old.top + dh,
                SWP_NOZORDER | SWP_NOACTIVATE,
            )
            # Buttons sit bottom-right, so they shift by the full size change.
            button = user32.FindWindowExW(hwnd, None, "Button", None)
            while button:
                r = rect_in_dialog(button)
                user32.SetWindowPos(
                    button, 0, r.left + dw, r.top + dh, 0, 0,
                    SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
                )
                button = user32.FindWindowExW(hwnd, button, "Button", None)

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left + dw
            h = rect.bottom - rect.top + dh
            user32.SetWindowPos(
                hwnd, 0, max(cx - w // 2, 0), max(cy - h // 2, 0), w, h,
                SWP_NOZORDER | SWP_NOACTIVATE,
            )
            user32.InvalidateRect(hwnd, None, True)
            return True

        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.FindWindowExW.restype = wintypes.HWND

        def find_boxes():
            """Message boxes with this title that belong to this process.
            Matching by title alone could grab a box left open by another
            copy of the app."""
            boxes, hwnd = [], None
            while True:
                hwnd = user32.FindWindowExW(None, hwnd, "#32770", title)
                if not hwnd:
                    return boxes
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == os.getpid():
                    boxes.append(hwnd)

        already_open = set(find_boxes())

        def watcher():
            try:
                for _ in range(150):
                    hwnd = next(
                        (h for h in find_boxes() if h not in already_open), None
                    )
                    # Wait for the box to be shown: with long text Windows can
                    # create it before its final layout is in place.
                    if hwnd and not user32.IsWindowVisible(hwnd):
                        hwnd = None
                    if hwnd and text_width and widen(ctypes, wintypes, user32, hwnd):
                        return
                    if hwnd:
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w, h = rect.right - rect.left, rect.bottom - rect.top
                        # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                        user32.SetWindowPos(
                            hwnd, 0, max(cx - w // 2, 0), max(cy - h // 2, 0), 0, 0,
                            0x0001 | 0x0004 | 0x0010,
                        )
                        return
                    time.sleep(0.02)
            except Exception:
                pass

        threading.Thread(target=watcher, daemon=True).start()

    def _show_info_dialog(self, title, body_text):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.resizable(False, False)
        # Hidden until positioned, so it doesn't flash at the default spot first.
        dialog.withdraw()

        if self._info_icon_image_lg:
            ctk.CTkLabel(dialog, text="", image=self._info_icon_image_lg).pack(pady=(20, 5))
        else:
            ctk.CTkLabel(dialog, text="ℹ️", font=ctk.CTkFont(size=32)).pack(pady=(20, 5))
        ctk.CTkLabel(
            dialog, text=body_text, wraplength=380, justify="left",
        ).pack(padx=25, pady=(0, 15))

        ctk.CTkButton(
            dialog, text="Close", command=dialog.destroy
        ).pack(padx=25, pady=(0, 20), fill="x")

        # Centre over the main app window.
        dialog.update_idletasks()
        width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        x = self.winfo_rootx() + (self.winfo_width() - width) // 2
        y = self.winfo_rooty() + (self.winfo_height() - height) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        dialog.deiconify()

        dialog.transient(self)
        dialog.after(10, dialog.lift)
        dialog.grab_set()

    def _embed_help_icon(self, log_box, index="1.0", size=16):
        """Embeds the generic-info.png icon directly into a log textbox at
        `index`, in place of a plain ℹ️ glyph -- no tooltip, no dialog."""
        if not self._info_icon_pil or log_box is None:
            return
        try:
            small = self._info_icon_pil.resize((size, size), PilImage.LANCZOS)
            photo = ImageTk.PhotoImage(small)
        except Exception:
            return
        self._inline_icon_refs.append(photo)

        was_disabled = str(log_box.cget("state")) == "disabled"
        log_box.configure(state="normal")
        log_box._textbox.image_create(index, image=photo)
        if was_disabled:
            log_box.configure(state="disabled")

    def _log_with_info_icon(self, log_box, text):
        """Like _log(), but every "ℹ️" marker in `text` (there may
        be several -- a leading header plus inline "FFmpeg command:" notes)
        is rendered as the real generic-info.png icon instead of the plain
        emoji glyph.

        The text is remembered as the box's help, so switching back to its
        panel after the log was cleared shows it again (_restore_empty_help)."""
        if not hasattr(self, "_log_help_texts"):
            self._log_help_texts = {}
        self._log_help_texts[log_box] = text
        parts = text.split("ℹ️")
        if len(parts) == 1:
            self._log(log_box, text)
            return

        log_box.configure(state="normal")
        log_box._textbox.insert("end", parts[0])
        for part in parts[1:]:
            self._embed_help_icon(log_box, index="end")
            log_box._textbox.insert("end", part)
        # Help text is read from the top; scrolling to the end hid its start
        # on tabs where the box is shorter than the text.
        log_box.see("1.0")
        log_box.configure(state="disabled")

    def _restore_empty_help(self, panel):
        """Re-show the help text in any of `panel`'s log boxes that are empty
        (cleared via Clear Logs, or by a run that produced nothing). Logs that
        still hold output are left alone."""
        prefix = str(panel) + "."
        for log_box, text in getattr(self, "_log_help_texts", {}).items():
            try:
                if str(log_box).startswith(prefix) and not log_box.get("1.0", "end-1c").strip():
                    self._log_with_info_icon(log_box, text)
            except tk.TclError:
                pass

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
        confirm=None,
        fallback_cmd_builder=None,
        on_success=None,
        pre_run=None,
        show_run_abort=True,
        save_label="Save",
        button_container=None,
        vertical_buttons=False,
        label_width=80,
    ):
        file_filters = file_filters or VIDEO_FILTERS
        output_filetypes = output_filetypes or file_filters
        opts = {"_input_change_callbacks": []}

        _files_card, files_body = dashboard_card(parent, "Files")
        input_frame = ctk.CTkFrame(files_body, fg_color="transparent")
        input_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(input_frame, text="Input File:", width=label_width, anchor="w").pack(
            side="left", padx=(0, 5)
        )
        input_entry = ctk.CTkEntry(input_frame, placeholder_text="Select input file...")
        input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        output_frame = ctk.CTkFrame(files_body, fg_color="transparent")
        output_frame.pack(fill="x")

        ctk.CTkLabel(output_frame, text="Output File:", width=label_width, anchor="w").pack(
            side="left", padx=(0, 5)
        )
        output_entry = ctk.CTkEntry(output_frame, placeholder_text="Auto-generated or browse...")
        output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # Remembers the last auto-generated name, so a name the user has typed
        # or browsed to survives the Input box losing focus and pressing Run
        # (where only its extension may change). Choosing a new input file, or
        # changing an option such as the LUFS target, re-asserts the generated
        # name so its tag matches the new settings.
        auto_state = {"input": None, "name": None}

        def update_output(*_args, keep_custom=True):
            input_path = input_entry.get().strip()
            if not input_path:
                return
            new_path = output_namer(input_path, opts)
            current = output_entry.get().strip()
            user_edited = bool(current) and current != auto_state["name"]
            if not keep_custom or input_path != auto_state["input"] or not user_edited:
                output_entry.delete(0, "end")
                output_entry.insert(0, new_path)
            else:
                current_base, current_ext = os.path.splitext(current)
                new_ext = os.path.splitext(new_path)[1]
                if current_ext.lower() != new_ext.lower():
                    output_entry.delete(0, "end")
                    output_entry.insert(0, current_base + new_ext)
            auto_state["input"] = input_path
            auto_state["name"] = new_path
            for callback in opts["_input_change_callbacks"]:
                callback(input_path)

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
        opts["input_entry"] = input_entry
        opts["output_entry"] = output_entry
        opts["_update_output"] = update_output

        if options_builder:
            _options_card, options_frame = dashboard_card(parent, "Options")
            def option_changed(*_args):
                update_output(keep_custom=False)

            options_builder(options_frame, opts, option_changed)

        if button_container is not None:
            action_frame = button_container() if callable(button_container) else button_container
        else:
            action_frame = ctk.CTkFrame(parent, fg_color="transparent")
            action_frame.pack(anchor="center", pady=(10, 5))

        run_btn = AccentButton(action_frame, text=run_label, width=150)

        abort_btn = AccentButton(
            action_frame, text="Abort", width=110, kind="danger", state="disabled",
            command=self._abort_current_operation
        )

        if show_run_abort:
            if vertical_buttons:
                run_btn.pack(side="top", fill="x", pady=(0, 6))
                abort_btn.pack(side="top", fill="x")
            else:
                run_btn.pack(side="left", padx=(0, 6))
                abort_btn.pack(side="left")
            primary_btn = run_btn
        else:
            save_btn = AccentButton(action_frame, text=save_label, width=150)
            if vertical_buttons:
                save_btn.pack(side="top", fill="x")
            else:
                save_btn.pack(side="left")
            primary_btn = save_btn

        progress = ActivityBar(parent, mode="indeterminate", height=6)
        progress.pack(fill="x", padx=4, pady=(2, 8))
        progress.set(0)

        log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))
        log_box.pack(fill="both", expand=True)
        log_box.configure(state="disabled")
        self._add_log_context_menu(log_box)
        self._log_with_info_icon(log_box, help_text)
        opts["_log_box"] = log_box

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
                error = validate(input_path, opts)
                if error:
                    self._log(log_box, f"Error: {error}\n")
                    messagebox.showerror("Cannot Run", error)
                    return

            if confirm and not confirm(input_path, opts):
                self._log(log_box, "Cancelled.\n")
                return
            output_path = output_entry.get().strip() or output_path

            if not self._ffmpeg_path or not os.path.isfile(self._ffmpeg_path):
                self._log(log_box, "Error: ffmpeg not found. Set its location in Settings.\n")
                return

            self._set_operation_running(True)
            primary_btn.configure(state="disabled")
            abort_btn.configure(state="normal")
            cmd = cmd_builder(self._ffmpeg_path, input_path, output_path, opts)

            if fallback_cmd_builder:
                fallback_cmd = fallback_cmd_builder(self._ffmpeg_path, input_path, output_path, opts)
                self._run_ffmpeg_with_fallback(
                    cmd, fallback_cmd, log_box, primary_btn, progress, abort_btn
                )
            else:
                success_cb = (
                    (lambda: on_success(input_path, output_path, opts))
                    if on_success is not None else None
                )
                self._run_ffmpeg(
                    cmd, log_box, primary_btn, progress, abort_btn=abort_btn,
                    on_success=success_cb,
                    pre_process=(lambda: pre_run(opts)) if pre_run is not None else None,
                )

        primary_btn.configure(command=run_command)

        return opts

    def _show_image_preview(self, image_path, log_box=None):
        if not image_path or not os.path.isfile(image_path):
            return
        try:
            img = PilImage.open(image_path)
            img.load()
        except Exception:
            return

        max_w, max_h = 640, 480
        width, height = img.size
        scale = min(max_w / width, max_h / height, 1.0)
        preview_size = (max(1, round(width * scale)), max(1, round(height * scale)))

        dialog = ctk.CTkToplevel(self)
        dialog.title("Still Frame Created")
        dialog.resizable(False, False)

        preview_image = ctk.CTkImage(light_image=img, dark_image=img, size=preview_size)
        image_label = ctk.CTkLabel(dialog, image=preview_image, text="")
        image_label.pack(padx=15, pady=(15, 10))

        ctk.CTkLabel(
            dialog, text=image_path, wraplength=max(preview_size[0], 400), justify="center"
        ).pack(padx=15, pady=(0, 15))

        button_row = ctk.CTkFrame(dialog, fg_color="transparent")
        button_row.pack(pady=(0, 15))

        if log_box is not None:
            ctk.CTkButton(
                button_row, text="Open Log in Notepad", width=170,
                command=lambda: self._open_log_in_notepad(log_box),
            ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(button_row, text="Close", width=100, command=dialog.destroy).pack(side="left")
        dialog.transient(self)
        dialog.after(10, dialog.lift)
        dialog.grab_set()

    def _list_windows_drives(self):
        """All mounted drive letters (C:\\, D:\\, ...) -- lets the folder
        picker below list every drive as a top-level tree root instead of
        being stuck on whichever drive the starting folder lives on."""
        if sys.platform != "win32":
            return []
        import string
        return [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]

    @staticmethod
    def _explorer_icon_key(filename):
        """Classifies a filename into an icon bucket by extension --
        mirrors Modern_Treeview_file_explorer_#1.py's icon_key_for_filename."""
        suffix = os.path.splitext(filename)[1].lower()
        if suffix in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}:
            return "image"
        if suffix in {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"}:
            return "video"
        if suffix in {".zip", ".7z", ".rar", ".tar", ".gz"}:
            return "archive"
        if suffix in {".exe", ".msi", ".bat", ".cmd", ".ps1"}:
            return "application"
        return "file"

    def _get_explorer_file_icons(self):
        """Small PIL-drawn, per-type coloured icons (folder/file/image/video/
        archive/application) for the folder picker's Treeview -- built once
        and cached, colors lifted from Modern_Treeview_file_explorer_#1.py."""
        if getattr(self, "_explorer_file_icons", None) is not None:
            return self._explorer_file_icons
        colors = {
            "folder": (245, 185, 55),
            "file": (148, 163, 184),
            "image": (45, 180, 145),
            "video": (217, 92, 92),
            "archive": (164, 125, 219),
            "application": (75, 145, 210),
        }
        icons = {}
        for key, color in colors.items():
            image = PilImage.new("RGBA", (20, 20), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            if key == "folder":
                draw.polygon([(2, 5), (8, 5), (10, 7), (18, 7), (18, 17), (2, 17)], fill=color)
                draw.line([(2, 5), (8, 5), (10, 7), (18, 7)], fill=(255, 220, 115), width=1)
            else:
                draw.polygon([(4, 2), (13, 2), (17, 6), (17, 18), (4, 18)], fill=color)
                draw.polygon([(13, 2), (13, 6), (17, 6)], fill=(226, 232, 240))
                draw.line([(7, 10), (14, 10)], fill=(255, 255, 255), width=1)
                draw.line([(7, 13), (14, 13)], fill=(255, 255, 255), width=1)
            icons[key] = ImageTk.PhotoImage(image)
        self._explorer_file_icons = icons
        return icons

    def _ask_folder_with_preview(self, initial_dir=None, title="Select Folder"):
        """Folder picker built on a ttk.Treeview (styled after
        Modern_Treeview_file_explorer_#1.py's dark, colour-coded file
        explorer) so the user can visually confirm they're in the right
        place -- every drive is a top-level root, subfolders lazy-expand,
        and picking a folder never requires clicking a file."""
        start_dir = initial_dir if initial_dir and os.path.isdir(initial_dir) else os.path.expanduser("~")
        result = {"path": None}
        current = {"path": None}
        folder_paths = {}
        loaded = set()
        icons = self._get_explorer_file_icons()

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "FFTExplorer.Treeview",
            background=INSET, fieldbackground=INSET, foreground=TEXT,
            bordercolor=INSET, borderwidth=0, rowheight=24, font=("Segoe UI", 10),
        )
        style.map(
            "FFTExplorer.Treeview",
            background=[("selected", SELECTED)], foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "FFTExplorer.Treeview.Heading",
            background=CARD_2, foreground=MUTED,
            font=("Segoe UI", 10, "bold"), relief="flat",
        )
        style.map("FFTExplorer.Treeview.Heading", background=[("active", CARD_2)])

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.withdraw()
        dialog.transient(self)
        dialog.configure(fg_color=BG)

        top = ctk.CTkFrame(dialog, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 5))
        path_var = ctk.StringVar(value=start_dir)
        path_entry = ctk.CTkEntry(top, textvariable=path_var)
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        tree_frame = tk.Frame(dialog, bg=INSET, highlightthickness=1,
                              highlightbackground=BORDER, highlightcolor=BORDER)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tree = ttk.Treeview(
            tree_frame, columns=("size",), show="tree headings",
            style="FFTExplorer.Treeview",
        )
        tree.heading("#0", text="Name")
        tree.heading("size", text="Size")
        tree.column("#0", anchor="w", width=340, stretch=True)
        tree.column("size", anchor="e", width=100, stretch=False)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def insert_entries(parent_id, path):
            try:
                entries = sorted(
                    os.scandir(path),
                    key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
                )
            except (OSError, PermissionError) as exc:
                tree.insert(parent_id, "end", text=f"  Unable to read folder ({exc.strerror or exc})", values=("",))
                loaded.add(path)
                return
            for entry in entries:
                is_dir = entry.is_dir(follow_symlinks=False)
                if is_dir:
                    item_id = tree.insert(
                        parent_id, "end", text=f"  {entry.name}",
                        image=icons["folder"], values=("<DIR>",),
                    )
                    folder_paths[item_id] = entry.path
                    tree.insert(item_id, "end", text="")
                else:
                    try:
                        size_str = f"{entry.stat(follow_symlinks=False).st_size:,}"
                    except OSError:
                        size_str = "?"
                    tree.insert(
                        parent_id, "end", text=f"  {entry.name}",
                        image=icons[self._explorer_icon_key(entry.name)], values=(size_str,),
                    )
            loaded.add(path)

        def ensure_loaded(item_id, path):
            if path not in loaded:
                tree.delete(*tree.get_children(item_id))
                insert_entries(item_id, path)

        def on_open(_event=None):
            item_id = tree.focus()
            path = folder_paths.get(item_id)
            if path is not None:
                ensure_loaded(item_id, path)

        def on_select(_event=None):
            item_id = tree.focus()
            path = folder_paths.get(item_id)
            if path is not None:
                current["path"] = path
                path_var.set(path)

        tree.bind("<<TreeviewOpen>>", on_open)
        tree.bind("<<TreeviewSelect>>", on_select)

        for drive in self._list_windows_drives():
            item_id = tree.insert("", "end", text=f"  {drive}", image=icons["folder"], values=("<DIR>",))
            folder_paths[item_id] = drive
            tree.insert(item_id, "end", text="")

        def reveal_path(target):
            target = os.path.normpath(target)
            if not os.path.isdir(target):
                messagebox.showerror("Not found", f"No such folder:\n{target}", parent=dialog)
                return
            drive, rest = os.path.splitdrive(target)
            drive_root = os.path.normpath(drive + os.sep)

            item_id = None
            for iid, p in folder_paths.items():
                if tree.parent(iid) == "" and os.path.normpath(p).lower() == drive_root.lower():
                    item_id = iid
                    break
            if item_id is None:
                messagebox.showerror("Not found", f"Drive not found:\n{drive_root}", parent=dialog)
                return

            ensure_loaded(item_id, folder_paths[item_id])
            tree.item(item_id, open=True)

            walked = drive_root
            for part in rest.strip(os.sep).split(os.sep):
                if not part:
                    continue
                walked = os.path.join(walked, part)
                child_id = next(
                    (c for c in tree.get_children(item_id)
                     if folder_paths.get(c, "").lower() == os.path.normpath(walked).lower()),
                    None,
                )
                if child_id is None:
                    break
                item_id = child_id
                ensure_loaded(item_id, folder_paths[item_id])
                tree.item(item_id, open=True)

            tree.selection_set(item_id)
            tree.focus(item_id)
            tree.see(item_id)
            current["path"] = folder_paths.get(item_id, target)
            path_var.set(current["path"])

        def go_to_typed_path(_event=None):
            reveal_path(path_var.get().strip())

        path_entry.bind("<Return>", go_to_typed_path)
        ctk.CTkButton(top, text="Go", width=50, command=go_to_typed_path).pack(side="left")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        def confirm():
            if current["path"] is None:
                messagebox.showinfo(
                    "Choose a folder", "Pick a drive or folder first.", parent=dialog
                )
                return
            result["path"] = current["path"]
            dialog.destroy()

        ctk.CTkButton(
            btn_row, text="Cancel", width=100, command=dialog.destroy
        ).pack(side="right")
        ctk.CTkButton(
            btn_row, text="Select This Folder", width=160,
            font=ctk.CTkFont(weight="bold"), command=confirm,
        ).pack(side="right", padx=(0, 8))

        reveal_path(start_dir)

        dialog_w, dialog_h = 620, 520
        self.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog_w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog_h) // 2
        dialog.geometry(f"{dialog_w}x{dialog_h}+{max(0, x)}+{max(0, y)}")
        dialog.deiconify()
        dialog.after(10, dialog.lift)
        dialog.grab_set()
        dialog.wait_window()
        return result["path"]

    def _suffixed_output(self, input_path, suffix, ext=None):
        directory = self._get_output_dir(input_path)
        basename = os.path.basename(input_path)
        name, orig_ext = os.path.splitext(basename)
        return os.path.join(directory, f"{name}{suffix}{ext if ext else orig_ext}")

    def _parse_timecode_to_seconds(self, text):
        text = text.strip()
        if not text:
            return None
        if ":" in text:
            fields = text.split(":")
            try:
                fields = [float(field) for field in fields]
            except ValueError:
                return None
            seconds = 0.0
            for field in fields:
                seconds = seconds * 60 + field
            return seconds
        try:
            return float(text)
        except ValueError:
            return None

    def _format_seconds_as_timecode(self, seconds):
        seconds = max(0.0, seconds)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"

    def _get_media_duration_seconds(self, input_path):
        """Quick ffprobe duration query with window suppression."""
        if not self._ffprobe_path or not os.path.isfile(self._ffprobe_path):
            return None
        probe_cmd = [
            self._ffprobe_path,
            "-hide_banner",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_path,
        ]
        try:
            result = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                timeout=15,
                **SUBPROCESS_WINDOW_KWARGS
            )
        except Exception:
            return None
        try:
            return float(result.stdout.strip())
        except ValueError:
            return None

    def _probe_audio_tracks(self, input_path):
        """Return a list of audio streams in `0:a:N` order, each as
        {"language": str, "codec": str, "channels": int} -- used so multi-
        language files (e.g. dual Turkish/English) can be picked explicitly
        instead of relying on ffmpeg's default "best audio stream" guess."""
        if not self._ffprobe_path or not os.path.isfile(self._ffprobe_path):
            return []
        probe_cmd = [
            self._ffprobe_path, "-hide_banner", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_name,channels,channel_layout:stream_tags=language,title",
            "-of", "json",
            input_path,
        ]
        try:
            result = subprocess.run(
                probe_cmd, capture_output=True, text=True, timeout=15,
                **SUBPROCESS_WINDOW_KWARGS
            )
            data = json.loads(result.stdout or "{}")
        except Exception:
            return []

        tracks = []
        for stream in data.get("streams", []):
            tags = stream.get("tags", {}) or {}
            language = tags.get("language", "und")
            title = tags.get("title", "")
            tracks.append({
                "language": language,
                "title": title,
                "codec": stream.get("codec_name", "?"),
                "channels": stream.get("channels", "?"),
                "layout": stream.get("channel_layout", ""),
            })
        return tracks

    def _probe_full(self, input_path):
        """Full ffprobe format+stream dump as parsed JSON, or None on failure."""
        if not self._ffprobe_path or not os.path.isfile(self._ffprobe_path):
            return None
        probe_cmd = [
            self._ffprobe_path, "-hide_banner", "-v", "error",
            "-show_format", "-show_streams", "-of", "json",
            input_path,
        ]
        try:
            result = subprocess.run(
                probe_cmd, capture_output=True, text=True, timeout=20,
                **SUBPROCESS_WINDOW_KWARGS
            )
            return json.loads(result.stdout or "{}")
        except Exception:
            return None

    def _format_fps(self, r_frame_rate):
        try:
            num, den = r_frame_rate.split("/")
            den = float(den)
            return f"{(float(num) / den):.2f}" if den else "?"
        except Exception:
            return "?"

    def _describe_media(self, path):
        """Human-readable multi-line summary of a media file's container/streams,
        used for the Audio Accessibility conversion report."""
        lines = [f"  Path: {path}"]
        if not os.path.isfile(path):
            lines.append("  (file not found)")
            return "\n".join(lines)

        data = self._probe_full(path)
        if not data:
            lines.append("  (unable to read details — ffprobe not available)")
            return "\n".join(lines)

        fmt = data.get("format", {}) or {}
        size = fmt.get("size")
        if size:
            try:
                lines.append(f"  Size: {int(size) / 1_000_000:.1f} MB")
            except (TypeError, ValueError):
                pass
        duration = fmt.get("duration")
        if duration:
            try:
                lines.append(f"  Duration: {self._format_seconds_as_timecode(float(duration))}")
            except (TypeError, ValueError):
                pass
        lines.append(f"  Container: {fmt.get('format_long_name') or fmt.get('format_name', '?')}")

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video":
                lines.append(
                    f"  Video: {stream.get('codec_name', '?')}, "
                    f"{stream.get('width', '?')}x{stream.get('height', '?')}, "
                    f"{self._format_fps(stream.get('r_frame_rate', ''))} fps"
                )
            elif codec_type == "audio":
                tags = stream.get("tags", {}) or {}
                language = tags.get("language", "und")
                title = tags.get("title", "")
                title_part = f" \"{title}\"" if title else ""
                lines.append(
                    f"  Audio: {stream.get('codec_name', '?')}, {language}{title_part}, "
                    f"{stream.get('channels', '?')}ch, {stream.get('sample_rate', '?')}Hz"
                )
            elif codec_type == "subtitle":
                tags = stream.get("tags", {}) or {}
                language = tags.get("language", "und")
                lines.append(f"  Subtitle: {stream.get('codec_name', '?')} ({language})")

        return "\n".join(lines)

    def _build_remux_mp4_tab(self, parent):
        def cmd_builder(ffmpeg, inp, out, opts):
            return [
                ffmpeg, "-hide_banner", "-i", inp,
                "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                out, "-y"
            ]

        def fallback_cmd_builder(ffmpeg, inp, out, opts):
            return [
                ffmpeg, "-hide_banner", "-i", inp,
                "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k", out, "-y"
            ]

        def confirm(input_path, opts):
            if os.path.splitext(input_path)[1].lower() == ".mp4":
                return messagebox.askyesno(
                    "Already MP4",
                    "This file is already in MP4 format.\n\n"
                    "Remuxing it again will just repackage its existing streams "
                    "into a new MP4 container.\n\n"
                    "Continue anyway?",
                )
            return True

        help_text = (
            "\u2139\ufe0f  Remux to MP4\n"
            "Copies video without re-encoding and converts audio to AAC for maximum compatibility.\n"
            "Copies the video without re-encoding while converting audio to AAC for broad compatibility.\n"
            "Use this to convert MKV / AVI / MOV / WMV / etc. into a standard, widely-compatible MP4.\n\n"
            "NOTE 1:\u26A0\uFE0F  Already-MP4 input: you'll be asked to confirm before it proceeds, since\n"
            "the existing streams will be repackaged and the audio will be converted to AAC.\n\n"
            "NOTE 2: \u26A0\uFE0F  If the video stream cannot be copied into MP4, it automatically retries\n"
            "with a full H.264/AAC re-encode instead of stopping at the error.\n\n"
            "\U0001F4CB FFmpeg command:\n"
            "ffmpeg -hide_banner -i input.mkv -map 0:v:0 -map 0:a? -c:v copy -c:a aac -b:a 256k output.mp4 -y\n\n"
            "Select a file above and click Run to begin.\n"
        )

        self._build_tool_panel(
            parent,
            help_text=help_text,
            cmd_builder=cmd_builder,
            fallback_cmd_builder=fallback_cmd_builder,
            confirm=confirm,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_remuxed", ".mp4"),
            output_filetypes=[("MP4 file", "*.mp4"), ("All files", "*.*")],
        )

    def _build_fix_tab(self, parent, mode):
        is_quick = mode == "quick"
        suffix = "_fixed" if is_quick else "_stubborn_fixed"

        def cmd_builder(ffmpeg, inp, out, opts):
            if is_quick:
                return [ffmpeg, "-hide_banner", "-i", inp,
                        "-map", "0:v:0", "-map", "0:a?",
                        "-c", "copy", out, "-y"]
            return [ffmpeg, "-hide_banner", "-i", inp,
                "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "copy", "-c:a", "pcm_s16le", out, "-y"]

        if is_quick:
            help_text = (
                "\u2139\ufe0f  Quick Fix\n"
                "Remuxes your video into a new container, copying all streams instantly without re-encoding.\n"
                "Use this first for files that won't import or are lagging in DaVinci Resolve.\n\n"
                "\U0001F4CB FFmpeg command:\n"
                "ffmpeg.exe -hide_banner -i <input> -map 0:v:0 -map 0:a? -c copy <output> -y\n\n"
                "Select a file above and click Run to begin.\n"
            )
        else:
            help_text = (
                "\u2139\ufe0f  Stubborn Fix\n"
                "Same as Quick Fix but converts the audio track into raw, uncompressed PCM data.\n"
                "Use this when a file imports as video-only with a missing audio track -- PCM is universally accepted by DaVinci Resolve.\n\n"
                "\U0001F4CB FFmpeg command:\n"
                "ffmpeg.exe -hide_banner -i <input> -map 0:v:0 -map 0:a? -c:v copy -c:a pcm_s16le <output>.mov -y\n\n"
                "Select a file above and click Run to begin.\n"
            )

        self._build_tool_panel(
            parent,
            help_text=help_text,
            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(
                inp, suffix, ext=".mov" if not is_quick else None
            ),
        )

    # ---- Scaling helpers (shared by Proxy Creator and Video Scaler) ----

    @staticmethod
    def _scale_short_side(n, flags=None):
        """Scale filter that sets the SHORT side to n and keeps the aspect
        ratio, so "720p" works for landscape and portrait alike. The -2 keeps
        the other side even, which H.264/H.265 require."""
        suffix = f":flags={flags}" if flags else ""
        return f"scale='if(gte(iw,ih),-2,{n})':'if(gte(iw,ih),{n},-2)'{suffix}"

    @staticmethod
    def _scale_fraction(divisor, flags=None):
        """Scale filter for 1/divisor of the size, rounded down to even numbers
        (plain iw/4 can give an odd width, e.g. 1366/4, which libx264 rejects)."""
        suffix = f":flags={flags}" if flags else ""
        d2 = divisor * 2
        return f"scale=trunc(iw/{d2})*2:trunc(ih/{d2})*2{suffix}"

    @staticmethod
    def _even(value):
        """Nearest even integer, minimum 2 -- mirrors ffmpeg's -2 rounding."""
        return max(2, int(round(value / 2.0)) * 2)

    def _display_size(self, probe):
        """(width, height) of the first video stream as it will be SHOWN --
        swapped for phone footage tagged with a 90/270 degree rotation, since
        ffmpeg auto-rotates before scaling. None if unknown."""
        video = self._prores_first_video(probe)
        w, h = video.get("width"), video.get("height")
        if not w or not h:
            return None
        rotation = 0
        for side in video.get("side_data_list", []) or []:
            if "rotation" in side:
                rotation = side.get("rotation") or 0
        if not rotation:
            rotation = (video.get("tags", {}) or {}).get("rotate", 0)
        try:
            if int(float(rotation)) % 180:
                w, h = h, w
        except (TypeError, ValueError):
            pass
        return int(w), int(h)

    def _build_proxy_tab(self, parent):
        SCALES = {
            "Half (1/2)": self._scale_fraction(2),
            "Quarter (1/4)": self._scale_fraction(4),
            "720p": self._scale_short_side(720),
            "480p": self._scale_short_side(480),
        }

        def options_builder(frame, opts, on_change):
            # Same width as the Input/Output File labels, so the menu lines up with their boxes.
            ctk.CTkLabel(frame, text="Resolution:", width=80, anchor="w").pack(side="left", padx=(0, 5))
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
            return [
                ffmpeg, "-hide_banner", "-i", inp,
                "-vf", f"{scale},format=yuv420p",
                "-c:v", codec, 
                "-crf", crf, 
                "-preset", "fast",
                "-colorspace", "bt709",
                "-color_trc", "bt709",
                "-color_primaries", "bt709",
                "-c:a", "pcm_s16le",
                out, "-y"
            ]

        self._build_tool_panel(
            parent,
            help_text="ℹ️  Proxy Creator\nCreates a lightweight proxy with Rec.709 color tracking.\n"
                      "Creates a lightweight, lower-resolution copy of your footage for smooth editing in DaVinci Resolve.\n"
                      "Resolve edits using the proxy, then switches back to the full-quality original at export \u2014 no quality loss.\n\n"
                      "Optimisations Applied:\n"
                      "  - Rec.709 Gamma Standardisation: Prevents proxies from appearing washed out or darker than the source footage.\n"
                      "  - Lossless PCM Audio Transcoding: Replaces heavy movie codecs with uncompressed 16-bit streams to stop timeline scrubbing lag and sync errors.\n"
                      "  - Aspect-Safe Sizing: 720p/480p set the short side, so portrait and non-16:9 footage isn't squashed; sizes are kept even for the encoder.\n\n"
                      "ℹ️  FFmpeg command:\n"
                      "ffmpeg.exe -hide_banner -i <input> -vf scale=trunc(iw/4)*2:trunc(ih/4)*2,format=yuv420p -c:v libx264 -crf 23 -colorspace bt709 -color_trc bt709 -color_primaries bt709 -c:a pcm_s16le <output>.mov -y\n",

            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_proxy", ext=".mov"),
            options_builder=options_builder,
            output_filetypes=[("MOV files", "*.mov"), ("All files", "*.*")],
        )

    # ---- Video Scaler ----

    # label -> (kind, value): "short" = short side in pixels, "frac" = 1/value
    # of the size, "custom" = the width/height boxes.
    _SCALER_PRESETS = {
        "2160p (4K)": ("short", 2160),
        "1440p": ("short", 1440),
        "1080p": ("short", 1080),
        "720p": ("short", 720),
        "480p": ("short", 480),
        "360p": ("short", 360),
        "50%": ("frac", 2),
        "25%": ("frac", 4),
        "Custom size": ("custom", None),
    }
    _SCALER_FIT_MODES = [
        "Fit inside (keep aspect)",
        "Fit + pad to exact size",
        "Crop to fill exact size",
        "Stretch to exact size",
    ]
    # Containers that take H.264/H.265 plus the source's audio as-is;
    # anything else (webm, avi, wmv...) goes to MKV, which accepts almost any audio.
    _SCALER_KEEP_EXTS = (".mp4", ".m4v", ".mov", ".mkv")

    def _scaler_custom_dims(self, opts):
        """(width, height, error) from the Custom boxes; blank means auto.
        Values are rounded to even numbers for the encoder."""
        dims = []
        for key, name in (("custom_w", "Width"), ("custom_h", "Height")):
            text = opts[key].get().strip()
            if not text:
                dims.append(None)
                continue
            try:
                value = int(text)
            except ValueError:
                return None, None, f"{name} must be a whole number of pixels."
            if not 16 <= value <= 8192:
                return None, None, f"{name} must be between 16 and 8192 pixels."
            dims.append(self._even(value))
        w, h = dims
        if w is None and h is None:
            return None, None, "Enter a width, a height, or both."
        if (w is None or h is None) and opts["fit_mode"].get() != self._SCALER_FIT_MODES[0]:
            return None, None, f"\"{opts['fit_mode'].get()}\" needs both a width and a height."
        return w, h, None

    def _scaler_filter(self, opts):
        """The scale part of the -vf chain for the current settings."""
        kind, value = self._SCALER_PRESETS[opts["preset"].get()]
        if kind == "short":
            return self._scale_short_side(value, "lanczos")
        if kind == "frac":
            return self._scale_fraction(value, "lanczos")

        w, h, _error = self._scaler_custom_dims(opts)
        if w is None:
            return f"scale=-2:{h}:flags=lanczos"
        if h is None:
            return f"scale={w}:-2:flags=lanczos"
        mode = self._SCALER_FIT_MODES.index(opts["fit_mode"].get())
        if mode == 0:
            return (f"scale={w}:{h}:force_original_aspect_ratio=decrease:"
                    f"force_divisible_by=2:flags=lanczos")
        if mode == 1:
            return (f"scale={w}:{h}:force_original_aspect_ratio=decrease:"
                    f"force_divisible_by=2:flags=lanczos,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")
        if mode == 2:
            return (f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
                    f"crop={w}:{h},setsar=1")
        return f"scale={w}:{h}:flags=lanczos,setsar=1"

    def _scaler_output_size(self, src, opts):
        """Predicted (width, height) for a source of display size src, mirroring
        _scaler_filter. None if the settings are incomplete."""
        src_w, src_h = src
        kind, value = self._SCALER_PRESETS[opts["preset"].get()]
        if kind == "short":
            if src_w >= src_h:
                return self._even(src_w * value / src_h), value
            return value, self._even(src_h * value / src_w)
        if kind == "frac":
            return max(2, src_w // (2 * value) * 2), max(2, src_h // (2 * value) * 2)

        w, h, error = self._scaler_custom_dims(opts)
        if error:
            return None
        if w is None:
            return self._even(src_w * h / src_h), h
        if h is None:
            return w, self._even(src_h * w / src_w)
        if opts["fit_mode"].get() == self._SCALER_FIT_MODES[0]:
            # Same steps as ffmpeg's force_original_aspect_ratio=decrease with
            # force_divisible_by=2: round to the nearest even number, take the
            # smaller box, then floor to even.
            fit_w = min(w, (h * src_w + src_h) // (2 * src_h) * 2)
            fit_h = min(h, (w * src_h + src_w) // (2 * src_w) * 2)
            return max(2, fit_w // 2 * 2), max(2, fit_h // 2 * 2)
        return w, h

    def _scaler_output_path(self, inp, opts):
        kind, value = self._SCALER_PRESETS[opts["preset"].get()]
        if kind == "short":
            tag = f"_{value}p"
        elif kind == "frac":
            tag = f"_{100 // value}pc"
        else:
            w, h, error = self._scaler_custom_dims(opts)
            tag = "_scaled" if error else f"_{w or 'auto'}x{h or 'auto'}"
        ext = os.path.splitext(inp)[1].lower()
        return self._suffixed_output(
            inp, tag, ext=None if ext in self._SCALER_KEEP_EXTS else ".mkv"
        )

    def _build_scaler_tab(self, parent):
        probe_cache = {}

        def options_builder(frame, opts, on_change):
            # Row 1: size
            row1 = ctk.CTkFrame(frame, fg_color="transparent")
            row1.pack(fill="x")
            # Same width as the Input/Output File labels, so the menu lines up with their boxes.
            ctk.CTkLabel(row1, text="Resolution:", width=80, anchor="w").pack(side="left", padx=(0, 5))
            opts["preset"] = ctk.StringVar(value="1080p")
            ctk.CTkOptionMenu(
                row1, variable=opts["preset"], values=list(self._SCALER_PRESETS.keys()), width=130
            ).pack(side="left", padx=(0, 15))

            opts["custom_w"] = ctk.StringVar(value="1920")
            opts["custom_h"] = ctk.StringVar(value="1080")
            ctk.CTkLabel(row1, text="Custom:", anchor="w").pack(side="left", padx=(0, 5))
            w_entry = ctk.CTkEntry(row1, textvariable=opts["custom_w"], width=64, placeholder_text="auto")
            w_entry.pack(side="left")
            ctk.CTkLabel(row1, text="×").pack(side="left", padx=4)
            h_entry = ctk.CTkEntry(row1, textvariable=opts["custom_h"], width=64, placeholder_text="auto")
            h_entry.pack(side="left", padx=(0, 15))

            opts["fit_mode"] = ctk.StringVar(value=self._SCALER_FIT_MODES[0])
            fit_menu = ctk.CTkOptionMenu(
                row1, variable=opts["fit_mode"], values=self._SCALER_FIT_MODES, width=200
            )
            fit_menu.pack(side="left")

            # Row 2: encoding
            row2 = ctk.CTkFrame(frame, fg_color="transparent")
            row2.pack(fill="x", pady=(8, 0))
            ctk.CTkLabel(row2, text="Codec:", width=80, anchor="w").pack(side="left", padx=(0, 5))
            opts["codec"] = ctk.StringVar(value="H.264")
            ctk.CTkOptionMenu(
                row2, variable=opts["codec"], values=["H.264", "H.265"], width=130
            ).pack(side="left", padx=(0, 15))

            ctk.CTkLabel(row2, text="Quality (CRF):", anchor="w").pack(side="left", padx=(0, 5))
            crf_label = ctk.CTkLabel(row2, text="20", width=30)
            opts["crf"] = ctk.IntVar(value=20)

            def on_crf_change(value):
                opts["crf"].set(int(value))
                crf_label.configure(text=str(int(value)))

            crf_slider = ctk.CTkSlider(row2, from_=16, to=30, number_of_steps=14,
                                       command=on_crf_change)
            crf_slider.set(20)
            crf_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
            crf_label.pack(side="right", padx=(5, 0))

            # Row 3: source -> output preview
            opts["size_label"] = ctk.CTkLabel(
                frame, text="Output size: select a file.", anchor="w",
                text_color=MUTED,
            )
            opts["size_label"].pack(fill="x", padx=(85, 0), pady=(6, 0))

            def show_sizes(*_args):
                probe = probe_cache.get(opts.get("_current_input"))
                if probe is None:
                    return
                src = self._display_size(probe)
                if src is None:
                    opts["size_label"].configure(
                        text="Output size: unknown (couldn't read the video's resolution).",
                        text_color=MUTED)
                    return
                out = self._scaler_output_size(src, opts)
                text = f"Source: {src[0]}×{src[1]}   →   Output: "
                if out is None:
                    opts["size_label"].configure(text=text + "check the custom size.",
                                                 text_color=AMBER)
                elif out[0] * out[1] > src[0] * src[1]:
                    opts["size_label"].configure(
                        text=text + f"{out[0]}×{out[1]}   ⚠ larger than the source "
                                    "— upscaling makes a bigger file but adds no detail",
                        text_color=AMBER)
                else:
                    opts["size_label"].configure(text=text + f"{out[0]}×{out[1]}",
                                                 text_color=MUTED)

            def on_input(input_path):
                opts["_current_input"] = input_path
                if input_path in probe_cache:
                    show_sizes()
                    return
                opts["size_label"].configure(text="Output size: reading file...",
                                             text_color=MUTED)

                def worker():
                    probe = self._probe_full(input_path) or {}

                    def done():
                        probe_cache[input_path] = probe
                        if opts.get("_current_input") == input_path:
                            show_sizes()
                    self._run_on_main(done)
                threading.Thread(target=worker, daemon=True).start()

            def on_setting_change(*_args):
                is_custom = self._SCALER_PRESETS[opts["preset"].get()][0] == "custom"
                state = "normal" if is_custom else "disabled"
                entry_text = TEXT if is_custom else DISABLED
                w_entry.configure(state=state, text_color=entry_text)
                h_entry.configure(state=state, text_color=entry_text)
                fit_menu.configure(state=state)
                show_sizes()
                on_change()  # refresh the suggested output name (_720p, _50pc...)

            opts["_input_change_callbacks"].append(on_input)
            for key in ("preset", "custom_w", "custom_h", "fit_mode"):
                opts[key].trace_add("write", on_setting_change)
            on_setting_change()

        def get_probe(inp):
            if inp not in probe_cache:
                probe_cache[inp] = self._probe_full(inp) or {}
            return probe_cache[inp]

        def validate(input_path, opts):
            if self._SCALER_PRESETS[opts["preset"].get()][0] == "custom":
                return self._scaler_custom_dims(opts)[2]
            return None

        def confirm(input_path, opts):
            src = self._display_size(get_probe(input_path))
            out = self._scaler_output_size(src, opts) if src else None
            if src and out and out[0] * out[1] > src[0] * src[1]:
                title = "Upscale?"
                self._center_next_messagebox(title)
                return messagebox.askyesno(
                    title,
                    f"The output ({out[0]}×{out[1]}) is larger than the source "
                    f"({src[0]}×{src[1]}).\n\n"
                    "Upscaling makes a bigger file but can't add detail that isn't there.\n\n"
                    "Continue anyway?",
                )
            return True

        def cmd_builder(ffmpeg, inp, out, opts):
            vf = self._scaler_filter(opts)
            is_h264 = opts["codec"].get() == "H.264"
            if is_h264:
                # 8-bit 4:2:0 plays everywhere; H.265 keeps the source's
                # bit depth so 10-bit/HDR footage doesn't band.
                vf += ",format=yuv420p"
            cmd = [
                ffmpeg, "-hide_banner", "-i", inp,
                "-map", "0:v:0", "-map", "0:a?", "-map_metadata", "0",
                "-vf", vf,
                "-c:v", "libx264" if is_h264 else "libx265",
                "-crf", str(opts["crf"].get()),
                "-preset", "medium",
            ]
            ext = os.path.splitext(out)[1].lower()
            if not is_h264 and ext in (".mp4", ".m4v", ".mov"):
                cmd += ["-tag:v", "hvc1"]  # lets Apple devices play H.265
            cmd += ["-c:a", "copy"]
            if ext in (".mp4", ".m4v", ".mov"):
                cmd += ["-movflags", "+faststart"]
            return cmd + [out, "-y"]

        self._build_tool_panel(
            parent,
            help_text="ℹ️  Video Scaler\n"
                "Resizes a video to a new resolution for sharing, uploading or saving space.\n\n"
                "Options:\n"
                "  - Resolution presets (2160p...360p) set the SHORT side, so portrait phone video is handled correctly "
                "(720p of a vertical video is 720×1280).\n"
                "  - 50% / 25% shrink both sides by that amount.\n"
                "  - Custom size: fill in width, height or both (blank = auto). With both filled in, choose how to fit:\n"
                "      Fit inside — keeps the shape, fits within the box.\n"
                "      Fit + pad — exact size, with black bars where the shape differs.\n"
                "      Crop to fill — exact size, trimming the overflow (good for 1080×1920 social video).\n"
                "      Stretch — exact size, distorting the picture.\n"
                "  - Quality (CRF): lower = better quality and bigger file. 18–22 is a good range.\n\n"
                "Optimisations Applied:\n"
                "  - Lanczos scaling for the sharpest result.\n"
                "  - Sizes kept even, as H.264/H.265 require.\n"
                "  - Rotated phone footage is sized by how it looks, not how it's stored.\n"
                "  - All audio tracks copied untouched (fast, no quality loss). Subtitles are not copied.\n"
                "  - Warns before upscaling.\n\n"
                "ℹ️  FFmpeg command (720p, H.264):\n"
                "ffmpeg.exe -hide_banner -i <input> -map 0:v:0 -map 0:a? -map_metadata 0 "
                "-vf scale='if(gte(iw,ih),-2,720)':'if(gte(iw,ih),720,-2)':flags=lanczos,format=yuv420p "
                "-c:v libx264 -crf 20 -preset medium -c:a copy -movflags +faststart <output>.mp4 -y\n\n"
                "Select a file above and click Run to begin.\n",
            cmd_builder=cmd_builder,
            output_namer=self._scaler_output_path,
            options_builder=options_builder,
            validate=validate,
            confirm=confirm,
        )

    # ---- ProRes Export (single file + batch share everything below) ----

    _PRORES_PROFILES = {
        "ProRes 422 Proxy": "0",
        "ProRes 422 LT": "1",
        "ProRes 422": "2",
        "ProRes 422 HQ": "3",
        "ProRes 4444": "4",
        "ProRes 4444 XQ": "5",
    }
    # Apple's published target data rates (Mbit/s) at 1920x1080, 29.97 fps.
    # Used only for the size estimate -- scaled by resolution and frame rate.
    _PRORES_MBPS_1080P30 = {"0": 45, "1": 102, "2": 147, "3": 220, "4": 330, "5": 500}
    _PRORES_HDR_MODES = ["Keep HDR", "Convert to SDR (Rec.709)"]
    _PRORES_FPS_CHOICES = {
        "Auto (source)": None,
        "23.976": "24000/1001", "24": "24", "25": "25",
        "29.97": "30000/1001", "30": "30",
        "50": "50", "59.94": "60000/1001", "60": "60",
    }
    # Standard rates that a phone's variable-frame-rate average is snapped to.
    _PRORES_STANDARD_RATES = [
        (24000 / 1001, "24000/1001"), (24.0, "24"), (25.0, "25"),
        (30000 / 1001, "30000/1001"), (30.0, "30"), (50.0, "50"),
        (60000 / 1001, "60000/1001"), (60.0, "60"),
    ]
    _HDR_TRANSFERS = ("arib-std-b67", "smpte2084")  # HLG, PQ
    _KNOWN_PRIMARIES = ("bt709", "smpte170m", "bt470bg", "bt2020")
    _KNOWN_TRANSFERS = ("bt709", "smpte170m", "bt470bg", "iec61966-2-1") + _HDR_TRANSFERS
    _KNOWN_MATRICES = ("bt709", "smpte170m", "bt470bg", "bt2020nc")
    _ALPHA_PIX_PREFIXES = ("yuva", "rgba", "bgra", "argb", "abgr", "gbrap", "ya")
    _BATCH_VIDEO_EXTS = (
        ".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts", ".m2ts",
        ".mxf", ".webm", ".mpg", ".mpeg", ".wmv", ".3gp",
    )

    @staticmethod
    def _parse_rate(rate):
        """'30000/1001', '60' or '29.970' -> float fps, or None."""
        try:
            num, _, den = str(rate).partition("/")
            num, den = float(num), float(den or 1)
            return num / den if den and num else None
        except Exception:
            return None

    @staticmethod
    def _format_bytes(num_bytes):
        size = float(num_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def _ffmpeg_has_filter(self, name):
        """Whether the current ffmpeg build has a given filter (cached per ffmpeg path)."""
        cache = getattr(self, "_filter_cache", None)
        if cache is None or cache.get("_path") != self._ffmpeg_path:
            cache = {"_path": self._ffmpeg_path}
            try:
                result = subprocess.run(
                    [self._ffmpeg_path, "-hide_banner", "-filters"],
                    capture_output=True, text=True, timeout=20, **SUBPROCESS_WINDOW_KWARGS
                )
                cache["_names"] = {
                    parts[1] for parts in (line.split() for line in result.stdout.splitlines())
                    if len(parts) >= 2
                }
            except Exception:
                cache["_names"] = None
            self._filter_cache = cache
        names = cache.get("_names")
        return True if names is None else name in names

    def _prores_first_video(self, probe):
        return next(
            (s for s in (probe or {}).get("streams", []) if s.get("codec_type") == "video"), {}
        )

    def _prores_target_rate(self, video, fps_label):
        """The -r value to force: the user's pick, or the source's average rate
        snapped to the nearest standard rate (so VFR phone footage becomes CFR)."""
        fps_choice = self._PRORES_FPS_CHOICES.get(fps_label)
        if fps_choice:
            return fps_choice
        fps = self._parse_rate(video.get("avg_frame_rate")) or self._parse_rate(video.get("r_frame_rate"))
        if not fps:
            return None
        best_fps, best_rate = min(self._PRORES_STANDARD_RATES, key=lambda r: abs(r[0] - fps))
        if abs(best_fps - fps) / fps <= 0.02:
            return best_rate
        return f"{fps:.3f}"

    def _prores_estimate(self, probe, profile_name, fps_label):
        """Estimated output size in bytes, and duration in seconds -- or (None, None)."""
        video = self._prores_first_video(probe)
        try:
            duration = float((probe or {}).get("format", {}).get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        width, height = video.get("width"), video.get("height")
        if not duration or not width or not height:
            return None, None
        fps = self._parse_rate(self._prores_target_rate(video, fps_label)) or 30000 / 1001
        mbps = self._PRORES_MBPS_1080P30.get(self._PRORES_PROFILES.get(profile_name, "2"), 147)
        video_bps = mbps * 1_000_000 * (width * height) / (1920 * 1080) * fps / (30000 / 1001)
        audio_bps = sum(
            48000 * 24 * int(s.get("channels") or 2)
            for s in probe.get("streams", []) if s.get("codec_type") == "audio"
        )
        return (video_bps + audio_bps) / 8 * duration, duration

    def _prores_space_ok(self, out_dir, needed_bytes, what="this export"):
        """Warn (and let the user cancel) if the output drive looks too small."""
        if not needed_bytes:
            return True
        try:
            probe_dir = out_dir
            while probe_dir and not os.path.isdir(probe_dir):
                parent_dir = os.path.dirname(probe_dir)
                if parent_dir == probe_dir:
                    break
                probe_dir = parent_dir
            free = shutil.disk_usage(probe_dir or ".").free
        except Exception:
            return True
        if free >= needed_bytes * 1.1:
            return True
        return messagebox.askyesno(
            "Low Disk Space",
            f"{what.capitalize()} is estimated at {self._format_bytes(needed_bytes)}, "
            f"but only {self._format_bytes(free)} is free on the output drive.\n\n"
            "The export may fail part-way through. Continue anyway?",
            icon="warning",
        )

    def _prores_options_row(self, frame, opts, label_width=80):
        """Profile / HDR / Frame-rate menus, shared by the single and batch tabs."""
        # Same width as the Input/Output File labels, so the menu lines up with their boxes.
        ctk.CTkLabel(frame, text="Profile:", width=label_width, anchor="w").pack(side="left", padx=(0, 5))
        opts["profile"] = ctk.StringVar(value="ProRes 422")
        ctk.CTkOptionMenu(
            frame, variable=opts["profile"], values=list(self._PRORES_PROFILES.keys()), width=160
        ).pack(side="left")

        ctk.CTkLabel(frame, text="HDR source:", anchor="w").pack(side="left", padx=(16, 5))
        opts["hdr_mode"] = ctk.StringVar(value=self._PRORES_HDR_MODES[0])
        ctk.CTkOptionMenu(
            frame, variable=opts["hdr_mode"], values=self._PRORES_HDR_MODES, width=190
        ).pack(side="left")

        ctk.CTkLabel(frame, text="Frame rate:", anchor="w").pack(side="left", padx=(16, 5))
        opts["fps"] = ctk.StringVar(value="Auto (source)")
        ctk.CTkOptionMenu(
            frame, variable=opts["fps"], values=list(self._PRORES_FPS_CHOICES.keys()), width=130
        ).pack(side="left")

    def _prores_build_cmd(self, ffmpeg, inp, out, profile_name, hdr_mode, fps_label,
                          probe=None, note=None):
        note = note or (lambda _text: None)
        if probe is None:
            probe = self._probe_full(inp)
        video = self._prores_first_video(probe)
        src_pix = video.get("pix_fmt") or ""
        src_trc = video.get("color_transfer")
        src_prim = video.get("color_primaries")
        src_matrix = video.get("color_space")
        src_range = video.get("color_range")
        height = video.get("height") or 1080
        color_range = "pc" if src_range == "pc" else "tv"

        profile_val = self._PRORES_PROFILES.get(profile_name, "2")
        if profile_val in ("4", "5"):
            has_alpha = src_pix.startswith(self._ALPHA_PIX_PREFIXES)
            pix_fmt = "yuva444p10le" if has_alpha else "yuv444p10le"
        else:
            pix_fmt = "yuv422p10le"

        filters = []
        is_hdr = src_trc in self._HDR_TRANSFERS
        want_sdr = is_hdr and hdr_mode == self._PRORES_HDR_MODES[1]
        if want_sdr and not (self._ffmpeg_has_filter("zscale") and self._ffmpeg_has_filter("tonemap")):
            note("ProRes: this ffmpeg build lacks zscale/tonemap -- keeping HDR instead of converting.")
            want_sdr = False

        if want_sdr:
            # HDR -> SDR: linearise, tone-map, then back to Rec.709 limited range.
            # Input/output primaries are spelled out because zscale can't
            # find a conversion path when the decoded frames lack tags.
            filters.append(
                f"zscale=tin={src_trc}:pin=bt2020:min=bt2020nc:rin={color_range}:"
                "t=linear:p=bt2020:npl=100,"
                "format=gbrpf32le,zscale=p=bt709,"
                "tonemap=tonemap=hable:desat=0,"
                f"zscale=t=bt709:m=bt709:r=tv,format={pix_fmt}"
            )
            prim, trc, matrix, color_range = "bt709", "bt709", "bt709", "tv"
            note("ProRes: HDR source detected -- tone-mapping to SDR Rec.709.")
        elif is_hdr:
            prim, trc, matrix = "bt2020", src_trc, "bt2020nc"
            note(f"ProRes: HDR source detected ({src_trc}) -- keeping HDR colour tags.")
        elif (src_prim in self._KNOWN_PRIMARIES and src_trc in self._KNOWN_TRANSFERS
              and src_matrix in self._KNOWN_MATRICES):
            prim, trc, matrix = src_prim, src_trc, src_matrix
            note(f"ProRes: keeping source colour tags ({prim}/{trc}/{matrix}).")
        else:
            # Untagged SDR: assume Rec.709 for HD and above, Rec.601 for SD.
            std = "bt709" if height >= 720 else "smpte170m"
            prim, trc, matrix = std, std, std
            note(f"ProRes: source has no colour tags -- tagging as {std}.")

        # Recent ffmpeg builds take colour info from the frames and ignore
        # the -color_primaries / -color_trc options for prores_ks, so the
        # tags are stamped onto the frames here as well (belt and braces).
        filters.append(
            f"setparams=color_primaries={prim}:color_trc={trc}:"
            f"colorspace={matrix}:range={color_range}"
        )

        rate = self._prores_target_rate(video, fps_label) if video else None

        cmd = [
            ffmpeg, "-hide_banner", "-i", inp,
            "-map", "0:v:0", "-map", "0:a?",
            "-map_metadata", "0",
            "-vf", ",".join(filters),
        ]
        if rate:
            cmd += ["-fps_mode", "cfr", "-r", rate]
            note(f"ProRes: constant frame rate {rate} fps.")
        cmd += [
            "-c:v", "prores_ks",
            "-profile:v", profile_val,
            "-vendor", "apl0",
            "-pix_fmt", pix_fmt,
            "-color_primaries", prim,
            "-color_trc", trc,
            "-colorspace", matrix,
            "-color_range", color_range,
            "-c:a", "pcm_s24le", "-ar", "48000",
            out, "-y"
        ]
        return cmd

    _PRORES_HELP_OPTIMISATIONS = (
        "Profiles: Proxy (smallest, editing only), LT (smaller files), 422 (great all-rounder), "
        "HQ (maximum 4:2:2 quality), 4444 (full colour detail + transparency), 4444 XQ (highest quality).\n\n"
        "Optimisations Applied:\n"
        "  - Smart Colour Tagging: Reads the source's colour info and carries it across (untagged HD is tagged Rec.709), "
        "preventing gamma shift / washed-out colours in Resolve.\n"
        "  - HDR Handling: iPhone HLG / PQ HDR footage keeps its HDR tags, or choose 'Convert to SDR (Rec.709)' to tone-map it.\n"
        "  - Constant Frame Rate: Variable-frame-rate phone footage is conformed to the nearest standard rate "
        "(or the rate you pick), preventing audio drift in Resolve.\n"
        "  - All Audio Tracks: Every audio track is kept, as 24-bit / 48 kHz PCM.\n"
        "  - Metadata: Recording date and other file metadata are preserved.\n"
        "  - Size Check: The estimated output size is shown up front, and you're warned if the drive is short of space.\n\n"
    )

    def _build_prores_tab(self, parent):
        probe_cache = {}

        def options_builder(frame, opts, on_change):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x")
            self._prores_options_row(row, opts)
            opts["_probe_cache"] = probe_cache
            opts["estimate_label"] = ctk.CTkLabel(
                frame, text="Estimated output size: select a file.", anchor="w",
                text_color=MUTED,
            )
            opts["estimate_label"].pack(fill="x", padx=(85, 0), pady=(4, 0))

            def show_estimate(input_path):
                probe = probe_cache.get(input_path)
                if probe is None:
                    return
                size, duration = self._prores_estimate(
                    probe, opts["profile"].get(), opts["fps"].get()
                )
                if size is None:
                    text = "Estimated output size: unknown (couldn't read duration/resolution)."
                else:
                    m, s = divmod(int(round(duration)), 60)
                    h, m = divmod(m, 60)
                    length = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                    text = f"Estimated output size: ~{self._format_bytes(size)}  (length {length})"
                opts["estimate_label"].configure(text=text)

            def on_input(input_path):
                opts["_current_input"] = input_path
                if input_path in probe_cache:
                    show_estimate(input_path)
                    return
                opts["estimate_label"].configure(text="Estimated output size: reading file...")

                def worker():
                    probe = self._probe_full(input_path) or {}

                    def done():
                        probe_cache[input_path] = probe
                        if opts.get("_current_input") == input_path:
                            show_estimate(input_path)
                    self._run_on_main(done)
                threading.Thread(target=worker, daemon=True).start()

            def on_setting_change(*_args):
                current = opts.get("_current_input")
                if current:
                    show_estimate(current)

            opts["_input_change_callbacks"].append(on_input)
            opts["profile"].trace_add("write", on_setting_change)
            opts["fps"].trace_add("write", on_setting_change)

        def get_probe(inp):
            if inp not in probe_cache:
                probe_cache[inp] = self._probe_full(inp) or {}
            return probe_cache[inp]

        def confirm(input_path, opts):
            size, _duration = self._prores_estimate(
                get_probe(input_path), opts["profile"].get(), opts["fps"].get()
            )
            output_path = opts["output_entry"].get().strip() or input_path
            return self._prores_space_ok(os.path.dirname(os.path.abspath(output_path)), size)

        def cmd_builder(ffmpeg, inp, out, opts):
            opts["_pending_notes"] = []
            return self._prores_build_cmd(
                ffmpeg, inp, out, opts["profile"].get(), opts["hdr_mode"].get(),
                opts["fps"].get(), probe=get_probe(inp), note=opts["_pending_notes"].append,
            )

        def pre_run(opts):
            # Runs after the log is cleared, just before ffmpeg starts.
            notes = opts.pop("_pending_notes", None)
            if notes:
                self._log(opts["_log_box"], "\n".join(notes) + "\n\n")

        self._build_tool_panel(
            parent,
            help_text="ℹ️  ProRes Export\n"
                "Converts your file to Apple ProRes — DaVinci Resolve's preferred high-quality ingest format.\n"
                + self._PRORES_HELP_OPTIMISATIONS +
                "ℹ️  FFmpeg command (typical HD source, ProRes 422):\n"
                "ffmpeg.exe -hide_banner -i <input> -map 0:v:0 -map 0:a? -map_metadata 0 "
                "-vf setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv -fps_mode cfr -r 30000/1001 "
                "-c:v prores_ks -profile:v 2 -vendor apl0 -pix_fmt yuv422p10le -color_primaries bt709 -color_trc bt709 "
                "-colorspace bt709 -color_range tv -c:a pcm_s24le -ar 48000 <output>.mov -y\n\n"
                "To convert a whole folder at once, use Batch ProRes Export.\n"
                "Select a file above and click Run to begin.\n",

            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_prores", ext=".mov"),
            options_builder=options_builder,
            confirm=confirm,
            pre_run=pre_run,
            output_filetypes=[("MOV files", "*.mov"), ("All files", "*.*")],
        )

    def _build_batch_prores_tab(self, parent):
        SEP = "=" * 52
        opts = {}
        files = []
        file_vars = {}
        file_checks = {}
        probe_cache = {}
        scan_state = {"generation": 0}

        log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))
        self._add_log_context_menu(log_box)

        _source_card, source_body = dashboard_card(parent, "Source")
        r1 = ctk.CTkFrame(source_body, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Source Folder:", width=110, anchor="w").pack(side="left")
        folder_ent = ctk.CTkEntry(r1, placeholder_text="Browse -- scans automatically...")
        folder_ent.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_folder():
            init_dir = folder_ent.get().strip() or None
            p = self._ask_folder_with_preview(initial_dir=init_dir, title="Select Source Folder")
            if p:
                folder_ent.delete(0, "end")
                folder_ent.insert(0, p)
                parent.after(150, scan)

        ctk.CTkButton(r1, text="Browse", width=80, command=browse_folder).pack(side="left")

        r2 = ctk.CTkFrame(source_body, fg_color="transparent")
        r2.pack(fill="x")
        self._prores_options_row(r2, opts, label_width=110)

        _files_card, files_body = dashboard_card(parent)
        list_header = ctk.CTkFrame(files_body, fg_color="transparent")
        list_header.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(list_header, text="Files", font=ctk.CTkFont(size=14, weight="bold")).pack(
            side="left", padx=(0, 12))
        selection_label = ctk.CTkLabel(list_header, text="No folder scanned yet.", anchor="w",
                                       text_color=MUTED)
        selection_label.pack(side="left")
        select_none_btn = ctk.CTkButton(list_header, text="Select None", width=90, state="disabled")
        select_none_btn.pack(side="right", padx=(6, 0))
        select_all_btn = ctk.CTkButton(list_header, text="Select All", width=90, state="disabled")
        select_all_btn.pack(side="right")

        file_list = ctk.CTkScrollableFrame(files_body, height=150, fg_color=INSET,
                                           border_width=1, border_color=BORDER, corner_radius=10)
        file_list.pack(fill="x", pady=(0, 4))

        batch_row = ctk.CTkFrame(files_body, fg_color="transparent")
        batch_row.pack(fill="x", pady=(4, 0))
        total_label = ctk.CTkLabel(batch_row, text="", anchor="w", text_color=MUTED)
        total_label.pack(side="left")

        batch_actions = ctk.CTkFrame(batch_row, fg_color="transparent")
        batch_actions.pack(side="right")
        run_btn = AccentButton(batch_actions, text="Convert Selected", width=150, state="disabled")
        run_btn.pack(side="left", padx=(0, 6))
        abort_btn = AccentButton(
            batch_actions, text="Abort", width=110, kind="danger", state="disabled",
            command=self._abort_current_operation
        )
        abort_btn.pack(side="left")

        status_label = ctk.CTkLabel(parent, text="", anchor="w", text_color=MUTED)
        status_label.pack(fill="x", padx=4)
        progress = ctk.CTkProgressBar(parent, mode="determinate", height=6)
        progress.pack(fill="x", padx=4, pady=(2, 8))
        progress.set(0)

        log_box.pack(fill="both", expand=True)
        log_box.configure(state="disabled")
        self._log_with_info_icon(log_box, (
            "ℹ️  Batch ProRes Export\n"
            "Converts every selected video in a folder to Apple ProRes, using the same settings as ProRes Export.\n"
            "Converted files are saved into a PRORES subfolder as <name>_prores.mov.\n\n"
            + self._PRORES_HELP_OPTIMISATIONS +
            "1. Click Browse and pick the folder -- its video files are listed below with checkboxes,\n"
            "   along with each file's length and estimated ProRes size\n"
            "2. Tick/untick individual files\n"
            "3. Choose the Profile, HDR handling and Frame rate\n"
            "4. Click Convert Selected -- progress for each file is shown above this log\n"
        ))

        def file_estimate(path):
            probe = probe_cache.get(path)
            if probe is None:
                return None, None
            return self._prores_estimate(probe, opts["profile"].get(), opts["fps"].get())

        def file_caption(path):
            name = os.path.basename(path)
            if path not in probe_cache:
                return f"{name}   (reading...)"
            size, duration = file_estimate(path)
            if size is None:
                return f"{name}   (size unknown)"
            m, s = divmod(int(round(duration)), 60)
            return f"{name}   ({m}:{s:02d}  ·  ~{self._format_bytes(size)})"

        def refresh_estimates(*_args):
            for path, check in file_checks.items():
                check.configure(text=file_caption(path))
            update_selection_count()

        def update_selection_count():
            total = len(files)
            selected = [f for f in files if file_vars.get(f) and file_vars[f].get()]
            if total == 0:
                selection_label.configure(text="No folder scanned yet.")
                total_label.configure(text="")
            else:
                selection_label.configure(text=f"{len(selected)} of {total} file(s) selected")
                sizes = [file_estimate(f)[0] for f in selected]
                known = sum(s for s in sizes if s)
                pending = any(f not in probe_cache for f in selected)
                if selected:
                    suffix = " (still reading some files...)" if pending else ""
                    total_label.configure(
                        text=f"Estimated total output: ~{self._format_bytes(known)}{suffix}"
                    )
                else:
                    total_label.configure(text="")
            if not self._operation_running:
                run_btn.configure(state="normal" if selected else "disabled")

        def select_all():
            for v in file_vars.values():
                v.set(True)
            update_selection_count()

        def select_none():
            for v in file_vars.values():
                v.set(False)
            update_selection_count()

        select_all_btn.configure(command=select_all)
        select_none_btn.configure(command=select_none)
        opts["profile"].trace_add("write", refresh_estimates)
        opts["fps"].trace_add("write", refresh_estimates)

        def scan():
            nonlocal files
            scan_state["generation"] += 1
            generation = scan_state["generation"]
            for child in file_list.winfo_children():
                child.destroy()
            file_vars.clear()
            file_checks.clear()

            folder = folder_ent.get().strip()
            if not folder or not os.path.isdir(folder):
                files = []
                select_all_btn.configure(state="disabled")
                select_none_btn.configure(state="disabled")
                update_selection_count()
                return
            files = sorted(
                (os.path.abspath(os.path.join(folder, f)) for f in os.listdir(folder)
                 if f.lower().endswith(self._BATCH_VIDEO_EXTS)
                 and not f.lower().endswith("_prores.mov")
                 and os.path.isfile(os.path.join(folder, f))),
                key=str.lower,
            )

            self._clear_log(log_box)
            if not files:
                self._log(log_box, f"No video files found in:\n{folder}\n")
                select_all_btn.configure(state="disabled")
                select_none_btn.configure(state="disabled")
                update_selection_count()
                return

            for f in files:
                var = ctk.BooleanVar(value=True)
                file_vars[f] = var
                check = ctk.CTkCheckBox(
                    file_list, text=file_caption(f), variable=var,
                    command=update_selection_count,
                )
                check.pack(anchor="w", padx=6, pady=2)
                file_checks[f] = check

            select_all_btn.configure(state="normal")
            select_none_btn.configure(state="normal")
            update_selection_count()

            # Probe in the background; each row fills in its length/size as it arrives.
            pending = [f for f in files if f not in probe_cache]

            def worker():
                for path in pending:
                    if scan_state["generation"] != generation:
                        return
                    probe = self._probe_full(path) or {}

                    def done(path=path, probe=probe):
                        probe_cache[path] = probe
                        if scan_state["generation"] == generation and path in file_checks:
                            file_checks[path].configure(text=file_caption(path))
                            update_selection_count()
                    self._run_on_main(done)
            if pending:
                threading.Thread(target=worker, daemon=True).start()

        def set_status(text, fraction=None):
            def apply():
                status_label.configure(text=text)
                if fraction is not None:
                    progress.set(max(0.0, min(1.0, fraction)))
            self._run_on_main(apply)

        def convert_selected():
            selected = [f for f in files if file_vars.get(f) and file_vars[f].get()]
            if not selected:
                return
            if not self._ffmpeg_path or not os.path.isfile(self._ffmpeg_path):
                self._log(log_box, "Error: ffmpeg not found. Set its location in Settings.\n")
                return
            folder = folder_ent.get().strip()
            out_dir = os.path.join(folder, "PRORES")
            total_size = sum(file_estimate(f)[0] or 0 for f in selected)
            if not self._prores_space_ok(out_dir, total_size, what="this batch"):
                self._log(log_box, "Cancelled.\n")
                return
            os.makedirs(out_dir, exist_ok=True)

            profile_name = opts["profile"].get()
            hdr_mode = opts["hdr_mode"].get()
            fps_label = opts["fps"].get()

            self._abort_event.clear()
            self._set_operation_running(True)
            run_btn.configure(state="disabled")
            abort_btn.configure(state="normal")
            progress.set(0)

            def worker():
                count = len(selected)
                self._log(log_box, f"\n{SEP}\nConverting {count} file(s) -> {profile_name}\n{SEP}\n\n")
                ok = fail = 0
                started = time.time()

                for i, inp in enumerate(selected, 1):
                    if self._abort_event.is_set():
                        break
                    base = os.path.splitext(os.path.basename(inp))[0]
                    outp = os.path.join(out_dir, f"{base}_prores.mov")
                    self._log(log_box, f"[{i}/{count}] {os.path.basename(inp)} -> PRORES\\{base}_prores.mov\n")

                    probe = probe_cache.get(inp)
                    if probe is None:
                        probe = self._probe_full(inp) or {}
                        probe_cache[inp] = probe
                    _size, duration = self._prores_estimate(probe, profile_name, fps_label)
                    notes = []
                    cmd = self._prores_build_cmd(
                        self._ffmpeg_path, inp, outp, profile_name, hdr_mode, fps_label,
                        probe=probe, note=notes.append,
                    )
                    for text in notes:
                        self._log(log_box, f"         {text}\n")
                    # Quiet ffmpeg; machine-readable progress on stdout, errors still come through.
                    cmd[1:1] = ["-v", "error", "-nostats", "-progress", "pipe:1"]

                    set_status(f"[{i}/{count}] {os.path.basename(inp)} -- starting...", (i - 1) / count)
                    try:
                        proc = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            universal_newlines=True,
                            errors="replace",
                            **SUBPROCESS_WINDOW_KWARGS
                        )
                        self._active_process = proc
                        speed = ""
                        for line in proc.stdout:
                            line = line.strip()
                            key, sep, value = line.partition("=")
                            if sep and re.fullmatch(r"[a-z0-9_]+", key):
                                if key == "speed":
                                    speed = value
                                elif key == "out_time_us" and duration:
                                    try:
                                        frac = max(0.0, int(value) / 1_000_000 / duration)
                                    except ValueError:
                                        continue
                                    frac = min(frac, 1.0)
                                    set_status(
                                        f"[{i}/{count}] {os.path.basename(inp)} -- "
                                        f"{frac * 100:.0f}%  (speed {speed or '?'})",
                                        (i - 1 + frac) / count,
                                    )
                            elif line:
                                self._log(log_box, f"         {line}\n")
                        proc.wait()
                        self._active_process = None

                        if self._abort_event.is_set():
                            self._remove_partial(outp)
                            break
                        if proc.returncode == 0:
                            self._log(log_box, "         OK Done\n")
                            ok += 1
                        else:
                            self._log(log_box, f"         FAILED ({proc.returncode})\n")
                            self._remove_partial(outp)
                            fail += 1
                    except Exception as e:
                        self._active_process = None
                        self._log(log_box, f"         ERROR: {str(e)}\n")
                        self._remove_partial(outp)
                        fail += 1

                elapsed = int(time.time() - started)
                if self._abort_event.is_set():
                    self._log(log_box, "\nAborted -- the unfinished file was removed.\n")
                    set_status("Aborted.")
                else:
                    set_status(f"Finished: {ok} converted, {fail} failed.", 1.0)
                self._log(
                    log_box,
                    f"\n{SEP}\n{ok} converted, {fail} failed  "
                    f"(time {elapsed // 60}:{elapsed % 60:02d})\nOutput folder: {out_dir}\n{SEP}\n",
                )
                parent.after(0, lambda: abort_btn.configure(state="disabled"))
                parent.after(0, lambda: self._set_operation_running(False))
                parent.after(0, update_selection_count)

            threading.Thread(target=worker, daemon=True).start()

        run_btn.configure(command=convert_selected)
        # A pasted/typed folder path scans on Enter too, not only via Browse.
        folder_ent.bind("<Return>", lambda _e: scan())

    @staticmethod
    def _remove_partial(path):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass

    def _build_fix_timestamps_tab(self, parent):
        def cmd_builder(ffmpeg, inp, out, opts):
            return [ffmpeg, "-hide_banner", "-fflags", "+genpts+igndts", "-i", inp,
                    "-map", "0:v:0", "-map", "0:a?", "-c", "copy", "-bitexact", out, "-y"]

        self._build_tool_panel(
            parent,
            help_text="ℹ️  Fix Timestamps\nRegenerates missing or corrupt presentation timestamps (PTS).\n"
               "Regenerates missing or corrupt presentation timestamps (PTS) across the file timeline.\n"
                "Use this when footage plays back with stuttering, freezing, skipping, or severe audio sync drift in DaVinci Resolve.\n\n"
                "ℹ️  FFmpeg command (Fast Remux):\n"
                "ffmpeg.exe -hide_banner -fflags +genpts+igndts -i <input> -map 0:v:0 -map 0:a? -c copy -bitexact <output> -y\n\n"
                "Select a file above and click Run to begin.\n",

            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_fixed_ts"),
        )

    def _build_trim_clip_tab(self, parent):
        state = {
            "current_input": None,
            "duration": None,
            "request_id": 0,
            "preview_job": None,
            "action_frame": None,
            "preview_path": os.path.join(
                tempfile.gettempdir(), f"ffmpeg_toolkit_trim_preview_{os.getpid()}.jpg"
            ),
        }

        def options_builder(frame, opts, on_change):
            # Two-column layout: a narrow left sidebar holding Trim & SAVE /
            # Abort, and a larger preview area (image + video + control bar)
            # filling the remaining width. main_row's height is pinned so
            # both columns stay visible no matter what state the preview is in.
            main_row = ctk.CTkFrame(frame, fg_color="transparent", height=340)
            main_row.pack(fill="x", pady=(0, 8))
            main_row.pack_propagate(False)

            left_col = ctk.CTkFrame(main_row, fg_color="transparent", width=220)
            left_col.pack(side="left", fill="y", padx=(0, 10))
            left_col.pack_propagate(False)

            preview_frame = ctk.CTkFrame(main_row, fg_color=INSET, border_width=1,
                                         border_color=BORDER, width=400)
            preview_frame.pack(side="left", fill="both", expand=True)
            # Without this, preview_frame's own footprint follows whichever
            # child currently has the larger natural size -- the static
            # thumbnail (scaled up to 640px wide) demands much more width
            # than the empty video_host frame does, so the row would quietly
            # inflate/shrink (and the control bar with it) depending on
            # whether a video is playing. Pinning it here makes the preview
            # area's size constant regardless of what's shown inside it.
            preview_frame.pack_propagate(False)

            # preview_area is packed exactly once, right here, before the
            # control bar / range label below it exist -- so its position at
            # the top of preview_frame's stack is permanent. preview_label
            # and video_host live *inside* it and are swapped with plain
            # pack()/pack_forget() -- since preview_area itself never moves,
            # neither can its children end up on the wrong side of the
            # control bar, regardless of how many times playback starts/stops.
            preview_area = ctk.CTkFrame(preview_frame, fg_color="transparent")
            preview_area.pack(fill="both", expand=True, padx=8, pady=(8, 4))

            opts["preview_label"] = ctk.CTkLabel(
                preview_area,
                text="Select a video to load its preview.",
                height=200,
            )
            opts["preview_label"].pack(fill="both", expand=True)

            # Hosts the embedded ffplay window during range playback; swapped
            # in/out with preview_label via show_video_host()/show_preview_label().
            video_host = tk.Frame(preview_area, bg="black", highlightthickness=0, bd=0)
            state["embedded_hwnd"] = None

            def show_video_host():
                opts["preview_label"].pack_forget()
                video_host.pack(fill="both", expand=True)

            def show_preview_label():
                video_host.pack_forget()
                opts["preview_label"].pack(fill="both", expand=True)

            def on_video_host_configure(event):
                hwnd = state.get("embedded_hwnd")
                if not hwnd or sys.platform != "win32":
                    return
                try:
                    import ctypes
                    ctypes.windll.user32.MoveWindow(hwnd, 0, 0, event.width, event.height, True)
                except Exception:
                    pass

            video_host.bind("<Configure>", on_video_host_configure)

            # ---- Video control bar (Play/Pause, Stop, scrubber, time,

            # mute, pop-out) -- styled like a normal media-player transport
            # bar and docked directly under the preview/video area. ----
            control_bar = ctk.CTkFrame(
                preview_frame, corner_radius=18, fg_color=CARD_2, border_width=1,
                border_color=BORDER, height=48
            )
            # Packed from the bottom *before* preview_area in pack order, so
            # Tk allocates the bar its full 48px first and any shortfall is
            # taken from the preview image/video instead of the bar.
            control_bar.pack(side="bottom", fill="x", padx=8, pady=(0, 4), before=preview_area)
            control_bar.pack_propagate(False)

            icon_font = ctk.CTkFont(size=15)
            small_icon_font = ctk.CTkFont(size=12)

            play_pause_btn = ctk.CTkButton(
                control_bar, text="\u25b6", width=34, height=34, corner_radius=17,
                fg_color="transparent", hover_color=HOVER, border_width=0, font=icon_font,
                command=lambda: play_or_pause(),
            )
            play_pause_btn.pack(side="left", padx=(8, 2), pady=7)

            stop_ctrl_btn = ctk.CTkButton(
                control_bar, text="\u23f9", width=30, height=30, corner_radius=15,
                fg_color="transparent", hover_color=HOVER, border_width=0, font=small_icon_font,
                state="disabled", command=lambda: stop_playback(),
            )
            stop_ctrl_btn.pack(side="left", padx=2, pady=7)

            expand_btn = ctk.CTkButton(
                control_bar, text="\u2922", width=28, height=28, corner_radius=14,
                fg_color="transparent", hover_color=HOVER, border_width=0, font=small_icon_font,
                state="disabled", command=lambda: pop_out(),
            )
            expand_btn.pack(side="right", padx=(2, 8), pady=7)

            volume_btn = ctk.CTkButton(
                control_bar, text="\U0001f50a", width=28, height=28, corner_radius=14,
                fg_color="transparent", hover_color=HOVER, border_width=0, font=small_icon_font,
                state="disabled", command=lambda: toggle_mute(),
            )
            volume_btn.pack(side="right", padx=2, pady=7)

            time_label = ctk.CTkLabel(
                control_bar, text="0:00/0:00", text_color=MUTED,
                width=84, anchor="e", font=ctk.CTkFont(size=12),
            )
            time_label.pack(side="right", padx=(4, 4), pady=7)

            def on_slider_move(value):
                if state.get("user_seeking"):
                    update_time_label(value)

            progress_slider = ctk.CTkSlider(
                control_bar, from_=0, to=1, number_of_steps=1000, height=12,
                progress_color=BLUE, button_color=TEXT,
                button_hover_color="#ffffff", fg_color=BORDER,
                command=on_slider_move,
            )
            progress_slider.set(0)
            progress_slider.pack(side="left", fill="x", expand=True, padx=10, pady=7)

            def format_mmss(secs):
                secs = max(0, int(round(secs)))
                m, s = divmod(secs, 60)
                return f"{m}:{s:02d}"

            def update_time_label(elapsed_seconds):
                total = state.get("segment_duration", 0.0)
                time_label.configure(text=f"{format_mmss(elapsed_seconds)}/{format_mmss(total)}")

            def elapsed():
                if state.get("playback_paused"):
                    return min(state.get("playback_offset_base", 0.0), state.get("segment_duration", 0.0))
                base = state.get("playback_offset_base", 0.0)
                started = state.get("playback_started_at")
                if started is None:
                    return base
                e = base + (time.time() - started)
                return max(0.0, min(e, state.get("segment_duration", 0.0)))

            def tick():
                process = self._trim_play_process
                if not process or process.poll() is not None:
                    state["ticker_job"] = None
                    return
                if not state.get("user_seeking") and not state.get("playback_paused"):
                    e = elapsed()
                    progress_slider.set(e)
                    update_time_label(e)
                state["ticker_job"] = self.after(200, tick)

            def stop_ticker():
                job = state.get("ticker_job")
                if job:
                    try:
                        self.after_cancel(job)
                    except Exception:
                        pass
                state["ticker_job"] = None

            def start_ticker():
                stop_ticker()
                tick()

            def on_slider_press(_event=None):
                state["user_seeking"] = True

            def on_slider_release(_event=None):
                state["user_seeking"] = False
                target = progress_slider.get()
                if self._trim_play_process and self._trim_play_process.poll() is None:
                    start_playback(offset=target)
                else:
                    update_time_label(target)

            try:
                progress_slider.bind("<Button-1>", on_slider_press)
                progress_slider.bind("<ButtonRelease-1>", on_slider_release)
            except Exception:
                pass

            range_label = ctk.CTkLabel(
                preview_frame, text="Range: select a video to enable the trim controls.",
                anchor="w",
            )
            range_label.pack(side="bottom", fill="x", padx=8, pady=(0, 8), before=control_bar)

            # Stream picker: which audio languages / subtitles to carry into
            # the trimmed file. Filled per-file by populate_streams() once the
            # input has been probed. Expanding also pushes the Trim & SAVE /
            # Abort buttons (added below via button_container) to the bottom.
            streams_frame = ctk.CTkScrollableFrame(
                left_col, fg_color=INSET, border_width=1, border_color=BORDER,
                label_fg_color=CARD_2, label_text="Preserve in Output File", height=120
            )
            # Packed further down, after action_frame: see there.
            opts["_audio_track_vars"] = []
            opts["_audio_defaults"] = []
            opts["_subtitle_track_vars"] = []

            def show_streams_message(text):
                for child in streams_frame.winfo_children():
                    child.destroy()
                ctk.CTkLabel(
                    streams_frame, text=text, wraplength=170, justify="left", anchor="w"
                ).pack(fill="x", padx=4, pady=4)

            def populate_streams(audio_streams, subtitle_streams, input_path):
                if state.get("current_input") != input_path:
                    return
                for child in streams_frame.winfo_children():
                    child.destroy()
                opts["_audio_track_vars"] = []
                opts["_audio_defaults"] = []
                opts["_subtitle_track_vars"] = []

                ctk.CTkLabel(
                    streams_frame, text="Audio", anchor="w",
                    font=ctk.CTkFont(weight="bold"),
                ).pack(fill="x", padx=4, pady=(2, 2))
                if not audio_streams:
                    ctk.CTkLabel(streams_frame, text="No audio tracks", anchor="w").pack(
                        fill="x", padx=4
                    )
                for i, stream in enumerate(audio_streams):
                    tags = stream.get("tags", {}) or {}
                    language = tags.get("language", "und")
                    var = ctk.BooleanVar(value=True)
                    box = ctk.CTkCheckBox(
                        streams_frame,
                        text=f"{i}: {language} ({stream.get('codec_name', '?')}, "
                             f"{stream.get('channels', '?')}ch)",
                        variable=var,
                    )
                    box.pack(fill="x", padx=4, pady=2)
                    if tags.get("title"):
                        CTkToolTip(box, tags["title"])
                    opts["_audio_track_vars"].append(var)
                    opts["_audio_defaults"].append(
                        bool((stream.get("disposition") or {}).get("default"))
                    )

                ctk.CTkLabel(
                    streams_frame, text="Subtitles", anchor="w",
                    font=ctk.CTkFont(weight="bold"),
                ).pack(fill="x", padx=4, pady=(8, 2))
                if not subtitle_streams:
                    ctk.CTkLabel(streams_frame, text="No subtitles", anchor="w").pack(
                        fill="x", padx=4
                    )
                for i, stream in enumerate(subtitle_streams):
                    tags = stream.get("tags", {}) or {}
                    language = tags.get("language", "und")
                    codec = SUBTITLE_CODEC_NAMES.get(
                        stream.get("codec_name"), stream.get("codec_name", "?")
                    )
                    forced = (stream.get("disposition") or {}).get("forced")
                    var = ctk.BooleanVar(value=True)
                    box = ctk.CTkCheckBox(
                        streams_frame,
                        text=f"{i}: {language} ({codec}{', forced' if forced else ''})",
                        variable=var,
                    )
                    box.pack(fill="x", padx=4, pady=2)
                    if tags.get("title"):
                        CTkToolTip(box, tags["title"])
                    opts["_subtitle_track_vars"].append(var)

            show_streams_message("Select a video to list its audio and subtitle tracks.")

            # The buttons are packed first (from the bottom) so they always get
            # their full height; the track list then takes whatever is left and
            # scrolls. Packed the other way round, the list squeezed the
            # Trim & SAVE / Abort buttons out of sight.
            action_frame = ctk.CTkFrame(left_col, fg_color="transparent")
            action_frame.pack(side="bottom", fill="x")
            state["action_frame"] = action_frame
            streams_frame.pack(side="top", fill="both", expand=True, pady=(0, 6))

            def show_important_info():
                title = "Clip & Track Editor - Important Information"
                self._center_next_messagebox(
                    title,
                    text_width=min(
                        int(self.winfo_width() * 0.65),
                        int(720 * self.winfo_fpixels("1i") / 96),
                    ),
                )
                messagebox.showinfo(
                    title,
                    "The Clip & Track Editor does two jobs, and it can do both at once:\n"
                    "  • Trim a section out of a video.\n"
                    "  • Choose which audio languages and subtitles to keep.\n\n"
                    "Nothing is re-encoded. The video, audio and subtitles are copied "
                    "exactly as they are, \nso saving is very fast and there is no loss "
                    "of quality.\n\n"
                    "HOW TO USE IT\n"
                    "  1. Select a video file. The output filename is generated for you "
                    "(ending in \"_trim\"), but you can change it.\n"
                    "  2. Drag the two handles of the range slider to set the start and "
                    "end of the section to keep.\n"
                    "  3. Use the play controls to preview the selected section.\n"
                    "  4. Under \"Keep in Output\", tick the audio tracks and subtitles "
                    "you want and untick the rest.\n"
                    "  5. Click \"Trim & SAVE\". You can Abort while it is saving.\n\n"
                    "EDITING LANGUAGES ONLY\n"
                    "To change the tracks without trimming, leave the range slider "
                    "covering the whole video. \nYou get the full video back with only "
                    "the audio and subtitles you ticked, \ne.g. to remove unwanted dubbed "
                    "languages or foreign subtitles.\n\n"
                    "AUDIO TRACKS\n"
                    "  • Each track shows its number, language, format and channel count. "
                    "Hover over a track to see its title, if it has one.\n"
                    "  • If you untick the track that players choose automatically, the "
                    "first ticked track takes over that role.\n"
                    "  • If you untick every audio track, you will be asked to confirm, "
                    "because the clip will have no sound.\n\n"
                    "SUBTITLES\n"
                    "  • Each subtitle shows its number, language and format. \"forced\" "
                    "marks subtitles that only translate foreign dialogue or signs.\n"
                    "  • Text subtitles (SRT, ASS) and picture subtitles (PGS, VobSub) are "
                    "both copied unchanged.\n"
                    "  • Fonts embedded in the file (used by styled ASS subtitles) are kept "
                    "as long as at least one subtitle is ticked.\n\n"
                    "THINGS TO KNOW\n"
                    "  • Because nothing is re-encoded, the cut can only fall on a "
                    "keyframe, so the start may be slightly off from the handle.\n"
                    "  • Language codes come from the file itself. \"und\" means the "
                    "track has no language tag.\n"
                    "  • Keep the same file type as the original (e.g. MKV to MKV). Some "
                    "types, such as MP4, can't hold every subtitle format.",
                )

            important_btn = ctk.CTkButton(
                action_frame, text="\u26A0  Important Information",
                fg_color=WARN_FILL, hover_color=WARN_HOVER, border_color="#6b5a2e",
                text_color=AMBER, font=ctk.CTkFont(size=12, weight="bold"),
                command=show_important_info,
            )
            important_btn.pack(fill="x", pady=(0, 8))

            def update_play_button_state(playing, paused=False):
                if not playing:
                    play_pause_btn.configure(text="\u25b6")
                    stop_ctrl_btn.configure(state="disabled")
                else:
                    play_pause_btn.configure(text="\u25b6" if paused else "\u23f8")
                    stop_ctrl_btn.configure(state="normal")

            def monitor_playback(process):
                process.wait()
                def finished():
                    if self._trim_play_process is process:
                        self._trim_play_process = None
                        self._trim_play_window_title = None
                        self._trim_play_hwnd = None
                        state["playback_paused"] = False
                        state["embedded_hwnd"] = None
                        stop_ticker()
                        show_preview_label()
                        update_play_button_state(False)
                        progress_slider.set(0)
                        update_time_label(0)
                        expand_btn.configure(state="disabled")
                        volume_btn.configure(state="disabled")
                self._run_on_main(finished)

            def try_embed(window_title, attempts=25):
                def worker():
                    hwnd = None
                    for _ in range(attempts):
                        hwnd = self._find_ffplay_hwnd(window_title)
                        if hwnd:
                            break
                        time.sleep(0.15)

                    def apply():
                        # Bail out quietly if playback was stopped/replaced
                        # while we were waiting for the window to appear.
                        if self._trim_play_window_title != window_title:
                            return
                        if not hwnd:
                            log_box = opts.get("_log_box")
                            if log_box:
                                self._log(
                                    log_box,
                                    "Couldn't find the preview window to embed it -- "
                                    "it may still open separately.\n",
                                )
                            show_preview_label()
                            return
                        # Cache the hwnd regardless of embed success -- pause
                        # and mute need it directly since, once embedded, the
                        # window is a child and title-based lookups stop working.
                        self._trim_play_hwnd = hwnd
                        if self._embed_external_window(hwnd, video_host):
                            state["embedded_hwnd"] = hwnd
                            w = max(video_host.winfo_width(), 1)
                            h = max(video_host.winfo_height(), 1)
                            try:
                                import ctypes
                                ctypes.windll.user32.MoveWindow(hwnd, 0, 0, w, h, True)
                            except Exception:
                                pass
                        else:
                            show_preview_label()
                            log_box = opts.get("_log_box")
                            if log_box:
                                self._log(
                                    log_box,
                                    "Couldn't embed the preview window; it will play "
                                    "in a separate window instead.\n",
                                )
                            self._bring_ffplay_to_front(window_title)
                        expand_btn.configure(state="normal")
                        volume_btn.configure(state="normal")

                    self._run_on_main(apply)

                threading.Thread(target=worker, daemon=True).start()

            def start_playback(offset=0.0):
                log_box = opts.get("_log_box")
                input_path = state.get("current_input")
                if not input_path or not os.path.isfile(input_path):
                    if log_box:
                        self._log(log_box, "Error: Select a video first.\n")
                    return
                start = opts.get("start_seconds")
                end = opts.get("end_seconds")
                if start is None or end is None or end <= start:
                    if log_box:
                        self._log(log_box, "Error: Define a valid trim range first.\n")
                    return
                player_path = self._ffplay_path
                if not player_path or not os.path.isfile(player_path):
                    if log_box:
                        self._log(
                            log_box,
                            "Error: ffplay not found. Place ffplay next to ffmpeg "
                            "(or on PATH) to enable range playback.\n",
                        )
                    return
                segment_duration = end - start
                offset = max(0.0, min(offset, max(segment_duration - 0.05, 0.0)))
                # Always stop any clip already playing (this tab or a prior one)
                # before starting a new one, so audio never overlaps.
                self._stop_trim_playback()
                stop_ticker()
                show_video_host()
                window_title = f"Trim Range Preview - {os.path.basename(input_path)}"
                cmd = [
                    player_path, "-hide_banner", "-autoexit",
                    "-window_title", window_title,
                    "-ss", self._format_seconds_as_timecode(start + offset),
                    "-t", self._format_seconds_as_timecode(segment_duration - offset),
                    input_path,
                ]
                state["segment_duration"] = segment_duration
                state["playback_offset_base"] = offset
                state["playback_started_at"] = time.time()
                state["playback_paused"] = False
                state["user_seeking"] = False
                progress_slider.configure(to=max(segment_duration, 0.001))
                progress_slider.set(offset)
                update_time_label(offset)

                def worker():
                    try:
                        process = subprocess.Popen(cmd, **PLAYER_SUBPROCESS_KWARGS)
                    except Exception as exc:
                        if log_box:
                            self.after(
                                0,
                                lambda: self._log(log_box, f"Error launching player: {exc}\n"),
                            )
                        return
                    self._trim_play_process = process
                    self._trim_play_window_title = window_title
                    self._run_on_main(lambda: update_play_button_state(True, False))
                    try_embed(window_title)
                    self._run_on_main(start_ticker)
                    monitor_playback(process)

                threading.Thread(target=worker, daemon=True).start()

            def toggle_pause():
                process = self._trim_play_process
                hwnd = self._trim_play_hwnd
                log_box = opts.get("_log_box")
                if not process or process.poll() is not None:
                    return
                sent = self._send_ffplay_pause_toggle(hwnd)
                if not sent:
                    if log_box:
                        self._log(
                            log_box,
                            "Couldn't reach the player window to toggle pause -- "
                            "click into it and press Spacebar.\n",
                        )
                    return
                now_paused = not state.get("playback_paused", False)
                if now_paused:
                    state["playback_offset_base"] = elapsed()
                else:
                    state["playback_started_at"] = time.time()
                state["playback_paused"] = now_paused
                update_play_button_state(True, now_paused)

            def play_or_pause():
                process = self._trim_play_process
                if process and process.poll() is None:
                    toggle_pause()
                else:
                    start_playback()

            def toggle_mute():
                hwnd = self._trim_play_hwnd
                log_box = opts.get("_log_box")
                if not hwnd:
                    return
                sent = self._send_ffplay_key(hwnd, 0x4D)  # VK 'M'
                if not sent and log_box:
                    self._log(log_box, "Couldn't reach the player window to toggle mute.\n")

            def pop_out():
                hwnd = self._trim_play_hwnd
                if not hwnd:
                    return
                if self._unembed_window(hwnd):
                    state["embedded_hwnd"] = None
                    show_preview_label()

            def stop_playback():
                self._stop_trim_playback()
                state["playback_paused"] = False
                state["embedded_hwnd"] = None
                stop_ticker()
                show_preview_label()
                update_play_button_state(False)
                progress_slider.set(0)
                update_time_label(0)
                expand_btn.configure(state="disabled")
                volume_btn.configure(state="disabled")

            # Start | ◀ range finder hint ▶ | Duration. Grid keeps the hint
            # centred while the timecodes hug the edges.
            values_row = ctk.CTkFrame(frame, fg_color="transparent")
            values_row.pack(fill="x", pady=(0, 5))
            values_row.grid_columnconfigure((0, 2), weight=1, uniform="ends")
            opts["start_label"] = ctk.CTkLabel(
                values_row, text="Start: 00:00:00.00", anchor="w"
            )
            opts["start_label"].grid(row=0, column=0, sticky="w")

            hint_frame = ctk.CTkFrame(values_row, fg_color="transparent")
            hint_frame.grid(row=0, column=1, padx=10)
            arrow_color = AMBER
            ctk.CTkLabel(
                hint_frame, text="◀", text_color=arrow_color,
                font=ctk.CTkFont(size=16),
            ).pack(side="left", padx=(0, 12))
            ctk.CTkLabel(
                hint_frame,
                text="use the Range Finder to define the START & END points "
                     "of the saved OUTPUT FILE",
                text_color=LINK,
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(side="left")
            ctk.CTkLabel(
                hint_frame, text="▶", text_color=arrow_color,
                font=ctk.CTkFont(size=16),
            ).pack(side="left", padx=(12, 0))

            opts["duration_label"] = ctk.CTkLabel(
                values_row, text="Duration: 00:00:00.00", anchor="e"
            )
            opts["duration_label"].grid(row=0, column=2, sticky="e")

            opts["range_slider"] = CTkRangeSlider(
                frame, min_val=0.0, max_val=1.0, start_val=0.0, end_val=1.0,
                height=42, command=lambda start, end: range_changed(start, end),
            )
            opts["range_slider"].pack(fill="x", pady=(0, 5))
            opts["range_slider"].enabled = False

            def update_labels(start, end):
                duration = max(0.0, end - start)
                opts["start_seconds"] = start
                opts["end_seconds"] = end
                opts["start_label"].configure(
                    text=f"Start: {self._format_seconds_as_timecode(start)}"
                )
                opts["duration_label"].configure(
                    text=f"Duration: {self._format_seconds_as_timecode(duration)}"
                )
                range_label.configure(
                    text=(
                        f"Selected: {self._format_seconds_as_timecode(start)} - "
                        f"{self._format_seconds_as_timecode(end)}"
                    )
                )
                # Keep the transport bar's total time in sync with the
                # selected range, reset to the (new) start position.
                state["segment_duration"] = duration
                progress_slider.configure(to=max(duration, 0.001))
                progress_slider.set(0)
                update_time_label(0)

            def range_changed(start, end):
                # Moving the RangeFinder invalidates whatever's currently
                # playing (it was for the old range), so stop it first, then
                # sync the transport bar to the new range at time-zero.
                if self._trim_play_process and self._trim_play_process.poll() is None:
                    stop_playback()
                update_labels(start, end)
                schedule_preview(start, opts)

            def apply_preview(ok, request_id, seconds):
                if request_id != state["request_id"]:
                    return
                if not ok:
                    opts["preview_label"].configure(
                        image=None,
                        text="Preview unavailable for this position.",
                    )
                    return
                try:
                    image = PilImage.open(state["preview_path"])
                    image.load()
                    width, height = image.size
                    # Capped so image + control bar + range label fit inside
                    # main_row's fixed 340px height without squashing the bar.
                    scale = min(640 / width, 240 / height, 1.0)
                    preview_size = (max(1, round(width * scale)), max(1, round(height * scale)))
                    preview_image = ctk.CTkImage(
                        light_image=image, dark_image=image, size=preview_size
                    )
                    opts["preview_label"].configure(image=preview_image, text="")
                    opts["preview_image"] = preview_image
                    range_label.configure(
                        text=(
                            f"Preview: {self._format_seconds_as_timecode(seconds)}  |  "
                            f"Selected: {self._format_seconds_as_timecode(opts['start_seconds'])} - "
                            f"{self._format_seconds_as_timecode(opts['end_seconds'])}"
                        )
                    )
                except Exception:
                    opts["preview_label"].configure(
                        image=None, text="Preview extracted but could not be loaded."
                    )

            def extract_preview(seconds):
                input_path = state.get("current_input")
                if not input_path or not os.path.isfile(input_path):
                    return
                if not self._ffmpeg_path or not os.path.isfile(self._ffmpeg_path):
                    opts["preview_label"].configure(
                        image=None, text="ffmpeg not found -- set its location in Settings."
                    )
                    return
                state["request_id"] += 1
                request_id = state["request_id"]
                cmd = [
                    self._ffmpeg_path, "-hide_banner", "-y",
                    "-ss", self._format_seconds_as_timecode(seconds),
                    "-i", input_path, "-frames:v", "1", "-update", "1",
                    "-sws_flags", "accurate_rnd+spline", state["preview_path"],
                ]

                def worker():
                    try:
                        result = subprocess.run(
                            cmd, capture_output=True, timeout=20, **SUBPROCESS_WINDOW_KWARGS
                        )
                        ok = result.returncode == 0 and os.path.isfile(state["preview_path"])
                    except Exception:
                        ok = False
                    self._run_on_main(lambda: apply_preview(ok, request_id, seconds))

                threading.Thread(target=worker, daemon=True).start()

            def schedule_preview(seconds, _opts):
                if state.get("preview_job"):
                    try:
                        self.after_cancel(state["preview_job"])
                    except Exception:
                        pass
                state["preview_job"] = self.after(150, lambda: extract_preview(seconds))

            def on_duration_ready(duration, input_path):
                if state.get("current_input") != input_path:
                    return
                state["duration"] = duration
                slider = opts["range_slider"]
                if duration is None or duration <= 0:
                    slider.enabled = False
                    opts["preview_label"].configure(
                        image=None, text="Could not determine video duration."
                    )
                    return
                slider.max_val = duration
                slider.min_val = 0.0
                slider.enabled = True
                slider.set_range(0.0, duration)
                update_labels(0.0, duration)
                schedule_preview(0.0, opts)

            def load_input(input_path):
                if input_path == state.get("current_input"):
                    return
                self._stop_trim_playback()
                state["playback_paused"] = False
                state["embedded_hwnd"] = None
                stop_ticker()
                show_preview_label()
                update_play_button_state(False)
                progress_slider.set(0)
                update_time_label(0)
                expand_btn.configure(state="disabled")
                volume_btn.configure(state="disabled")
                state["current_input"] = input_path
                state["duration"] = None
                opts["range_slider"].enabled = False
                opts["preview_label"].configure(
                    image=None, text="Reading video duration..."
                )
                opts["_audio_track_vars"] = []
                opts["_audio_defaults"] = []
                opts["_subtitle_track_vars"] = []
                show_streams_message("Reading tracks...")

                def probe_duration():
                    duration = self._get_media_duration_seconds(input_path)
                    self._run_on_main(lambda: on_duration_ready(duration, input_path))

                def probe_streams():
                    data = self._probe_full(input_path) or {}
                    streams = data.get("streams", [])
                    audio = [s for s in streams if s.get("codec_type") == "audio"]
                    subtitles = [s for s in streams if s.get("codec_type") == "subtitle"]
                    self.after(
                        0, lambda: populate_streams(audio, subtitles, input_path)
                    )

                threading.Thread(target=probe_duration, daemon=True).start()
                threading.Thread(target=probe_streams, daemon=True).start()

            opts["_input_change_callbacks"].append(load_input)

            update_labels(0.0, 1.0)

            # Force geometry to settle immediately rather than lazily on the
            # next idle pass -- without this, the very first paint (before
            # any tab switch, resize, or video load nudges Tk into
            # recomputing layout) can render the control bar cramped even
            # though everything is sized correctly from then on. A follow-up
            # pass shortly after covers CTk's canvas-based widgets (rounded
            # buttons/slider), which don't always fully re-settle from a
            # synchronous update during construction alone.
            self.update_idletasks()
            self.after(50, self.update_idletasks)

        def cmd_builder(ffmpeg, inp, out, opts):
            start = self._format_seconds_as_timecode(opts["start_seconds"])
            duration = self._format_seconds_as_timecode(
                opts["end_seconds"] - opts["start_seconds"]
            )
            cmd = [
                ffmpeg, "-hide_banner", "-i", inp,
                "-ss", start,
                "-t", duration,
                "-map", "0:v:0",
            ]

            track_vars = opts.get("_audio_track_vars", [])
            if track_vars:
                kept = [i for i, var in enumerate(track_vars) if var.get()]
                for i in kept:
                    cmd.extend(["-map", f"0:a:{i}"])
                # If the source's default track was dropped, flag the first
                # kept track as default so players still auto-select audio.
                defaults = opts.get("_audio_defaults", [])
                if kept and not any(defaults[i] for i in kept if i < len(defaults)):
                    cmd.extend(["-disposition:a:0", "default"])
            else:
                # Tracks not probed (ffprobe missing/failed) -- keep them all.
                cmd.extend(["-map", "0:a?"])

            sub_vars = opts.get("_subtitle_track_vars", [])
            if sub_vars:
                kept_subs = [i for i, var in enumerate(sub_vars) if var.get()]
                for i in kept_subs:
                    cmd.extend(["-map", f"0:s:{i}"])
            else:
                # Tracks not probed (or none present) -- keep whatever exists.
                kept_subs = None
                cmd.extend(["-map", "0:s?"])
            if kept_subs is None or kept_subs:
                # Attachments carry the fonts that MKV ASS subtitles rely on.
                cmd.extend(["-map", "0:t?"])

            cmd.extend([
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                out, "-y",
            ])
            return cmd

        def confirm(input_path, opts):
            track_vars = opts.get("_audio_track_vars", [])
            if track_vars and not any(var.get() for var in track_vars):
                return messagebox.askyesno(
                    "No Audio Selected",
                    "No audio tracks are ticked, so the trimmed clip will have no sound.\n\n"
                    "Continue anyway?",
                )
            return True

        def validate(input_path, opts):
            start = opts.get("start_seconds")
            end = opts.get("end_seconds")
            if start is None or end is None:
                return "Select a video and define a trim range."
            if end <= start:
                return "The trim end must be after the trim start."
            duration = self._get_media_duration_seconds(input_path)
            if duration is not None and end > duration + 0.01:
                return "The trim range extends beyond the end of the video."
            return None

        self._build_tool_panel(
            parent,
            help_text="ℹ️  Clip & Track Editor\nCuts a section of video and/or picks the audio and subtitle tracks to keep, without re-encoding.\n"
                "Extremely fast \u2014 it simply copies the frames within your chosen range.\n\n"
                "Optimisations Applied:\n"
                "  - Output Seeking Alignment: Prevents the first few seconds from starting on a black screen or glitching.\n"
                "  - Zeroed Timestamps: Stabilises metadata clocks so the file drops seamlessly into DaVinci Resolve.\n\n"
                "Move the two handles below the preview to set the trim boundaries.\n\n"
                "Use the transport bar under the preview to play the selected range: "
                "\u25b6/\u23f8 toggles play/pause, \u23f9 stops, drag the scrubber to seek, "
                "\U0001f50a toggles mute, and \u2922 pops the preview out into its own window. "
                "Choosing a different clip automatically stops any preview in progress.\n\n"
                "Keep in Output:\n"
                "  - Tick the audio tracks (languages) to keep; untick any you don't need.\n"
                "  - Tick the subtitle tracks to keep; untick any you don't need. "
                "Embedded fonts are carried over whenever at least one subtitle is kept.\n\n"
                "ℹ️  FFmpeg command (example keeping audio tracks 0 and 1 plus subtitle track 0):\n"
                "ffmpeg.exe -hide_banner -i <input> -ss 00:00:30 -t 00:01:00 -map 0:v:0 -map 0:a:0 -map 0:a:1 -map 0:s:0 -map 0:t? -c copy -avoid_negative_ts make_zero <output> -y\n\n"
                "Select a file above and click Trim & SAVE to begin.\n",

            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_trim"),
            options_builder=options_builder,
            validate=validate,
            confirm=confirm,
            button_container=lambda: state["action_frame"],
            vertical_buttons=True,
            run_label="Trim & SAVE",
        )

    def _build_still_frame_tab(self, parent):
        EXT = {"PNG": ".png", "JPEG": ".jpg"}
        state = {
            "current_input": None,
            "duration": None,
            "slider_max": None,
            "step_seconds": 1.0,
            "request_id": 0,
            "debounce_job": None,
            "syncing": False,
            "preview_path": os.path.join(
                tempfile.gettempdir(), f"ffmpeg_toolkit_preview_{os.getpid()}.jpg"
            ),
        }

        def options_builder(frame, opts, on_change):
            row1 = ctk.CTkFrame(frame, fg_color="transparent")
            row1.pack(fill="x")
            ctk.CTkLabel(row1, text="Timecode (HH:MM:SS or seconds):", anchor="w").pack(
                side="left", padx=(0, 5)
            )
            opts["timecode"] = ctk.CTkEntry(row1, width=120)
            opts["timecode"].insert(0, "00:00:01")
            opts["timecode"].pack(side="left", padx=(0, 20))

            ctk.CTkLabel(row1, text="Format:", anchor="w").pack(side="left", padx=(0, 5))
            opts["format"] = ctk.StringVar(value="PNG")
            ctk.CTkOptionMenu(
                row1, variable=opts["format"], values=list(EXT.keys()), width=100,
                command=lambda _v: on_change()
            ).pack(side="left")

            duration_row = ctk.CTkFrame(frame, fg_color="transparent")
            duration_row.pack(fill="x", pady=(10, 2))

            opts["duration_label"] = ctk.CTkLabel(
                duration_row, text="Select a video above to enable the scrubber.",
                anchor="w", text_color=AMBER,
            )
            opts["duration_label"].pack(side="left", fill="x", expand=True)

            state["button_slot"] = ctk.CTkFrame(duration_row, fg_color="transparent")
            state["button_slot"].pack(side="right")

            slider_row = ctk.CTkFrame(frame, fg_color="transparent")
            slider_row.pack(fill="x", pady=(0, 8))
            opts["slider"] = ctk.CTkSlider(
                slider_row, from_=0, to=1, number_of_steps=1000, state="disabled",
            )
            opts["slider"].set(0)
            opts["slider"].pack(fill="x", side="left", expand=True, padx=(0, 10))

            opts["slider_label"] = ctk.CTkLabel(slider_row, text="--:--:--.--", width=90, anchor="e")
            opts["slider_label"].pack(side="left")

            preview_frame = ctk.CTkFrame(frame, fg_color=INSET, border_width=1, border_color=BORDER)
            preview_frame.pack(fill="x", pady=(0, 5))
            opts["preview_image_label"] = ctk.CTkLabel(
                preview_frame,
                text="No preview yet -- select a video, then drag the slider.",
                height=280,
            )
            opts["preview_image_label"].pack(pady=10)

            status_row = ctk.CTkFrame(frame, fg_color="transparent")
            status_row.pack(fill="x")

            opts["preview_status_label"] = ctk.CTkLabel(
                status_row, text="", anchor="w", text_color=MUTED
            )
            opts["preview_status_label"].pack(side="left")

            opts["preview_status_label2"] = ctk.CTkLabel(
                status_row, text="", anchor="w", text_color=MUTED
            )
            opts["preview_status_label2"].pack(side="left")

            def set_time_display(seconds):
                state["syncing"] = True
                try:
                    opts["slider"].set(seconds)
                    opts["slider_label"].configure(text=self._format_seconds_as_timecode(seconds))
                    opts["timecode"].delete(0, "end")
                    opts["timecode"].insert(0, self._format_seconds_as_timecode(seconds))
                finally:
                    state["syncing"] = False

            def entry_to_slider(*_args):
                if state["syncing"] or state["duration"] is None:
                    return
                requested = self._parse_timecode_to_seconds(opts["timecode"].get().strip())
                if requested is None:
                    return
                requested = max(0.0, min(requested, state["duration"]))
                set_time_display(requested)
                schedule_preview(requested, opts, state)

            opts["timecode"].bind("<Return>", entry_to_slider)
            opts["timecode"].bind("<FocusOut>", entry_to_slider)

            def slider_moved(value):
                if state["syncing"] or state["duration"] is None:
                    return
                seconds = float(value)
                state["syncing"] = True
                try:
                    opts["slider_label"].configure(text=self._format_seconds_as_timecode(seconds))
                    opts["timecode"].delete(0, "end")
                    opts["timecode"].insert(0, self._format_seconds_as_timecode(seconds))
                finally:
                    state["syncing"] = False
                schedule_preview(seconds, opts, state)

            opts["slider"].configure(command=slider_moved)

            def nudge_slider(direction):
                if state["duration"] is None or state.get("slider_max") is None:
                    return
                current = float(opts["slider"].get())
                step = state.get("step_seconds", 1.0)
                new_value = max(0.0, min(current + direction * step, state["slider_max"]))
                set_time_display(new_value)
                schedule_preview(new_value, opts, state)

            key_target = getattr(opts["slider"], "_canvas", opts["slider"])
            opts["_slider_key_target"] = key_target
            key_target.bind("<Left>", lambda _e: nudge_slider(-1))
            key_target.bind("<Right>", lambda _e: nudge_slider(1))
            key_target.bind("<Button-1>", lambda _e: key_target.focus_set(), add="+")

        def schedule_preview(seconds, opts, state):
            if state.get("debounce_job"):
                try:
                    self.after_cancel(state["debounce_job"])
                except Exception:
                    pass
            state["debounce_job"] = self.after(
                120, lambda: extract_preview(seconds, opts, state)
            )

        def extract_preview(seconds, opts, state):
            input_path = state.get("current_input")
            if not input_path or not os.path.isfile(input_path):
                return
            if not self._ffmpeg_path or not os.path.isfile(self._ffmpeg_path):
                opts["preview_status_label"].configure(
                    text="ffmpeg not found -- set its location in Settings.",
                    text_color=MUTED,
                )
                opts["preview_status_label2"].configure(text="", text_color=MUTED)
                return

            state["request_id"] += 1
            my_request_id = state["request_id"]
            opts["preview_status_label"].configure(
                text=f"Extracting frame at {self._format_seconds_as_timecode(seconds)} ...",
                text_color=MUTED,
            )
            opts["preview_status_label2"].configure(text="", text_color=MUTED)

            def worker():
                timecode_str = self._format_seconds_as_timecode(seconds)
                preview_path = state["preview_path"]
                cmd = [
                    self._ffmpeg_path, "-hide_banner", "-y",
                    "-ss", timecode_str, "-i", input_path,
                    "-frames:v", "1",
                    "-update", "1",
                    "-sws_flags", "accurate_rnd+spline",
                    preview_path,
                ]
                try:
                    # Windows console suppression applied to eliminate black window popup
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        timeout=20,
                        **SUBPROCESS_WINDOW_KWARGS
                    )
                    ok = result.returncode == 0 and os.path.isfile(preview_path)
                except Exception:
                    ok = False
                self._run_on_main(lambda: apply_preview_result(ok, my_request_id, seconds, opts, state))

            threading.Thread(target=worker, daemon=True).start()

        def apply_preview_result(ok, request_id, seconds, opts, state):
            if request_id != state["request_id"]:
                return
            if not ok:
                opts["preview_status_label"].configure(
                    text=f"Couldn't extract a frame at {self._format_seconds_as_timecode(seconds)}.",
                    text_color=MUTED,
                )
                opts["preview_status_label2"].configure(text="", text_color=MUTED)
                return
            try:
                img = PilImage.open(state["preview_path"])
                img.load()
            except Exception:
                opts["preview_status_label"].configure(text="Preview extracted but couldn't be loaded.", text_color=MUTED)
                opts["preview_status_label2"].configure(text="", text_color=MUTED)
                return

            max_w, max_h = 480, 270
            width, height = img.size
            scale = min(max_w / width, max_h / height, 1.0)
            preview_size = (max(1, round(width * scale)), max(1, round(height * scale)))
            preview_image = ctk.CTkImage(light_image=img, dark_image=img, size=preview_size)
            opts["preview_image_label"].configure(image=preview_image, text="")
            opts["_preview_ctk_image"] = preview_image
            opts["preview_status_label"].configure(
                text=f"Previewing frame at {self._format_seconds_as_timecode(seconds)}.",
                text_color=AMBER,
            )
            opts["preview_status_label2"].configure(
                text=" Adjust slider, then click SAVE.",
                text_color=LINK,
            )

        def refresh_duration(input_path, opts, state):
            if not input_path or not os.path.isfile(input_path):
                return
            if input_path == state.get("current_input"):
                return

            state["current_input"] = input_path
            opts["duration_label"].configure(
                text="Reading video metadata...",
                text_color=AMBER
            )

            # Asynchronous background duration resolution to keep UI completely responsive
            def async_probe():
                duration = self._get_media_duration_seconds(input_path)
                self._run_on_main(lambda: on_duration_ready(duration, input_path, opts, state))

            threading.Thread(target=async_probe, daemon=True).start()

        def on_duration_ready(duration, input_path, opts, state):
            if state.get("current_input") != input_path:
                return
            state["duration"] = duration

            if duration is None:
                opts["duration_label"].configure(
                    text="Could not determine video length -- scrubber disabled, enter timecode manually.",
                    text_color=AMBER,
                )
                opts["slider"].configure(state="disabled")
                opts["preview_image_label"].configure(
                    image=None, text="No preview available -- enter a timecode and click Run."
                )
                opts["preview_status_label"].configure(text="", text_color=MUTED)
                opts["preview_status_label2"].configure(text="", text_color=MUTED)
                return

            opts["duration_label"].configure(
                text=f"Video length: {self._format_seconds_as_timecode(duration)}  -- drag slider to preview.",
                text_color=AMBER,
            )
            steps = max(100, min(2000, int(duration)))
            slider_max = max(duration - 0.05, 0.05)
            state["slider_max"] = slider_max
            state["step_seconds"] = slider_max / steps
            opts["slider"].configure(state="normal", from_=0, to=slider_max, number_of_steps=steps)

            opts["preview_image_label"].configure(image=None, text="Loading first-frame preview...")
            opts["preview_status_label"].configure(text="", text_color=MUTED)
            opts["preview_status_label2"].configure(text="", text_color=MUTED)
            opts["slider"].set(0)
            opts["slider_label"].configure(text="00:00:00.00")
            opts["timecode"].delete(0, "end")
            opts["timecode"].insert(0, "00:00:00")
            schedule_preview(0.0, opts, state)

            key_target = opts.get("_slider_key_target", opts["slider"])
            try:
                key_target.focus_set()
            except Exception:
                pass

        def cmd_builder(ffmpeg, inp, out, opts):
            timecode = opts["timecode"].get().strip()
            requested_seconds = self._parse_timecode_to_seconds(timecode) or 0.0

            FAST_SEEK_BUFFER = 5.0
            if requested_seconds > FAST_SEEK_BUFFER:
                fast_seek = requested_seconds - FAST_SEEK_BUFFER
                precise_seek = FAST_SEEK_BUFFER
            else:
                fast_seek = 0.0
                precise_seek = requested_seconds

            return [
                ffmpeg, "-hide_banner",
                "-ss", self._format_seconds_as_timecode(fast_seek), "-i", inp,
                "-ss", self._format_seconds_as_timecode(precise_seek),
                "-frames:v", "1",
                "-update", "1",
                "-sws_flags", "accurate_rnd+spline",
                out, "-y"
            ]

        def validate(input_path, opts):
            timecode_text = opts["timecode"].get().strip()
            if not timecode_text:
                return "Timecode is required."

            requested_seconds = self._parse_timecode_to_seconds(timecode_text)
            if requested_seconds is None:
                return f"'{timecode_text}' isn't a valid timecode (use HH:MM:SS or seconds)."
            if requested_seconds < 0:
                return "Timecode can't be negative."

            if state.get("current_input") == input_path and state.get("duration") is not None:
                duration_seconds = state["duration"]
            else:
                duration_seconds = self._get_media_duration_seconds(input_path)
            if duration_seconds is not None and requested_seconds >= duration_seconds:
                return (
                    f"NO SUCH TIME\n"
                    f"This video is only "
                    f"{self._format_seconds_as_timecode(duration_seconds)} long.\n"
                    f"You requested {timecode_text}."
                )
            return None

        def output_namer(inp, opts):
            refresh_duration(inp, opts, state)
            return self._suffixed_output(inp, "_frame", ext=EXT[opts["format"].get()])

        self._build_tool_panel(
            parent,
            help_text=(
                "\u2139\ufe0f  Still Frame Export\n"
                "Extracts a single frame from your video and saves it as an image.\n"
                "Useful for thumbnails, reference shots, or grabbing a frame for colour grading.\n\n"
                "Optimisations Applied:\n"
                "  - Frame-Accurate Output Seeking: Bypasses keyframe restrictions to extract the exact frame requested.\n"
                "  - High-Fidelity Color Retention: Disables basic bilinear filtering so reference shots stay color-accurate.\n\n"
                "ℹ️  FFmpeg command:\n"
                "ffmpeg.exe -hide_banner -i <input> -ss 00:01:30 -frames:v 1 -sws_flags accurate_rnd+spline <output>.png -y\n\n"
                "Select a file above and click Run to begin.\n"

            ),
            cmd_builder=cmd_builder,
            output_namer=output_namer,
            options_builder=options_builder,
            validate=validate,
            output_filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
            on_success=lambda inp, out, opts: self._show_image_preview(out, opts.get("_log_box")),
            show_run_abort=False,
            save_label="Save",
            button_container=lambda: state["button_slot"],
        )

    def _build_extract_audio_tab(self, parent):
        FORMATS = {
            "WAV (PCM)": (".wav", ["-c:a", "pcm_s16le"]),
            "AAC (192k)": (".m4a", ["-c:a", "aac", "-b:a", "192k"]),
        }

        ALL_TRACKS_LABEL = "All tracks (one file each)"
        NO_TRACKS_LABEL = "First audio track"
        # Shared by every label in the left column (Input/Output File too),
        # so the boxes and menus all start at the same edge.
        LABEL_WIDTH = 120
        # ffmpeg channel layouts that include a front-centre (FC) channel,
        # where film mixes put most of the dialogue.
        CENTRE_LAYOUTS = {
            "3.0", "3.0(back)", "3.1", "4.0", "4.1", "5.0", "5.0(side)",
            "5.1", "5.1(side)", "6.0", "6.1", "6.1(back)", "7.0", "7.0(front)",
            "7.1", "7.1(wide)", "7.1(wide-side)", "7.1(top)", "hexagonal", "octagonal",
        }

        def has_centre(track):
            layout = track.get("layout") or ""
            if layout:
                return layout in CENTRE_LAYOUTS
            # No layout reported: 6+ channels is almost always 5.1 or wider.
            return isinstance(track.get("channels"), int) and track["channels"] >= 6

        def is_surround(track):
            return isinstance(track.get("channels"), int) and track["channels"] > 2

        ORIGINAL_LABEL = "Original channels"
        # Channels menu label -> (name suffix, ffmpeg args, which tracks it applies to).
        CHANNEL_MODES = {
            ORIGINAL_LABEL: ("", [], lambda t: True),
            # -ac 2 uses ffmpeg's standard downmix: centre and surrounds are
            # folded into left/right at reduced level, so nothing clips.
            "Stereo downmix": ("_stereo", ["-ac", "2"], is_surround),
            "Dialogue only (centre channel)": ("_dialogue", ["-af", "pan=mono|c0=FC"], has_centre),
        }

        def options_builder(frame, opts, on_change):
            top_row = ctk.CTkFrame(frame, fg_color="transparent")
            top_row.pack(fill="x")
            ctk.CTkLabel(top_row, text="Format:", width=LABEL_WIDTH, anchor="w").pack(
                side="left", padx=(0, 5)
            )
            opts["format"] = ctk.StringVar(value="WAV (PCM)")
            ctk.CTkOptionMenu(
                top_row, variable=opts["format"], values=list(FORMATS.keys()), width=140,
                command=lambda _v: on_change()
            ).pack(side="left")

            ctk.CTkLabel(top_row, text="Audio Track:", anchor="w").pack(side="left", padx=(20, 5))
            opts["track"] = ctk.StringVar(value=NO_TRACKS_LABEL)
            opts["_audio_tracks"] = []
            # Menu label -> track index, or "all".
            opts["_track_choices"] = {}
            track_menu = ctk.CTkOptionMenu(
                top_row, variable=opts["track"], values=[NO_TRACKS_LABEL], width=320,
                command=lambda _v: track_changed(),
            )
            track_menu.pack(side="left")

            channels_row = ctk.CTkFrame(frame, fg_color="transparent")
            channels_row.pack(fill="x", pady=(8, 0))
            ctk.CTkLabel(channels_row, text="Surround Options:", width=LABEL_WIDTH, anchor="w").pack(
                side="left", padx=(0, 5)
            )
            opts["channels"] = ctk.StringVar(value=ORIGINAL_LABEL)
            channels_menu = ctk.CTkOptionMenu(
                channels_row, variable=opts["channels"], values=[ORIGINAL_LABEL],
                width=260, command=lambda _v: on_change(), state="disabled",
            )
            channels_menu.pack(side="left")
            CTkToolTip(
                channels_menu,
                "Offered for surround (5.1 / 7.1) tracks:\n"
                "  Stereo downmix - folds all channels into ordinary left/right stereo.\n"
                "  Dialogue only - saves just the centre channel as mono,\n"
                "  which in most films is mainly the dialogue.",
            )

            def track_changed():
                # Only offer the channel modes the chosen track(s) can use.
                choice = selected_track(opts)
                tracks = opts["_audio_tracks"]
                if choice == "all":
                    chosen = tracks
                elif isinstance(choice, int):
                    chosen = [tracks[choice]]
                else:
                    chosen = []
                values = [
                    label for label, (_s, _a, applies) in CHANNEL_MODES.items()
                    if label == ORIGINAL_LABEL or any(applies(t) for t in chosen)
                ]
                channels_menu.configure(
                    values=values, state="normal" if len(values) > 1 else "disabled"
                )
                if opts["channels"].get() not in values:
                    opts["channels"].set(ORIGINAL_LABEL)
                on_change()

            probed = {"path": None}

            def refresh_tracks(input_path):
                # on_change (Format/Track) also fires this callback; only
                # re-probe and reset the track selection when the input changes.
                if input_path == probed["path"]:
                    return
                probed["path"] = input_path
                tracks = self._probe_audio_tracks(input_path)
                opts["_audio_tracks"] = tracks
                choices = {}
                for i, track in enumerate(tracks):
                    language = track["language"]
                    name = LANGUAGE_NAMES.get(language.lower())
                    label_bits = [f"Track {i}: {name} ({language})" if name else f"Track {i}: {language}"]
                    if track.get("title"):
                        label_bits.append(f"\"{track['title']}\"")
                    label_bits.append(f"({track['codec']}, {track['channels']}ch)")
                    choices[" ".join(label_bits)] = i
                if len(tracks) > 1:
                    choices[ALL_TRACKS_LABEL] = "all"
                if not choices:
                    choices[NO_TRACKS_LABEL] = None
                opts["_track_choices"] = choices
                values = list(choices)
                track_menu.configure(values=values)
                opts["track"].set(values[0])
                # Also regenerates the output name, which was generated
                # before the tracks were known.
                track_changed()

            opts["_input_change_callbacks"].append(refresh_tracks)

        def selected_track(opts):
            return opts["_track_choices"].get(opts["track"].get())

        def per_track_path(out, index, track):
            stem, ext = os.path.splitext(out)
            return f"{stem}_{index}_{track['language']}{ext}"

        def output_namer(inp, opts):
            ext = FORMATS[opts["format"].get()][0]
            tracks = opts["_audio_tracks"]
            choice = selected_track(opts)
            suffix = "_extracted"
            # Tag single-track picks with the language when there's a choice of several.
            if isinstance(choice, int) and len(tracks) > 1:
                suffix += f"_{tracks[choice]['language']}"
            suffix += CHANNEL_MODES[opts["channels"].get()][0]
            return self._suffixed_output(inp, suffix, ext=ext)

        def cmd_builder(ffmpeg, inp, out, opts):
            _ext, codec_args = FORMATS[opts["format"].get()]
            cmd = [ffmpeg, "-hide_banner", "-i", inp]
            choice = selected_track(opts)
            _suffix, mode_args, applies = CHANNEL_MODES[opts["channels"].get()]

            def filter_for(track):
                # With "All tracks", tracks the mode can't apply to are saved as-is.
                return mode_args if applies(track) else []

            if choice == "all":
                # One ffmpeg run, one output file per track.
                for i, track in enumerate(opts["_audio_tracks"]):
                    cmd.extend([
                        "-map", f"0:a:{i}", *filter_for(track), *codec_args,
                        per_track_path(out, i, track),
                    ])
            elif isinstance(choice, int):
                track = opts["_audio_tracks"][choice]
                cmd.extend(["-map", f"0:a:{choice}", *filter_for(track), *codec_args, out])
            else:
                # Tracks not probed -- WAV holds only one stream, so take the first.
                cmd.extend(["-map", "0:a:0?", *codec_args, out])
            cmd.append("-y")
            return cmd

        self._build_tool_panel(
            parent,
            help_text="ℹ️  Extract Audio\nPulls the audio track out of your video file.\n"
                "Pulls the audio track out of your video file as a standalone audio file.\n"
                "WAV gives you uncompressed audio; AAC gives you a smaller compressed file.\n\n"
                "Optimisations Applied:\n"
                "  - Safe Stream Mapping: Changed from a forced layout to a flexible tracking layout. This prevents extracting a director's commentary track by accident.\n"
                "  - True Container Packaging: AAC streams are now safely packaged into standard .m4a wrappers for wide compatibility.\n\n"
                "Audio Track:\n"
                "  - Lists every audio track (language) in the file. Pick one to save just that track; "
                "its language code is added to the output name (e.g. _extracted_eng.wav).\n"
                "  - \"All tracks (one file each)\" saves every track as its own file, named after the Output File "
                "with the track number and language added (e.g. _extracted_0_tur.wav, _extracted_1_eng.wav).\n\n"
                "Surround Options (offered when the chosen track is surround, e.g. 5.1 / 7.1):\n"
                "  - Original channels: saves the track exactly as it is.\n"
                "  - Stereo downmix: folds all the channels into ordinary left/right stereo, for playback "
                "on TVs, headphones or editing timelines that expect stereo (_stereo is added to the name). "
                "FFmpeg adds: -ac 2\n"
                "  - Dialogue only (centre channel): in surround film mixes, dialogue sits mostly in the centre channel, "
                "so this saves just that channel as mono (_dialogue is added to the name). Expect some music and "
                "effects to remain, as mixers often put a little of both in the centre. "
                "FFmpeg adds: -af \"pan=mono|c0=FC\"\n"
                "  - With \"All tracks\", tracks a mode can't apply to (e.g. stereo tracks) are saved as they are.\n\n"
                "ℹ️  FFmpeg commands (example extracting audio track 1):\n"
                "WAV: ffmpeg.exe -hide_banner -i <input> -map 0:a:1 -c:a pcm_s16le <output>.wav -y\n"
                "AAC: ffmpeg.exe -hide_banner -i <input> -map 0:a:1 -c:a aac -b:a 192k <output>.m4a -y\n\n"
                "Select a file above and click Run to begin.\n",

            cmd_builder=cmd_builder,
            output_namer=output_namer,
            options_builder=options_builder,
            output_filetypes=[("Audio files", "*.wav *.m4a"), ("All files", "*.*")],
            label_width=LABEL_WIDTH,
        )

    def _build_strip_audio_tab(self, parent):
        def cmd_builder(ffmpeg, inp, out, opts):
            return [
                ffmpeg, "-hide_banner", "-i", inp, 
                "-map", "0:v", 
                "-map", "0:s?", 
                "-c:v", "copy", 
                "-c:s", "copy", 
                "-an", 
                out, "-y"
            ]

        self._build_tool_panel(
            parent,
            help_text="ℹ️  Strip Audio\nRemoves audio tracks while keeping video and subtitles intact.\n"
                "Removes all audio tracks from the file, keeping the video and subtitles perfectly intact.\n"
                "Useful for preparing files when you plan to completely replace the audio timeline in DaVinci Resolve.\n\n"
                "Optimisations Applied:\n"
                "  - Complete Video Mapping: Preserves embedded cover art, posters, and alternate video thumbnails instead of dropping them.\n"
                "  - Subtitle Preservation: Automatically keeps embedded subtitle streams (-map 0:s?) untouched while isolating the video.\n\n"
                "ℹ️  FFmpeg command:\n"
                "ffmpeg.exe -hide_banner -i <input> -map 0:v -map 0:s? -c:v copy -c:s copy -an <output> -y\n\n"
                "Select a file above and click Run to begin.\n",


            cmd_builder=cmd_builder,
            output_namer=lambda inp, opts: self._suffixed_output(inp, "_noaudio"),
        )

    def _build_audio_accessibility_tab(self, parent):
        LOUDNESS_OPTIONS = [
            "-14 LUFS  (YouTube / Spotify)",
            "-16 LUFS  (Apple Music)",
            "-20 LUFS  (Custom Accentuation)",
            "-23 LUFS  (Broadcast / EBU R128)",
            "-27 LUFS  (Netflix / Amazon)",
        ]

        ALL_TRACKS_LABEL = "All Tracks (keep every audio track)"

        IMAGE_SUBTITLE_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}

        CONTAINER_FORMATS = {
            "MKV (Matroska)": ".mkv",
            "MOV (QuickTime)": ".mov",
            "MP4 (Compatibility)": ".mp4",
        }

        button_holder = {}
        # Option labels share this width, and the Input/Output File labels
        # (plus their 5px gap) match it, so every box and menu lines up.
        LABEL_WIDTH = 105

        def options_builder(frame, opts, on_change):
            track_frame = ctk.CTkFrame(frame, fg_color="transparent")
            track_frame.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(track_frame, text="Audio Track:", width=LABEL_WIDTH, anchor="w").pack(side="left")
            opts["track"] = ctk.StringVar(value=ALL_TRACKS_LABEL)
            opts["_audio_tracks"] = []
            track_menu = ctk.CTkOptionMenu(
                track_frame, values=[ALL_TRACKS_LABEL], variable=opts["track"], width=320
            )
            track_menu.pack(side="left")

            multi_lang_icon = ctk.CTkLabel(
                track_frame, text="", image=self._multi_lang_icon_image
            )
            if self._multi_lang_icon_image is not None:
                CTkToolTip(multi_lang_icon, "Multiple languages detected in this file")

            probed = {"path": None}

            def refresh_tracks(input_path):
                # on_change (Mode/Codec/Format etc.) also fires this callback; only
                # re-probe and reset the track selection when the input file changes.
                if input_path == probed["path"]:
                    return
                probed["path"] = input_path
                tracks = self._probe_audio_tracks(input_path)
                opts["_audio_tracks"] = tracks
                values = [ALL_TRACKS_LABEL]
                for i, track in enumerate(tracks):
                    label_bits = [f"Track {i}: {track['language']}"]
                    if track.get("title"):
                        label_bits.append(f"\"{track['title']}\"")
                    label_bits.append(f"({track['codec']}, {track['channels']}ch)")
                    values.append(" ".join(label_bits))
                track_menu.configure(values=values)
                opts["track"].set(values[0])

                distinct_langs = {
                    t.get("language") for t in tracks
                    if t.get("language") and t.get("language") != "und"
                }
                if self._multi_lang_icon_image is not None and len(distinct_langs) > 1:
                    multi_lang_icon.pack(side="left", padx=(8, 0))
                else:
                    multi_lang_icon.pack_forget()

                data = self._probe_full(input_path) or {}
                opts["_subtitle_streams"] = [
                    s for s in data.get("streams", []) if s.get("codec_type") == "subtitle"
                ]
                if opts["_subtitle_streams"]:
                    subs_frame.pack(fill="x", pady=(0, 4), after=mix_frame)
                else:
                    subs_frame.pack_forget()

            opts["_input_change_callbacks"].append(refresh_tracks)

            mode_frame = ctk.CTkFrame(frame, fg_color="transparent")
            mode_frame.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(mode_frame, text="Mode:", width=LABEL_WIDTH, anchor="w").pack(side="left")
            opts["mode"] = ctk.StringVar(value="Dynamic Normaliser")

            loudness_frame = ctk.CTkFrame(frame, fg_color="transparent")
            ctk.CTkLabel(loudness_frame, text="Target Loudness:", width=LABEL_WIDTH, anchor="w").pack(side="left")
            opts["loudness"] = ctk.StringVar(value="-16 LUFS  (Apple Music)")
            ctk.CTkOptionMenu(
                loudness_frame, values=LOUDNESS_OPTIONS, variable=opts["loudness"], width=260,
                command=lambda _v: on_change(),
            ).pack(side="left")

            def toggle_loudness(mode):
                if mode == "Loudness Compression":
                    loudness_frame.pack(fill="x", pady=(0, 4), before=codec_frame)
                else:
                    loudness_frame.pack_forget()
                on_change()

            ctk.CTkSegmentedButton(
                mode_frame,
                values=["Dynamic Normaliser", "Loudness Compression"],
                variable=opts["mode"],
                command=toggle_loudness,
            ).pack(side="left")

            codec_frame = ctk.CTkFrame(frame, fg_color="transparent")
            codec_frame.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(codec_frame, text="Output Codec:", width=LABEL_WIDTH, anchor="w").pack(side="left")
            opts["codec"] = ctk.StringVar(value="PCM (Resolve/Editing)")
            ctk.CTkSegmentedButton(
                codec_frame,
                values=["PCM (Resolve/Editing)", "AAC (Server Storage)"],
                variable=opts["codec"],
                command=lambda _v: on_change(),
            ).pack(side="left")

            format_frame = ctk.CTkFrame(frame, fg_color="transparent")
            format_frame.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(format_frame, text="Output Format:", width=LABEL_WIDTH, anchor="w").pack(side="left")
            opts["format"] = ctk.StringVar(value="MKV (Matroska)")
            ctk.CTkSegmentedButton(
                format_frame,
                values=list(CONTAINER_FORMATS.keys()),
                variable=opts["format"],
                command=lambda _v: on_change(),
            ).pack(side="left")

            mix_frame = ctk.CTkFrame(frame, fg_color="transparent")
            mix_frame.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(mix_frame, text="Channels:", width=LABEL_WIDTH, anchor="w").pack(side="left")
            opts["channels"] = ctk.StringVar(value="Original Layout")
            ctk.CTkSegmentedButton(
                mix_frame,
                values=["Original Layout", "Stereo Downmix (Clear Dialogue)"],
                variable=opts["channels"]
            ).pack(side="left")

            button_holder["frame"] = ctk.CTkFrame(mix_frame, fg_color="transparent")
            button_holder["frame"].pack(side="right")

            # Only shown (by refresh_tracks) when the input has subtitle tracks.
            opts["_subtitle_streams"] = []
            subs_frame = ctk.CTkFrame(frame, fg_color="transparent")
            ctk.CTkLabel(subs_frame, text="Subtitles:", width=LABEL_WIDTH, anchor="w").pack(side="left")
            ctk.CTkButton(
                subs_frame, text="\u26A0  Important Subtitle Info", width=210,
                fg_color=WARN_FILL, hover_color=WARN_HOVER, border_color="#6b5a2e",
                text_color=AMBER, font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda: show_subtitle_info(),
            ).pack(side="left")

            def show_subtitle_info():
                streams = opts.get("_subtitle_streams", [])
                track_lines = []
                has_image = has_non_mov_text = False
                for i, s in enumerate(streams):
                    codec = s.get("codec_name", "?")
                    language = (s.get("tags", {}) or {}).get("language", "und")
                    is_image = codec in IMAGE_SUBTITLE_CODECS
                    has_image = has_image or is_image
                    has_non_mov_text = has_non_mov_text or codec != "mov_text"
                    kind = "image" if is_image else "text"
                    track_lines.append(f"  • Subtitle {i}: {language} — {codec} ({kind})")

                safe = ["MKV"]
                if not has_non_mov_text:
                    safe.append("MOV")
                if not has_image:
                    safe.append("MP4")

                self._center_next_messagebox("Important Subtitle Info")
                messagebox.showinfo(
                    "Important Subtitle Info",
                    f"This file contains {len(streams)} subtitle track"
                    f"{'s' if len(streams) != 1 else ''}:\n"
                    + "\n".join(track_lines) + "\n\n"
                    f"Output formats that will succeed for this file: {', '.join(safe)}\n\n"
                    "All subtitle tracks are carried into the converted file, whichever "
                    "Audio Track is selected. What happens to them depends on the Output Format:\n\n"
                    "MKV (Matroska)\n"
                    "  • Text subtitles (SRT, ASS): copied unchanged.\n"
                    "  • Image subtitles (PGS from Blu-ray, VobSub from DVD): copied unchanged.\n"
                    "  • Embedded fonts are not kept, so styled (ASS) subtitles fall back "
                    "to a plain font.\n\n"
                    "MOV (QuickTime)\n"
                    "  • Text subtitles: CONVERSION FAILS. Subtitles are copied as-is, but MOV "
                    "only accepts its own text subtitle format (mov_text), so SRT/ASS are rejected "
                    "with a \"codec not supported in container\" error.\n"
                    "  • Image subtitles: CONVERSION FAILS for the same reason.\n\n"
                    "MP4 (Compatibility)\n"
                    "  • Text subtitles: converted to MP4's own subtitle format (mov_text). "
                    "ASS styling (fonts, colours, positioning) is lost.\n"
                    "  • Image subtitles: CONVERSION FAILS. FFmpeg can't turn a picture "
                    "into text.\n\n"
                    "In all formats, subtitle language tags are preserved.\n\n"
                    "A failed conversion stops with an error, which can happen after a long PCM "
                    "encode. If in doubt, choose MKV.",
                    parent=self,
                )

        def cmd_builder(ffmpeg, inp, out, opts):
            if opts["mode"].get() == "Dynamic Normaliser":
                af = "dynaudnorm"
            else:
                lufs = opts["loudness"].get().split()[0]
                af = f"loudnorm=I={lufs}:LRA=7:TP=-2"

            cmd = [ffmpeg, "-i", inp, "-map", "0:v", "-c:v", "copy"]

            selection = opts.get("track", ALL_TRACKS_LABEL)
            selection = selection.get() if hasattr(selection, "get") else selection
            tracks = opts.get("_audio_tracks", [])

            if selection == ALL_TRACKS_LABEL or not tracks:
                cmd.extend(["-map", "0:a"])
                for i in range(max(len(tracks), 1)):
                    cmd.extend([f"-filter:a:{i}", af])
            else:
                track_index = int(selection.split(":")[0].replace("Track", "").strip())
                cmd.extend(["-map", f"0:a:{track_index}"])
                cmd.extend(["-af", af])

            if opts["channels"].get() == "Stereo Downmix (Clear Dialogue)":
                cmd.extend(["-ac", "2"])

            if opts["codec"].get() == "PCM (Resolve/Editing)":
                cmd.extend(["-c:a", "pcm_s16le"])
            else:
                cmd.extend(["-c:a", "aac", "-b:a", "256k"])

            if not opts.get("_drop_subtitles"):
                subtitle_codec = "mov_text" if opts["format"].get() == "MP4 (Compatibility)" else "copy"
                cmd.extend(["-map", "0:s?", "-c:s", subtitle_codec])
            cmd.extend([out, "-y"])
            return cmd

        def output_namer(inp, opts):
            if opts["mode"].get() == "Loudness Compression":
                label = opts["loudness"].get().split()[0] + " LUFS"
            else:
                label = "Dynamic Normalised"
            ext = CONTAINER_FORMATS[opts["format"].get()]
            return self._suffixed_output(inp, f" ({label})", ext=ext)

        def unsupported_subtitles(opts):
            """Subtitle tracks the chosen Output Format can't take (see the
            Important Subtitle Info popup): MOV only copies mov_text, MP4
            can't convert image subtitles to text. MKV accepts everything."""
            fmt = opts["format"].get()
            streams = opts.get("_subtitle_streams", [])
            if fmt == "MOV (QuickTime)":
                return [s for s in streams if s.get("codec_name") != "mov_text"]
            if fmt == "MP4 (Compatibility)":
                return [s for s in streams if s.get("codec_name") in IMAGE_SUBTITLE_CODECS]
            return []

        def confirm(input_path, opts):
            opts["_drop_subtitles"] = False
            bad_subs = unsupported_subtitles(opts)
            if bad_subs:
                fmt_short = opts["format"].get().split()[0]
                codecs = ", ".join(sorted({s.get("codec_name", "?") for s in bad_subs}))
                title = "Subtitles Not Supported"
                self._center_next_messagebox(title)
                answer = messagebox.askyesnocancel(
                    title,
                    f"{len(bad_subs)} subtitle track{'s' if len(bad_subs) != 1 else ''} "
                    f"in this file ({codecs}) can't be carried into {fmt_short}, "
                    "so FFmpeg would stop with an error.\n\n"
                    "Yes  -  switch Output Format to MKV and keep all subtitles\n"
                    f"No  -  stay with {fmt_short} and leave the subtitles out\n"
                    "Cancel  -  don't run",
                    parent=self,
                )
                if answer is None:
                    return False
                if answer:
                    opts["format"].set("MKV (Matroska)")
                    # Keeps a typed name (just changing its extension to .mkv).
                    opts["_update_output"]()
                else:
                    opts["_drop_subtitles"] = True

            if opts["format"].get() == "MP4 (Compatibility)" and opts["codec"].get() == "PCM (Resolve/Editing)":
                return messagebox.askyesno(
                    "PCM in MP4",
                    "MP4 does not reliably support PCM audio - most players won't recognise it.\n\n"
                    "Use MKV or MOV for PCM output, or switch the codec to AAC.\n\n"
                    "Continue anyway?",
                )
            return True

        def on_success(input_path, output_path, opts):
            log_box = opts.get("_log_box")
            try:
                selection = opts.get("track", ALL_TRACKS_LABEL)
                selection = selection.get() if hasattr(selection, "get") else selection

                if opts["mode"].get() == "Loudness Compression":
                    mode_desc = f"Loudness Compression, target {opts['loudness'].get()}"
                else:
                    mode_desc = "Dynamic Normaliser"

                report_lines = [
                    "FF-Toolkit Conversion Report",
                    f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    "Tool: Audio Accessibility",
                    "",
                    "=== Input File ===",
                    self._describe_media(input_path),
                    "",
                    "=== Changes Applied ===",
                    f"  Audio Track Processed: {selection}",
                    f"  Loudness Mode: {mode_desc}",
                    f"  Channels: {opts['channels'].get()}",
                    f"  Output Codec: {opts['codec'].get()}",
                    f"  Output Format: {opts['format'].get()}",
                    "  Subtitles: "
                    + ("left out (not supported by this format)"
                       if opts.get("_drop_subtitles") else "carried over"),
                    "",
                    "=== Output File ===",
                    self._describe_media(output_path),
                    "",
                ]

                report_dir = os.path.dirname(output_path) or "."
                report_path = os.path.join(report_dir, "FF-Toolkit Conversion Report.txt")
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(report_lines))

                if log_box is not None:
                    self._log(log_box, f"Report saved: {report_path}\n")
            except Exception as exc:
                if log_box is not None:
                    self._log(log_box, f"Warning: could not write conversion report ({exc}).\n")

        self._build_tool_panel(
            parent,
            help_text="ℹ️  Audio Accessibility Tool\nNormalise loudness ranges safely before editing.\n"
                "Normalise loudness ranges safely before importing your MKV assets into DaVinci Resolve.\n"
                "Optimised explicitly for users who are hard of hearing.\n\n"
                "Profiles:\n"
                "  - A range of LUF settings to suit different listening environments including...\n"
                "    -20 LUFS: Custom mid-ground balance. Excellent for older film dialogue preservation.\n"
                "  - PCM Codec: Massive uncompressed files. Fixes missing audio timelines in Resolve instantly.\n"
                "  - AAC Codec: Compact compressed streams. Highly recommended for Plex / Jellyfin servers.\n\n"
                "Channels:\n"
                "  - Stereo Downmix: Flattens multi-channel sound to a clean 2.0 space, pinning dialogue heavily to the front speakers.\n\n"
                "Audio Track:\n"
                "  - For multi-language files (e.g. dual Turkish/English), pick the exact track to process, "
                "or leave on \"All Tracks\" to keep and process every language track instead of losing the others.\n\n"
                "Output Format:\n"
                "  - MKV: recommended default. Accepts any video/subtitle codec plus PCM or AAC audio.\n"
                "  - MOV: pairs well with PCM audio for editing/delivery workflows.\n"
                "  - MP4: widest player compatibility, best paired with AAC. PCM audio isn't reliably "
                "supported in MP4, and non-text subtitles (e.g. PGS/VobSub) can't be carried over.\n",


            cmd_builder=cmd_builder,
            output_namer=output_namer,
            options_builder=options_builder,
            button_container=lambda: button_holder["frame"],
            confirm=confirm,
            on_success=on_success,
            output_filetypes=[
                ("MKV files", "*.mkv"), ("MOV files", "*.mov"), ("MP4 files", "*.mp4"),
                ("All files", "*.*"),
            ],
            label_width=LABEL_WIDTH - 5,
        )

    def _build_subtitles_extractor_tab(self, parent):
        ORIGINAL_LABEL = "Keep original format"
        # Format menu label -> (extension, ffmpeg args); None = each track's own format.
        FORMATS = {
            ORIGINAL_LABEL: None,
            "SRT (SubRip)": (".srt", ["-c:s", "srt"]),
            "WebVTT": (".vtt", ["-c:s", "webvtt"]),
            "ASS (Advanced SubStation)": (".ass", ["-c:s", "ass"]),
        }
        # Subtitle codec -> (extension, ffmpeg args) for "Keep original format".
        # Picture subtitles can't be turned into text (that needs OCR), so PGS
        # is copied to a .sup file and any other format into a subtitle-only
        # Matroska file (.mks), which can hold every subtitle type.
        MKS = (".mks", ["-c:s", "copy", "-f", "matroska"])
        ORIGINAL_FORMATS = {
            "subrip": (".srt", ["-c:s", "copy"]),
            "ass": (".ass", ["-c:s", "copy"]),
            "ssa": (".ass", ["-c:s", "ass"]),
            "webvtt": (".vtt", ["-c:s", "copy"]),
            # MP4's mov_text has no file of its own; SRT is its plain-text twin.
            "mov_text": (".srt", ["-c:s", "srt"]),
            "hdmv_pgs_subtitle": (".sup", ["-c:s", "copy"]),
        }

        ALL_TRACKS_LABEL = "All tracks (one file each)"
        NO_TRACKS_LABEL = "No subtitle tracks found"
        # Shared by every label in the left column (Input/Output File too).
        LABEL_WIDTH = 120

        def is_picture(track):
            return track["codec"] in PICTURE_SUBTITLE_CODECS

        def format_for(track, opts):
            """(extension, ffmpeg args) for one track under the chosen Format.
            Picture tracks always keep their own format."""
            chosen = FORMATS[opts["format"].get()]
            if chosen is None or is_picture(track):
                return ORIGINAL_FORMATS.get(track["codec"], MKS)
            return chosen

        def track_tag(track):
            # Language plus forced / SDH flags, so e.g. a full English track and
            # its forced-only twin don't overwrite each other.
            tag = track["language"]
            if track["forced"]:
                tag += "_forced"
            if track["hearing_impaired"]:
                tag += "_sdh"
            return tag

        def probe_tracks(input_path):
            """Subtitle streams in `0:s:N` order."""
            data = self._probe_full(input_path) or {}
            tracks = []
            for stream in data.get("streams", []):
                if stream.get("codec_type") != "subtitle":
                    continue
                tags = stream.get("tags", {}) or {}
                disposition = stream.get("disposition") or {}
                tracks.append({
                    "language": tags.get("language", "und"),
                    "title": tags.get("title", ""),
                    "codec": stream.get("codec_name", "?"),
                    "forced": bool(disposition.get("forced")),
                    "hearing_impaired": bool(disposition.get("hearing_impaired")),
                })
            return tracks

        def track_label(i, track):
            language = track["language"]
            name = LANGUAGE_NAMES.get(language.lower())
            label_bits = [f"Track {i}: {name} ({language})" if name else f"Track {i}: {language}"]
            if track["title"]:
                label_bits.append(f"\"{track['title']}\"")
            details = [SUBTITLE_CODEC_NAMES.get(track["codec"], track["codec"])]
            if is_picture(track):
                details.append("picture")
            if track["forced"]:
                details.append("forced")
            if track["hearing_impaired"]:
                details.append("SDH")
            label_bits.append(f"({', '.join(details)})")
            return " ".join(label_bits)

        def options_builder(frame, opts, on_change):
            track_row = ctk.CTkFrame(frame, fg_color="transparent")
            track_row.pack(fill="x")
            ctk.CTkLabel(track_row, text="Subtitle Track:", width=LABEL_WIDTH, anchor="w").pack(
                side="left", padx=(0, 5)
            )
            opts["track"] = ctk.StringVar(value=NO_TRACKS_LABEL)
            opts["_sub_tracks"] = []
            # Menu label -> track index, or "all".
            opts["_track_choices"] = {}
            track_menu = ctk.CTkOptionMenu(
                track_row, variable=opts["track"], values=[NO_TRACKS_LABEL], width=420,
                command=lambda _v: track_changed(),
            )
            track_menu.pack(side="left")

            format_row = ctk.CTkFrame(frame, fg_color="transparent")
            format_row.pack(fill="x", pady=(8, 0))
            ctk.CTkLabel(format_row, text="Format:", width=LABEL_WIDTH, anchor="w").pack(
                side="left", padx=(0, 5)
            )
            opts["format"] = ctk.StringVar(value=ORIGINAL_LABEL)
            format_menu = ctk.CTkOptionMenu(
                format_row, variable=opts["format"], values=list(FORMATS), width=240,
                command=lambda _v: on_change(), state="disabled",
            )
            format_menu.pack(side="left")
            CTkToolTip(
                format_menu,
                "Keep original format - saves each track as it is (SRT stays .srt,\n"
                "ASS stays .ass, PGS becomes .sup, other picture subtitles .mks).\n"
                "SRT / WebVTT / ASS - converts text subtitles to that format.\n"
                "Picture subtitles (PGS, VobSub, DVB) can't be converted to text,\n"
                "so they are always saved in their original format.",
            )

            def track_changed():
                # Converting is only offered when the chosen track(s) include text subtitles.
                choice = selected_track(opts)
                tracks = opts["_sub_tracks"]
                if choice == "all":
                    chosen = tracks
                elif isinstance(choice, int):
                    chosen = [tracks[choice]]
                else:
                    chosen = []
                can_convert = any(not is_picture(t) for t in chosen)
                values = list(FORMATS) if can_convert else [ORIGINAL_LABEL]
                format_menu.configure(values=values, state="normal" if can_convert else "disabled")
                if opts["format"].get() not in values:
                    opts["format"].set(ORIGINAL_LABEL)
                on_change()

            probed = {"path": None}

            def refresh_tracks(input_path):
                # on_change (Format/Track) also fires this callback; only
                # re-probe and reset the track selection when the input changes.
                if input_path == probed["path"]:
                    return
                probed["path"] = input_path
                tracks = probe_tracks(input_path)
                opts["_sub_tracks"] = tracks
                choices = {track_label(i, track): i for i, track in enumerate(tracks)}
                if len(tracks) > 1:
                    choices[ALL_TRACKS_LABEL] = "all"
                if not choices:
                    choices[NO_TRACKS_LABEL] = None
                opts["_track_choices"] = choices
                values = list(choices)
                track_menu.configure(values=values)
                opts["track"].set(values[0])
                # Also regenerates the output name, which was generated
                # before the tracks were known.
                track_changed()

            opts["_input_change_callbacks"].append(refresh_tracks)

        def selected_track(opts):
            return opts["_track_choices"].get(opts["track"].get())

        def per_track_path(out, index, track, opts):
            stem, _ext = os.path.splitext(out)
            return f"{stem}_{index}_{track_tag(track)}{format_for(track, opts)[0]}"

        def output_namer(inp, opts):
            tracks = opts["_sub_tracks"]
            choice = selected_track(opts)
            if isinstance(choice, int):
                track = tracks[choice]
                return self._suffixed_output(
                    inp, f"_subs_{track_tag(track)}", ext=format_for(track, opts)[0]
                )
            # "All tracks" (each file gets its own number, language and
            # extension added) or nothing probed yet.
            chosen = FORMATS[opts["format"].get()]
            if chosen is not None:
                ext = chosen[0]
            elif tracks:
                ext = format_for(tracks[0], opts)[0]
            else:
                ext = ".srt"
            return self._suffixed_output(inp, "_subs", ext=ext)

        def validate(input_path, opts):
            if opts["_sub_tracks"]:
                return None
            if not self._ffprobe_path or not os.path.isfile(self._ffprobe_path):
                return "ffprobe is needed to list the subtitle tracks. Set its location in Settings."
            return "This file has no subtitle tracks to extract."

        def cmd_builder(ffmpeg, inp, out, opts):
            cmd = [ffmpeg, "-hide_banner", "-i", inp]
            tracks = opts["_sub_tracks"]
            choice = selected_track(opts)
            if choice == "all":
                # One ffmpeg run, one output file per track.
                for i, track in enumerate(tracks):
                    cmd.extend([
                        "-map", f"0:s:{i}", *format_for(track, opts)[1],
                        per_track_path(out, i, track, opts),
                    ])
            else:
                cmd.extend(["-map", f"0:s:{choice}", *format_for(tracks[choice], opts)[1], out])
            cmd.append("-y")
            return cmd

        self._build_tool_panel(
            parent,
            help_text="ℹ️  Subtitles Extractor\nSaves the subtitle tracks inside a video file as standalone subtitle files.\n"
                "Handy for editing or correcting subtitles, loading them into DaVinci Resolve, "
                "or keeping a separate .srt next to the video for your media player or Plex/Jellyfin server.\n\n"
                "Subtitle Track:\n"
                "  - Lists every subtitle track in the file with its language, format and flags "
                "(\"forced\" = only translates foreign dialogue or signs; \"SDH\" = for the deaf and hard of hearing). "
                "Pick one to save just that track; its language is added to the output name (e.g. _subs_eng.srt).\n"
                "  - \"All tracks (one file each)\" saves every track as its own file, named after the Output File "
                "with the track number and language added (e.g. _subs_0_eng.srt, _subs_1_fre_forced.srt).\n\n"
                "Format:\n"
                "  - Keep original format: saves each track exactly as it is stored - SRT stays .srt, ASS stays .ass "
                "(keeping its fonts, colours and positioning), WebVTT stays .vtt. MP4 (mov_text) subtitles are saved as .srt.\n"
                "  - SRT (SubRip): the most widely supported format - works in almost every player, TV and editor. "
                "Converting from ASS drops the styling and keeps just the text and timing.\n"
                "  - WebVTT: for web / HTML5 video players.\n"
                "  - ASS (Advanced SubStation): for styled subtitles, e.g. to restyle them in Aegisub.\n\n"
                "Picture subtitles (PGS from Blu-ray, VobSub from DVD, DVB from TV):\n"
                "  - These are stored as images, not text, so they can't be converted to SRT / WebVTT / ASS "
                "(that needs OCR software such as Subtitle Edit). They are always saved in their original form: "
                "PGS as a .sup file, VobSub and DVB as a subtitle-only Matroska file (.mks).\n"
                "  - With \"All tracks\", text tracks are converted to the chosen Format and picture tracks are kept as they are.\n\n"
                "ℹ️  FFmpeg commands (example extracting subtitle track 1):\n"
                "Original: ffmpeg.exe -hide_banner -i <input> -map 0:s:1 -c:s copy <output>.srt -y\n"
                "SRT:      ffmpeg.exe -hide_banner -i <input> -map 0:s:1 -c:s srt <output>.srt -y\n"
                "WebVTT:   ffmpeg.exe -hide_banner -i <input> -map 0:s:1 -c:s webvtt <output>.vtt -y\n"
                "ASS:      ffmpeg.exe -hide_banner -i <input> -map 0:s:1 -c:s ass <output>.ass -y\n\n"
                "Select a file above and click Run to begin.\n",

            cmd_builder=cmd_builder,
            output_namer=output_namer,
            options_builder=options_builder,
            file_filters=[
                ("Video files", "*.mp4 *.mov *.mkv *.avi *.mxf *.m4v *.wmv *.webm *.ts *.m2ts"),
                ("All files", "*.*"),
            ],
            output_filetypes=[
                ("Subtitle files", "*.srt *.vtt *.ass *.sup *.mks"), ("All files", "*.*"),
            ],
            validate=validate,
            label_width=LABEL_WIDTH,
        )

    def _build_inspect_tab(self, parent):
        _file_card, file_body = dashboard_card(parent, "File")
        input_frame = ctk.CTkFrame(file_body, fg_color="transparent")
        input_frame.pack(fill="x")

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

        inspect_actions = ctk.CTkFrame(file_body, fg_color="transparent")
        inspect_actions.pack(anchor="e", pady=(10, 0))

        inspect_btn = AccentButton(inspect_actions, text="Inspect", width=150)
        inspect_btn.pack(side="left", padx=(0, 6))

        abort_btn = AccentButton(
            inspect_actions, text="Abort", width=110, kind="danger", state="disabled",
            command=self._abort_current_operation
        )
        abort_btn.pack(side="left")

        progress = ActivityBar(parent, mode="indeterminate", height=6)
        progress.pack(fill="x", padx=4, pady=(2, 8))
        progress.set(0)

        log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))
        log_box.pack(fill="both", expand=True)
        log_box.configure(state="disabled")
        self._add_log_context_menu(log_box)
        self._log_with_info_icon(log_box, (
            "ℹ️  Inspect File\n"
            "Reads and displays all stream information from the file. \n"
            "codec, resolution, bitrate, audio format, aspect ratio without modifying it.\n"
            "Also lists every audio (language) track and subtitle track, with its language, "
            "format and flags (default, forced, SDH, commentary).\n\n"
            "Select a file above and click Inspect to begin.\n"
        ))


        def run_inspect():
            input_path = input_entry.get().strip()
            if not input_path:
                self._log(log_box, "Error: No input file selected.\n")
                return

            ffprobe_path = self._ffprobe_path
            if not ffprobe_path or not os.path.isfile(ffprobe_path):
                self._log(log_box, "Error: ffprobe.exe not found alongside ffmpeg.\n")
                return

            cmd = [
                ffprobe_path,
                "-hide_banner",
                "-v", "error",
                "-show_entries", "stream=index,codec_name,codec_type,channels,channel_layout",
                "-of", "default=noprint_wrappers=1",
                input_path
            ]

            def _log_aspect_ratio():
                probe_cmd = [
                    ffprobe_path,
                    "-hide_banner",
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "default=noprint_wrappers=1",
                    input_path
                ]
                try:
                    result = subprocess.run(
                        probe_cmd,
                        capture_output=True,
                        text=True,
                        timeout=15,
                        **SUBPROCESS_WINDOW_KWARGS
                    )
                except Exception:
                    return

                width = height = None
                for line in result.stdout.splitlines():
                    width_match = re.match(r"\s*width=(\d+)", line)
                    if width_match:
                        width = int(width_match.group(1))
                        continue
                    height_match = re.match(r"\s*height=(\d+)", line)
                    if height_match:
                        height = int(height_match.group(1))

                if width is None or height is None:
                    return
                try:
                    ratio = calculate_aspect_ratio(width, height)
                except (ValueError, ZeroDivisionError):
                    return
                self._log(log_box, (
                    f"Aspect Ratio: {ratio['raw_mathematical_ratio']} "
                    f"({ratio['industry_standard_match']}) \u2014 {ratio['dimensions']}\n"
                ))

            def _log_tracks():
                data = self._probe_full(input_path)
                if not data:
                    return
                streams = data.get("streams", [])
                audio = [s for s in streams if s.get("codec_type") == "audio"]
                subtitles = [s for s in streams if s.get("codec_type") == "subtitle"]

                def language_of(stream):
                    code = ((stream.get("tags") or {}).get("language") or "und").lower()
                    name = LANGUAGE_NAMES.get(code)
                    return f"{name} ({code})" if name else code

                def flags_of(stream):
                    disposition = stream.get("disposition") or {}
                    flags = [f for f in ("default", "forced") if disposition.get(f)]
                    if disposition.get("hearing_impaired"):
                        flags.append("SDH")
                    if disposition.get("comment"):
                        flags.append("commentary")
                    return f" [{', '.join(flags)}]" if flags else ""

                def title_of(stream):
                    title = (stream.get("tags") or {}).get("title")
                    return f" \"{title}\"" if title else ""

                lines = [f"\nAudio Tracks: {len(audio) or 'none'}"]
                for i, s in enumerate(audio):
                    layout = s.get("channel_layout") or f"{s.get('channels', '?')}ch"
                    lines.append(
                        f"  {i}: {language_of(s)} \u2014 {s.get('codec_name', '?')}, "
                        f"{layout}, {s.get('sample_rate', '?')} Hz"
                        f"{flags_of(s)}{title_of(s)}"
                    )

                lines.append(f"\nSubtitle Tracks: {len(subtitles) or 'none'}")
                for i, s in enumerate(subtitles):
                    codec = s.get("codec_name", "?")
                    kind = "picture" if codec in PICTURE_SUBTITLE_CODECS else "text"
                    lines.append(
                        f"  {i}: {language_of(s)} \u2014 "
                        f"{SUBTITLE_CODEC_NAMES.get(codec, codec)} ({kind})"
                        f"{flags_of(s)}{title_of(s)}"
                    )
                self._log(log_box, "\n".join(lines) + "\n\n")

            def _pre_process():
                _log_aspect_ratio()
                _log_tracks()

            self._run_ffmpeg(
                cmd, log_box, inspect_btn, progress,
                expect_error=True, abort_btn=abort_btn,
                pre_process=_pre_process,
            )

        inspect_btn.configure(command=run_inspect)

    def _build_custom_tab(self, parent):
        file_filters = [
            ("Video files", "*.mp4 *.mov *.mkv *.avi *.mxf *.m4v *.wmv"),
            ("Audio files", "*.wav *.mp3 *.aac *.flac *.ogg *.m4a"),
            ("All files", "*.*"),
        ]

        _files_card, files_body = dashboard_card(parent, "Files")
        input_frame = ctk.CTkFrame(files_body, fg_color="transparent")
        input_frame.pack(fill="x", pady=(0, 5))
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

        output_frame = ctk.CTkFrame(files_body, fg_color="transparent")
        output_frame.pack(fill="x")
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

        _cmd_card, cmd_body = dashboard_card(parent, "Command")
        cmd_box = ctk.CTkTextbox(cmd_body, height=80, font=ctk.CTkFont(family="Consolas", size=12))
        cmd_box.pack(fill="x")
        cmd_box.insert("1.0", "ffmpeg.exe -i <input> -c copy -y <output>")

        custom_actions = ctk.CTkFrame(cmd_body, fg_color="transparent")
        custom_actions.pack(anchor="e", pady=(10, 0))

        run_btn = AccentButton(custom_actions, text="Run Custom Command", width=190)
        run_btn.pack(side="left", padx=(0, 6))

        abort_btn = AccentButton(
            custom_actions, text="Abort", width=110, kind="danger", state="disabled",
            command=self._abort_current_operation
        )
        abort_btn.pack(side="left")

        progress = ActivityBar(parent, mode="indeterminate", height=6)
        progress.pack(fill="x", padx=4, pady=(2, 8))
        progress.set(0)

        log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=12))
        log_box.pack(fill="both", expand=True)
        log_box.configure(state="disabled")
        self._add_log_context_menu(log_box)
        self._log_with_info_icon(log_box, (
            "\U0001F6E0\ufe0f  Custom Command\n"
            "Build and run any FFmpeg command you like.\n\n"
            "\u2022 Use <input> and <output> as placeholders -- they will be replaced with your selected files.\n"
            "\u2022 Tick the Quick Build checkboxes and click 'Build from Checkboxes' for a head start.\n"
            "\u2022 Or type/paste your own full command string directly.\n\n"
            "\u26A0\ufe0f  The command runs via shell -- double-check before executing!\n\n"
            "Select your files, write your command, and click Run.\n"
        ))

        def run_command():
            input_path = input_entry.get().strip()
            output_path = output_entry.get().strip()
            raw_cmd = cmd_box.get("1.0", "end").strip()

            if not raw_cmd:
                self._log(log_box, "Error: No command entered.\n")
                return

            final_cmd = raw_cmd.replace("<input>", f'"{input_path}"').replace("<output>", f'"{output_path}"')

            self._clear_log(log_box)
            self._abort_event.clear()
            self._set_operation_running(True)
            run_btn.configure(state="disabled")
            abort_btn.configure(state="normal")
            progress.start()

            def worker():
                try:
                    self._log_running_cmd(log_box, final_cmd)

                    process = subprocess.Popen(
                        final_cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        errors="replace",
                        **SUBPROCESS_WINDOW_KWARGS
                    )
                    self._active_process = process

                    for line in process.stdout:
                        self._log(log_box, line)

                    process.wait()
                    returncode = process.returncode

                    self._log(log_box, f"\n{'=' * 60}\n")
                    if self._abort_event.is_set():
                        self._log(log_box, "Aborted.\n")
                    elif returncode == 0:
                        self._log(log_box, "Done!\n")
                    else:
                        self._log(log_box, f"Error \u2014 check log (exit code: {returncode})\n")

                except Exception as e:
                    self._log(log_box, f"Error: {e}\n")
                finally:
                    self._run_on_main(lambda: run_btn.configure(state="normal"))
                    self._run_on_main(lambda: abort_btn.configure(state="disabled"))
                    self._run_on_main(lambda: progress.stop())
                    self._run_on_main(lambda: progress.set(0))
                    self._run_on_main(lambda: self._set_operation_running(False))
                    self._active_process = None

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
        self._add_log_context_menu(log_box)

        _source_card, source_body = dashboard_card(parent, "Source")
        r1 = ctk.CTkFrame(source_body, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Input Format:", width=110, anchor="w").pack(side="left")
        in_fmt = ctk.StringVar(value="WAV")
        ctk.CTkOptionMenu(r1, values=FORMATS, variable=in_fmt, width=120,
                          command=lambda v: parent.after(150, scan)).pack(side="left")

        r2 = ctk.CTkFrame(source_body, fg_color="transparent")
        r2.pack(fill="x", pady=4)
        ctk.CTkLabel(r2, text="Source Folder:", width=110, anchor="w").pack(side="left")
        folder_ent = ctk.CTkEntry(r2, placeholder_text="Browse -- scans automatically...")
        folder_ent.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_folder():
            init_dir = folder_ent.get().strip() or None
            p = self._ask_folder_with_preview(
                initial_dir=init_dir, title="Select Source Folder"
            )
            if p:
                folder_ent.delete(0, "end")
                folder_ent.insert(0, p)
                parent.after(150, scan)

        ctk.CTkButton(r2, text="Browse", width=80, command=browse_folder).pack(side="left")

        r3 = ctk.CTkFrame(source_body, fg_color="transparent")
        r3.pack(fill="x")
        ctk.CTkLabel(r3, text="Output Format:", width=110, anchor="w").pack(side="left")
        out_fmt = ctk.StringVar(value="MP3")
        ctk.CTkOptionMenu(r3, values=FORMATS, variable=out_fmt, width=120).pack(side="left")

        _files_card, files_body = dashboard_card(parent)
        list_header = ctk.CTkFrame(files_body, fg_color="transparent")
        list_header.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(list_header, text="Files", font=ctk.CTkFont(size=14, weight="bold")).pack(
            side="left", padx=(0, 12))
        selection_label = ctk.CTkLabel(list_header, text="No folder scanned yet.", anchor="w",
                                       text_color=MUTED)
        selection_label.pack(side="left")
        select_none_btn = ctk.CTkButton(list_header, text="Select None", width=90, state="disabled")
        select_none_btn.pack(side="right", padx=(6, 0))
        select_all_btn = ctk.CTkButton(list_header, text="Select All", width=90, state="disabled")
        select_all_btn.pack(side="right")

        file_list = ctk.CTkScrollableFrame(files_body, height=150, fg_color=INSET,
                                           border_width=1, border_color=BORDER, corner_radius=10)
        file_list.pack(fill="x", pady=(0, 4))

        batch_actions = ctk.CTkFrame(files_body, fg_color="transparent")
        batch_actions.pack(anchor="e", pady=(4, 0))
        run_btn = AccentButton(batch_actions, text="Convert Selected", width=150, state="disabled")
        run_btn.pack(side="left", padx=(0, 6))
        abort_btn = AccentButton(
            batch_actions, text="Abort", width=110, kind="danger", state="disabled",
            command=self._abort_current_operation
        )
        abort_btn.pack(side="left")

        progress = ActivityBar(parent, mode="indeterminate", height=6)
        progress.pack(fill="x", padx=4, pady=(2, 8))
        progress.stop()

        log_box.pack(fill="both", expand=True)
        log_box.configure(state="disabled")
        self._log_with_info_icon(log_box, (
            "ℹ️  Batch Audio Convert\n"
            "Converts all audio files of a chosen format in a folder to a new format.\n"
            "Converted files are saved into a CONVERTED subfolder.\n\n"
            "Optimisations Applied:\n"
            "  - Case-Insensitive Path Scanning: Resolves duplicate asset detection bugs on Windows systems.\n"
            "  - Live Log Pipelines: Subprocess executions now output rendering frame progress markers interactively.\n\n"
            "1. Choose input audio format\n"
            "2. Click Browse -- the folder picker lists both subfolders and files as you navigate, so you can "
            "see what's actually in each folder, then click \"Select This Folder\" at any point (no need to "
            "click a specific file) -- the folder is then scanned automatically and matching files are listed "
            "below with checkboxes\n"
            "3. Tick/untick individual files -- untick everything except one to convert just a single file\n"
            "4. Choose output format (and bitrate/quality if MP3)\n"
            "5. Click Convert Selected to begin\n"
        ))

        files = []
        file_vars = {}

        def update_selection_count():
            total = len(files)
            selected = sum(1 for v in file_vars.values() if v.get())
            if total == 0:
                selection_label.configure(text="No folder scanned yet.")
            else:
                selection_label.configure(text=f"{selected} of {total} file(s) selected")
            run_btn.configure(state="normal" if selected else "disabled")

        def select_all():
            for v in file_vars.values():
                v.set(True)
            update_selection_count()

        def select_none():
            for v in file_vars.values():
                v.set(False)
            update_selection_count()

        select_all_btn.configure(command=select_all)
        select_none_btn.configure(command=select_none)

        def scan():
            nonlocal files
            for child in file_list.winfo_children():
                child.destroy()
            file_vars.clear()

            folder = folder_ent.get().strip()
            if not folder or not os.path.isdir(folder):
                files = []
                select_all_btn.configure(state="disabled")
                select_none_btn.configure(state="disabled")
                update_selection_count()
                return
            ext = EXT[in_fmt.get()]
            seen, files = set(), []
            glob_pattern = os.path.join(folder, f"*.{ext}")
            for f in sorted(glob.glob(glob_pattern) + glob.glob(os.path.join(folder, f"*.{ext.upper()}"))):
                normalized_path = os.path.abspath(f)
                if normalized_path.lower() not in seen:
                    seen.add(normalized_path.lower())
                    files.append(normalized_path)

            self._clear_log(log_box)
            if not files:
                self._log(log_box, f"No .{ext.upper()} files found in:\n{folder}\n")
                select_all_btn.configure(state="disabled")
                select_none_btn.configure(state="disabled")
                update_selection_count()
                return

            for f in files:
                var = ctk.BooleanVar(value=True)
                file_vars[f] = var
                ctk.CTkCheckBox(
                    file_list, text=os.path.basename(f), variable=var,
                    command=update_selection_count,
                ).pack(anchor="w", padx=6, pady=2)

            select_all_btn.configure(state="normal")
            select_none_btn.configure(state="normal")
            update_selection_count()

        def convert_all():
            selected = [f for f in files if file_vars.get(f) and file_vars[f].get()]
            if not selected:
                return
            folder = folder_ent.get().strip()
            fmt = out_fmt.get()
            ext = EXT[fmt]
            out_dir = os.path.join(folder, "CONVERTED")
            os.makedirs(out_dir, exist_ok=True)
            args = list(CODEC[fmt])
            self._abort_event.clear()
            self._set_operation_running(True)
            run_btn.configure(state="disabled")
            abort_btn.configure(state="normal")
            progress.stop()
            progress.configure(mode="determinate")
            progress.set(0)

            def set_progress(fraction):
                parent.after(0, lambda: progress.set(max(0.0, min(1.0, fraction))))

            def worker():
                count = len(selected)
                self._log(log_box, f"\n{SEP}\nConverting {count} file(s) -> {fmt}\n{SEP}\n\n")
                ok = fail = 0

                for i, inp in enumerate(selected, 1):
                    if self._abort_event.is_set():
                        break
                    base = os.path.splitext(os.path.basename(inp))[0]
                    outp = os.path.join(out_dir, f"{base}.{ext}")
                    self._log(log_box, f"[{i}/{count}] {os.path.basename(inp)} -> {base}.{ext}\n")
                    set_progress((i - 1) / count)

                    try:
                        duration = float(((self._probe_full(inp) or {}).get("format") or {}).get("duration") or 0)
                    except (TypeError, ValueError):
                        duration = 0

                    # Quiet ffmpeg; machine-readable progress on stdout, errors still come through.
                    # stdout must be drained continuously or ffmpeg blocks once the pipe buffer fills.
                    cmd = [self._ffmpeg_path, "-v", "error", "-nostats", "-progress", "pipe:1",
                           "-hide_banner", "-i", inp] + args + [outp, "-y"]
                    try:
                        proc = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            universal_newlines=True,
                            errors="replace",
                            **SUBPROCESS_WINDOW_KWARGS
                        )
                        self._active_process = proc
                        for line in proc.stdout:
                            line = line.strip()
                            key, sep, value = line.partition("=")
                            if sep and re.fullmatch(r"[a-z0-9_]+", key):
                                if key == "out_time_us" and duration:
                                    try:
                                        frac = max(0.0, int(value) / 1_000_000 / duration)
                                    except ValueError:
                                        continue
                                    set_progress((i - 1 + min(frac, 1.0)) / count)
                            elif line:
                                self._log(log_box, f"         {line}\n")
                        proc.wait()
                        self._active_process = None

                        if self._abort_event.is_set():
                            self._remove_partial(outp)
                            break
                        if proc.returncode == 0:
                            self._log(log_box, "         OK Done\n")
                            ok += 1
                        else:
                            self._log(log_box, f"         FAILED ({proc.returncode})\n")
                            self._remove_partial(outp)
                            fail += 1
                    except Exception as e:
                        self._active_process = None
                        self._log(log_box, f"         ERROR: {str(e)}\n")
                        self._remove_partial(outp)
                        fail += 1

                if self._abort_event.is_set():
                    self._log(log_box, "\nAborted -- the unfinished file was removed.\n")
                else:
                    set_progress(1.0)
                self._log(log_box, f"\n{SEP}\n{ok} converted, {fail} failed\nOutput folder: {out_dir}\n{SEP}\n")
                parent.after(0, update_selection_count)
                parent.after(0, lambda: abort_btn.configure(state="disabled"))
                parent.after(0, lambda: self._set_operation_running(False))

            threading.Thread(target=worker, daemon=True).start()

        run_btn.configure(command=convert_all)

    def _build_settings_tab(self, parent):
        _ffmpeg_card, ffmpeg_body = dashboard_card(parent, "FFmpeg")
        ffmpeg_frame = ctk.CTkFrame(ffmpeg_body, fg_color="transparent")
        ffmpeg_frame.pack(fill="x")

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
            ffmpeg_body,
            text=(f"Currently using: {resolved}" if resolved
                  else "Not found -- checked app folder, then system PATH, then this setting."),
            font=ctk.CTkFont(size=11),
            text_color=MUTED if resolved else AMBER,
            anchor="w",
        )
        ffmpeg_status_label.pack(fill="x", padx=(165, 0), pady=(4, 0))

        self._settings_ffmpeg_entry = ffmpeg_entry
        self._settings_ffmpeg_status_label = ffmpeg_status_label

        _output_card, output_body = dashboard_card(parent, "Output")
        folder_frame = ctk.CTkFrame(output_body, fg_color="transparent")
        folder_frame.pack(fill="x")

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

        _prefs_card, prefs_body = dashboard_card(parent, "Preferences")
        remember_var = ctk.BooleanVar(value=self._settings.get("remember_last_folder", True))
        ctk.CTkCheckBox(
            prefs_body, text="Remember last input folder", variable=remember_var
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkCheckBox(
            prefs_body, text="Show welcome screen at startup", variable=self._show_splash_var
        ).pack(anchor="w")

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
                text_color=MUTED if found else AMBER,
            )
            self._set_ffmpeg_status(found)
            if found:
                self._check_ffmpeg_version_and_warn()

            status_label.configure(text="Settings saved!", text_color=GREEN)
            self.after(3000, lambda: status_label.configure(text=""))

        save_row = ctk.CTkFrame(parent, fg_color="transparent")
        save_row.pack(fill="x", pady=(4, 0))
        AccentButton(save_row, text="Save Settings", width=170, command=save_settings).pack(side="right")

        status_label = ctk.CTkLabel(save_row, text="", font=ctk.CTkFont(size=12))
        status_label.pack(side="right", padx=12)

    def _log(self, textbox, text):
        if threading.current_thread() is not threading.main_thread():
            self._run_on_main(lambda: self._log(textbox, text))
            return
        textbox.configure(state="normal")
        textbox.insert("end", text)
        textbox.see("end")
        textbox.configure(state="disabled")

    def _clear_log(self, textbox):
        if threading.current_thread() is not threading.main_thread():
            self._run_on_main(lambda: self._clear_log(textbox))
            return
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.configure(state="disabled")

    def _add_log_context_menu(self, log_box):
        menu = self._dark_menu()
        menu.add_command(
            label="Launch Log Info with NOTEPAD",
            command=lambda: self._open_log_in_notepad(log_box),
        )
        menu.add_separator()
        menu.add_command(
            label="Clear Logs",
            command=lambda: self._clear_log(log_box),
        )

        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        log_box.bind("<Button-3>", show_menu)
        log_box.bind("<Control-Button-1>", show_menu)
        return menu

    def _open_log_in_notepad(self, log_box):
        content = log_box.get("1.0", "end-1c")
        try:
            fd, temp_path = tempfile.mkstemp(prefix="ffmpeg_toolkit_log_", suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as exc:
            messagebox.showerror("Couldn't open log", f"Failed to write log file:\n{exc}")
            return

        try:
            if sys.platform == "win32":
                subprocess.Popen(["notepad.exe", temp_path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "TextEdit", temp_path])
            else:
                subprocess.Popen(["xdg-open", temp_path])
        except Exception as exc:
            messagebox.showerror("Couldn't open log", f"Failed to launch editor:\n{exc}")

    def _display_cmd(self, cmd):
        if isinstance(cmd, (list, tuple)):
            parts = [
                os.path.basename(tok) if isinstance(tok, str) and re.search(r"[\\/]", tok) else tok
                for tok in cmd
            ]
            return " ".join(parts)
        return cmd

    def _log_running_cmd(self, log_box, cmd):
        full_cmd = " ".join(cmd) if isinstance(cmd, (list, tuple)) else cmd
        self._log(log_box, f"SIMPLIFIED COMMAND STRING\nRunning: {self._display_cmd(cmd)}\n\n")
        self._log(log_box, f"COMPLETE COMMAND STRING\nRunning: {full_cmd}\n\n")

    def _exec_ffmpeg_command(self, cmd, log_box, expect_error=False):
        try:
            self._log_running_cmd(log_box, cmd)
            self._last_run_suspected_old_ffmpeg = False

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                errors="replace",
                **SUBPROCESS_WINDOW_KWARGS
            )
            self._active_process = process

            for line in process.stdout:
                if expect_error and "At least one output file must be specified" in line:
                    continue
                if any(sig in line for sig in OLD_FFMPEG_ERROR_SIGNATURES):
                    self._last_run_suspected_old_ffmpeg = True
                self._log(log_box, line)

            process.wait()
            if self._abort_event.is_set():
                return "aborted"
            return process.returncode

        except FileNotFoundError:
            self._log(log_box, "Error: ffmpeg not found. Set its location in Settings.\n")
            return None
        except Exception as e:
            self._log(log_box, f"Error: {e}\n")
            return None
        finally:
            self._active_process = None

    def _run_ffmpeg(
        self, cmd, log_box, btn, progress, expect_error=False, abort_btn=None,
        pre_process=None, on_success=None,
    ):
        self._clear_log(log_box)
        self._abort_event.clear()
        self._set_operation_running(True)
        btn.configure(state="disabled")
        if abort_btn is not None:
            abort_btn.configure(state="normal")
        progress.start()

        def worker():
            if pre_process is not None:
                pre_process()

            returncode = self._exec_ffmpeg_command(cmd, log_box, expect_error=expect_error)

            if returncode is not None:
                self._log(log_box, f"\n{'=' * 60}\n")
                if returncode == "aborted":
                    self._log(log_box, "Aborted.\n")
                elif returncode == 0:
                    self._log(log_box, "Done!\n")
                    if on_success is not None:
                        self._run_on_main(on_success)
                elif expect_error and returncode == 1:
                    self._log(log_box, "Inspection complete.\n")
                else:
                    self._log(log_box, f"Error \u2014 check log (exit code: {returncode})\n")
                    if self._last_run_suspected_old_ffmpeg:
                        self._run_on_main(self._show_old_ffmpeg_warning)

            self._run_on_main(lambda: btn.configure(state="normal"))
            if abort_btn is not None:
                self._run_on_main(lambda: abort_btn.configure(state="disabled"))
            self._run_on_main(lambda: progress.stop())
            self._run_on_main(lambda: progress.set(0))
            self._run_on_main(lambda: self._set_operation_running(False))

        threading.Thread(target=worker, daemon=True).start()

    def _run_ffmpeg_with_fallback(
        self, primary_cmd, fallback_cmd, log_box, btn, progress, abort_btn=None
    ):
        self._clear_log(log_box)
        self._abort_event.clear()
        self._set_operation_running(True)
        btn.configure(state="disabled")
        if abort_btn is not None:
            abort_btn.configure(state="normal")
        progress.start()

        def worker():
            returncode = self._exec_ffmpeg_command(primary_cmd, log_box)

            if returncode == "aborted":
                self._log(log_box, "Aborted.\n")
            elif returncode == 0:
                self._log(log_box, f"\n{'=' * 60}\nDone!\n")
            elif returncode is not None:
                self._log(
                    log_box,
                    f"\n{'=' * 60}\nStream copy failed (exit code: {returncode}) \u2014 retrying with re-encode...\n{'=' * 60}\n",
                )
                if self._abort_event.is_set():
                    self._log(log_box, "Aborted.\n")
                else:
                    returncode2 = self._exec_ffmpeg_command(fallback_cmd, log_box)
                    self._log(log_box, f"\n{'=' * 60}\n")
                    if returncode2 == 0:
                        self._log(log_box, "Done (re-encoded)!\n")
                    elif returncode2 is not None:
                        self._log(log_box, f"Error (exit code: {returncode2})\n")

            self._run_on_main(lambda: btn.configure(state="normal"))
            if abort_btn is not None:
                self._run_on_main(lambda: abort_btn.configure(state="disabled"))
            self._run_on_main(lambda: progress.stop())
            self._run_on_main(lambda: progress.set(0))
            self._run_on_main(lambda: self._set_operation_running(False))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    apply_dashboard_theme()
    app = FFmpegToolkit()
    app.mainloop()
