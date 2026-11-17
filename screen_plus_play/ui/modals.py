from __future__ import annotations

import customtkinter as ctk
from tkinter import filedialog

from screen_plus_play.core.config import DISPLAY_PRESETS
from .theme import THEME, ui_font


class ConnectionBridgeModal(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Connect Phone — Screen+Play")
        self.geometry("440x240")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=THEME["bg_canvas"])
        ctk.CTkLabel(self, text="BRIDGE CONNECTION", text_color=THEME["accent_gold"], font=ui_font(15, "bold")).pack(pady=16)
        ctk.CTkButton(self, text="Connect via USB", command=lambda: self._connect("usb"), fg_color=THEME["accent_gold"], text_color=THEME["text_on_gold"]).pack(fill="x", padx=24, pady=6)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=6)
        self.target = ctk.CTkEntry(row, placeholder_text="192.168.1.50:5555")
        self.target.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.target.insert(0, parent.get_cfg("wifi_target"))
        ctk.CTkButton(row, text="Wi-Fi", width=80, command=lambda: self._connect("wifi")).pack(side="right")
        self.status = ctk.CTkLabel(self, text="", text_color=THEME["text_secondary"])
        self.status.pack(pady=8)
        ctk.CTkButton(self, text="Enable Wi-Fi ADB from USB", command=self._pair).pack(pady=4)

    def _connect(self, mode):
        if mode == "wifi":
            self.parent.data["config"]["wifi_target"] = self.target.get().strip()
            self.parent.save_data()
        self.parent.detect_device_async(mode)
        self.destroy()

    def _pair(self):
        self.status.configure(text="Enabling wireless ADB...")
        self.parent.run_worker(self.parent.android.enable_tcpip_from_usb, self._paired)

    def _paired(self, target):
        if target:
            self.target.delete(0, "end")
            self.target.insert(0, target)
            self.status.configure(text=f"Paired {target}")


class GameConfigModal(ctk.CTkToplevel):
    def __init__(self, parent, app_entry, profile):
        super().__init__(parent)
        self.parent, self.entry, self.profile = parent, app_entry, profile
        self.title(f"Configure — {app_entry['name']}")
        self.geometry("620x570")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=THEME["bg_canvas"])
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=f"⚙ {app_entry['name']}", font=ui_font(16, "bold"), text_color=THEME["accent_gold"]).grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=14)
        self.fields = {}
        definitions = [("display_name", "Display title"), ("resolution", "Resolution"), ("dpi", "DPI"), ("fps", "Max FPS"), ("video_codec", "Video codec"), ("encoder", "Encoder"), ("usb_bitrate", "USB bitrate"), ("wifi_bitrate", "Wi-Fi bitrate"), ("audio_mode", "Audio mode"), ("input_mode", "Input mode"), ("custom_args", "Custom scrcpy flags"), ("sgp_path", "ShaderGlass profile")]
        for row, (key, label) in enumerate(definitions, 1):
            ctk.CTkLabel(self, text=label, font=ui_font(11)).grid(row=row, column=0, sticky="w", padx=18, pady=4)
            entry = ctk.CTkEntry(self, fg_color=THEME["bg_surface"])
            entry.insert(0, str(profile.get(key, "")))
            entry.grid(row=row, column=1, sticky="ew", padx=18, pady=4)
            self.fields[key] = entry
        self.desc = ctk.CTkTextbox(self, height=60, fg_color=THEME["bg_surface"])
        self.desc.insert("1.0", profile.get("description", ""))
        self.desc.grid(row=13, column=0, columnspan=2, sticky="ew", padx=18, pady=6)
        self.vars = {}
        for row, key, label in ((14, "pinned", "Pin to shelf"), (15, "turn_screen_off", "Turn off phone display"), (16, "stay_awake", "Keep phone awake"), (17, "use_shaderglass", "Enable ShaderGlass"), (18, "auto_close_on_exit", "Close stream when app exits")):
            var = ctk.BooleanVar(value=bool(profile.get(key, False)))
            ctk.CTkCheckBox(self, text=label, variable=var, fg_color=THEME["accent_gold"], font=ui_font(11)).grid(row=row, column=0, columnspan=2, sticky="w", padx=18, pady=3)
            self.vars[key] = var
        ctk.CTkButton(self, text="Crawl metadata & artwork", command=self._crawl).grid(row=19, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkButton(self, text="Save & Apply", command=self._save, fg_color=THEME["accent_gold"], text_color=THEME["text_on_gold"]).grid(row=19, column=1, padx=18, pady=8, sticky="e")

    def _crawl(self):
        self.parent.crawl_profile_async(self.entry["package"], self.fields["display_name"].get() or self.entry["name"], self._metadata_done)

    def _metadata_done(self, result):
        if result.description:
            self.desc.delete("1.0", "end")
            self.desc.insert("1.0", result.description)

    def _save(self):
        for key, entry in self.fields.items(): self.profile[key] = entry.get().strip()
        for key, var in self.vars.items(): self.profile[key] = var.get()
        self.profile["description"] = self.desc.get("1.0", "end").strip()
        self.parent.save_data()
        self.parent.refresh_views()
        self.destroy()


class GlobalSettingsModal(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Global Settings — Screen+Play")
        self.geometry("600x440")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=THEME["bg_canvas"])
        self.grid_columnconfigure(1, weight=1)
        self.entries = {}
        settings = [("scrcpy_dir", "scrcpy folder"), ("shaderglass_exe", "ShaderGlass executable"), ("default_sgp", "Default .sgp"), ("wifi_target", "Wi-Fi ADB target"), ("steamgriddb_api_key", "SteamGridDB API key")]
        for row, (key, label) in enumerate(settings):
            ctk.CTkLabel(self, text=label).grid(row=row, column=0, sticky="w", padx=15, pady=7)
            entry = ctk.CTkEntry(self, show="*" if key.endswith("api_key") else "")
            entry.insert(0, str(parent.get_cfg(key) or ""))
            entry.grid(row=row, column=1, sticky="ew", padx=15, pady=7)
            self.entries[key] = entry
        self.display = ctk.CTkComboBox(self, values=list(DISPLAY_PRESETS))
        self.display.set(parent.get_cfg("active_display_preset"))
        ctk.CTkLabel(self, text="Display preset").grid(row=5, column=0, sticky="w", padx=15, pady=7)
        self.display.grid(row=5, column=1, sticky="ew", padx=15, pady=7)
        self.follow = ctk.BooleanVar(value=parent.get_cfg("follow_display_preset"))
        ctk.CTkCheckBox(self, text="Follow display preset", variable=self.follow).grid(row=6, column=1, sticky="w", padx=15, pady=7)
        self.borderless = ctk.BooleanVar(value=parent.get_cfg("borderless_mode"))
        ctk.CTkCheckBox(self, text="Borderless full-screen window", variable=self.borderless).grid(row=7, column=1, sticky="w", padx=15, pady=7)
        ctk.CTkButton(self, text="Save Settings", command=self._save, fg_color=THEME["accent_gold"], text_color=THEME["text_on_gold"]).grid(row=8, column=1, sticky="e", padx=15, pady=16)

    def _save(self):
        self.parent.data["config"].update({key: entry.get().strip() for key, entry in self.entries.items()})
        self.parent.data["config"].update(active_display_preset=self.display.get(), follow_display_preset=self.follow.get(), borderless_mode=self.borderless.get())
        self.parent.save_data()
        self.parent.apply_window_chrome()
        self.parent.refresh_views()
        self.destroy()
