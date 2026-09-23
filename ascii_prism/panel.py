"""Tkinter customizer panel. Runs in the main thread alongside the OpenCV
window; the app calls `pump()` once per frame to process its events.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Callable

from .charsets import CHARSETS, by_id
from .settings import COLUMNS_RANGE, RANGES, SMOOTHING_RANGE, Settings

GRADING = (("saturation", "Saturation"), ("hue", "Hue"), ("brightness", "Brightness"), ("opacity", "Opacity"))


class Panel:
    def __init__(self, settings: Settings, on_change: Callable[[], None], on_lock: Callable[[], bool], on_reset: Callable[[], None]):
        self.settings = settings
        self.on_change = on_change
        self.on_lock = on_lock
        self.on_reset = on_reset
        self.visible = True
        self._syncing = False

        self.root = tk.Tk()
        self.root.title("ASCII Prism")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._build()
        self.sync()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        pad = {"padx": 12, "pady": 3}
        frame = ttk.Frame(self.root, padding=(6, 8))
        frame.grid(sticky="nsew")

        ttk.Label(frame, text="Characters", font=("TkDefaultFont", 10, "bold")).grid(sticky="w", **pad)
        self.preset_var = tk.StringVar()
        self.preset = ttk.Combobox(frame, textvariable=self.preset_var, state="readonly", width=28,
                                   values=[cs.label for cs in CHARSETS] + ["Custom"])
        self.preset.grid(sticky="ew", **pad)
        self.preset.bind("<<ComboboxSelected>>", self._preset_chosen)

        ttk.Label(frame, text="Ramp, dark to bright").grid(sticky="w", **pad)
        self.ramp_var = tk.StringVar()
        ramp = ttk.Entry(frame, textvariable=self.ramp_var, width=30, font=("Menlo", 12))
        ramp.grid(sticky="ew", **pad)
        self.ramp_var.trace_add("write", self._ramp_edited)
        self.levels = ttk.Label(frame, text="")
        self.levels.grid(sticky="w", **pad)

        self.invert_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Invert brightness", variable=self.invert_var,
                        command=lambda: self._set("invert", self.invert_var.get())).grid(sticky="w", **pad)

        ttk.Separator(frame).grid(sticky="ew", pady=6)
        ttk.Label(frame, text="Resolution", font=("TkDefaultFont", 10, "bold")).grid(sticky="w", **pad)
        self.columns_label = ttk.Label(frame, text="")
        self.columns_label.grid(sticky="w", **pad)
        self.columns_var = tk.IntVar()
        ttk.Scale(frame, from_=COLUMNS_RANGE[0], to=COLUMNS_RANGE[1], variable=self.columns_var,
                  command=self._columns_moved).grid(sticky="ew", **pad)
        self.rows_label = ttk.Label(frame, text="Rows follow the shape of the region")
        self.rows_label.grid(sticky="w", **pad)

        ttk.Separator(frame).grid(sticky="ew", pady=6)
        ttk.Label(frame, text="Colour", font=("TkDefaultFont", 10, "bold")).grid(sticky="w", **pad)
        self.grade_vars: dict[str, tk.DoubleVar] = {}
        self.grade_labels: dict[str, ttk.Label] = {}
        for name, _title in GRADING:
            self.grade_labels[name] = ttk.Label(frame, text="")
            self.grade_labels[name].grid(sticky="w", **pad)
            self.grade_vars[name] = tk.DoubleVar()
            lo, hi = RANGES[name]
            ttk.Scale(frame, from_=lo, to=hi, variable=self.grade_vars[name],
                      command=lambda value, n=name: self._grade_moved(n, value)).grid(sticky="ew", **pad)
        self.bg_button = tk.Button(frame, text="Backdrop", width=12, command=self._pick_background)
        self.bg_button.grid(sticky="w", **pad)

        ttk.Separator(frame).grid(sticky="ew", pady=6)
        ttk.Label(frame, text="Tracking", font=("TkDefaultFont", 10, "bold")).grid(sticky="w", **pad)
        self.smoothing_label = ttk.Label(frame, text="")
        self.smoothing_label.grid(sticky="w", **pad)
        self.smoothing_var = tk.DoubleVar()
        ttk.Scale(frame, from_=SMOOTHING_RANGE[0], to=SMOOTHING_RANGE[1], variable=self.smoothing_var,
                  command=self._smoothing_moved).grid(sticky="ew", **pad)
        self.tips_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Show fingertips and outline", variable=self.tips_var,
                        command=lambda: self._set("show_tips", self.tips_var.get())).grid(sticky="w", **pad)
        self.mirror_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Mirror camera", variable=self.mirror_var,
                        command=lambda: self._set("mirror", self.mirror_var.get())).grid(sticky="w", **pad)

        ttk.Separator(frame).grid(sticky="ew", pady=6)
        buttons = ttk.Frame(frame)
        buttons.grid(sticky="ew", **pad)
        self.lock_button = ttk.Button(buttons, text="Lock region", command=self._lock)
        self.lock_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Reset to defaults", command=self._reset).grid(row=0, column=1)
        self.status = ttk.Label(frame, text="", foreground="#666")
        self.status.grid(sticky="w", **pad)
        ttk.Label(frame, text="Keys in the video window: L lock  H panel  T tips  M mirror  F fullscreen  Q quit",
                  foreground="#666", wraplength=260).grid(sticky="w", **pad)

    # -------------------------------------------------------------- callbacks
    def _set(self, name: str, value) -> None:
        if self._syncing:
            return
        setattr(self.settings, name, value)
        self.on_change()

    def _preset_chosen(self, _event=None) -> None:
        label = self.preset_var.get()
        for cs in CHARSETS:
            if cs.label == label:
                self.settings.charset_id = cs.id
                self.settings.charset = cs.chars
                self._syncing = True
                self.ramp_var.set(cs.chars)
                self._syncing = False
                self._update_levels()
                self.on_change()
                return
        self.settings.charset_id = "custom"

    def _ramp_edited(self, *_args) -> None:
        if self._syncing:
            return
        self.settings.charset = self.ramp_var.get() or " "
        self.settings.charset_id = "custom"
        self.preset_var.set("Custom")
        self._update_levels()
        self.on_change()

    def _update_levels(self) -> None:
        self.levels.config(text=f"{len(self.settings.chars())} brightness levels")

    def _columns_moved(self, value) -> None:
        if self._syncing:
            return
        self.settings.columns = int(float(value))
        self.columns_label.config(text=f"Characters across: {self.settings.columns}")
        self.on_change()

    def _smoothing_moved(self, value) -> None:
        if self._syncing:
            return
        self.settings.smoothing = round(float(value), 2)
        self.smoothing_label.config(text=f"Smoothing: {self.settings.smoothing:.2f}")
        self.on_change()

    def _grade_moved(self, name: str, value) -> None:
        if self._syncing:
            return
        setattr(self.settings, name, float(round(float(value))) if name == "hue" else round(float(value), 2))
        self._update_grade_label(name)
        self.on_change()

    def _update_grade_label(self, name: str) -> None:
        value = getattr(self.settings, name)
        title = dict(GRADING)[name]
        text = f"{title}: {value:+.0f}°" if name == "hue" else f"{title}: {value * 100:.0f}%"
        self.grade_labels[name].config(text=text)

    def _pick_background(self) -> None:
        _rgb, hex_value = colorchooser.askcolor(color=self.settings.background, parent=self.root, title="Choose backdrop colour")
        if hex_value:
            self._set("background", hex_value)
            self.bg_button.config(bg=hex_value)

    def _lock(self) -> None:
        self.set_locked(self.on_lock())

    def _reset(self) -> None:
        self.on_reset()
        self.sync()

    # ----------------------------------------------------------------- public
    def set_locked(self, locked: bool) -> None:
        self.lock_button.config(text="Unlock region" if locked else "Lock region")

    def set_status(self, text: str) -> None:
        self.status.config(text=text)

    def sync(self) -> None:
        """Refresh every widget from the settings object."""
        s = self.settings
        self._syncing = True
        try:
            cs = by_id(s.charset_id)
            self.preset_var.set(cs.label if cs and cs.chars == s.charset else "Custom")
            self.ramp_var.set(s.charset)
            self.invert_var.set(s.invert)
            self.columns_var.set(s.columns)
            self.columns_label.config(text=f"Characters across: {s.columns}")
            for name, _title in GRADING:
                self.grade_vars[name].set(getattr(s, name))
                self._update_grade_label(name)
            self.bg_button.config(bg=s.background)
            self.smoothing_var.set(s.smoothing)
            self.smoothing_label.config(text=f"Smoothing: {s.smoothing:.2f}")
            self.tips_var.set(s.show_tips)
            self.mirror_var.set(s.mirror)
            self._update_levels()
        finally:
            self._syncing = False

    def pump(self) -> None:
        self.root.update()

    def hide(self) -> None:
        self.root.withdraw()
        self.visible = False

    def show(self) -> None:
        self.root.deiconify()
        self.visible = True

    def toggle(self) -> None:
        self.hide() if self.visible else self.show()

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass
