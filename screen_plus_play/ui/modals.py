from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog

from screen_plus_play.core.config import DEFAULT_APP_PROFILE, DISPLAY_PRESETS
from .theme import THEME, ui_font


class ConnectionBridgeModal(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Connect Phone — Screen+Play")
        self.geometry("460x280")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=THEME["bg_canvas"])
        ctk.CTkLabel(self, text="BRIDGE CONNECTION", text_color=THEME["accent_gold"], font=ui_font(15, "bold")).pack(pady=14)
        ctk.CTkButton(self, text="🔌 Connect via USB", command=lambda: self._connect("usb"), fg_color=THEME["accent_gold"], text_color=THEME["text_on_gold"]).pack(fill="x", padx=24, pady=5)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=5)
        self.target = ctk.CTkEntry(row, placeholder_text="192.168.1.50:5555")
        self.target.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.target.insert(0, parent.get_cfg("wifi_target") or "")
        ctk.CTkButton(row, text="Connect Wi-Fi", width=110, command=lambda: self._connect("wifi")).pack(side="right")
        self.status = ctk.CTkLabel(self, text="", text_color=THEME["text_secondary"])
        self.status.pack(pady=5)
        ctk.CTkButton(self, text="⚡ Auto-Pair Wi-Fi from Plugged-in USB", command=self._pair).pack(pady=5)

    def _connect(self, mode):
        if mode == "wifi":
            self.parent.data["config"]["wifi_target"] = self.target.get().strip()
            self.parent.save_data()
        self.parent.detect_device_async(mode)
        self.destroy()

    def _pair(self):
        self.status.configure(text="Enabling wireless ADB over USB...")
        def paired(target):
            if target:
                self.parent.data["config"]["wifi_target"] = target
                self.parent.save_data()
                self.target.delete(0, "end")
                self.target.insert(0, target)
                self.status.configure(text=f"Paired {target}; you can unplug USB now.")
            else:
                self.status.configure(text="Connect the phone via USB and enable debugging first.")
        self.parent.run_worker(self.parent.android.enable_tcpip_from_usb, paired,
            lambda exc: self.status.configure(text=f"Pairing failed: {exc}"))


class GameConfigModal(ctk.CTkToplevel):
    def __init__(self, parent, app_entry, profile):
        super().__init__(parent)
        self.parent, self.entry, self.profile = parent, app_entry, profile
        self.title(f"Configure — {profile.get('display_name') or app_entry['name']}")
        self.geometry("720x700")
        self.minsize(650, 600)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=THEME["bg_canvas"])
        self.grid_columnconfigure(1, weight=1)
        header = ctk.CTkLabel(self, text=f"⚙ {app_entry['name']}  •  {app_entry['package']}", font=ui_font(15, "bold"), text_color=THEME["accent_gold"])
        header.grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=12)
        body = ctk.CTkScrollableFrame(self, fg_color=THEME["bg_surface"])
        body.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=14, pady=4)
        self.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(1, weight=1)
        definitions = [("display_name", "Display / search title"), ("resolution", "Virtual resolution"), ("dpi", "DPI density"),
            ("fps", "Max FPS"), ("video_codec", "Video codec"), ("encoder", "Hardware encoder"),
            ("usb_bitrate", "USB bitrate"), ("wifi_bitrate", "Wi-Fi bitrate"), ("audio_mode", "Audio mode"),
            ("input_mode", "Input mode"), ("sgp_path", "ShaderGlass .sgp profile"), ("custom_args", "Custom scrcpy flags")]
        self.fields = {}
        for row, (key, label) in enumerate(definitions):
            ctk.CTkLabel(body, text=label, font=ui_font(11)).grid(row=row, column=0, sticky="w", padx=12, pady=5)
            entry = ctk.CTkEntry(body, fg_color=THEME["bg_canvas"])
            entry.insert(0, str(profile.get(key, DEFAULT_APP_PROFILE.get(key, ""))))
            entry.grid(row=row, column=1, sticky="ew", padx=12, pady=5)
            self.fields[key] = entry
        self.desc = ctk.CTkTextbox(body, height=72, fg_color=THEME["bg_canvas"])
        self.desc.insert("1.0", profile.get("description", ""))
        self.desc.grid(row=12, column=0, columnspan=2, sticky="ew", padx=12, pady=5)
        self.github = ctk.CTkLabel(body, text=profile.get("github_info", ""), text_color=THEME["gh_badge"], wraplength=560, justify="left", font=ui_font(10, "bold"))
        self.github.grid(row=13, column=0, columnspan=2, sticky="w", padx=12, pady=4)
        self.vars = {}
        flags = (("pinned", "Pin to Screen+Play home shelf"), ("turn_screen_off", "Turn off phone display"),
            ("stay_awake", "Keep phone awake"), ("use_shaderglass", "Enable ShaderGlass overlay"),
            ("auto_close_on_exit", "Close stream when the phone app exits"),
            ("no_vd_decorations", "Hide virtual display decorations"), ("no_vd_destroy", "Preserve app state on close"))
        for row, (key, label) in enumerate(flags, 14):
            var = ctk.BooleanVar(value=bool(profile.get(key, DEFAULT_APP_PROFILE.get(key, False))))
            ctk.CTkCheckBox(body, text=label, variable=var, fg_color=THEME["accent_gold"], font=ui_font(11)).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=4)
            self.vars[key] = var
        artwork = ctk.CTkFrame(body, fg_color="transparent")
        artwork.grid(row=21, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        ctk.CTkButton(artwork, text="Pull App Icon from Phone", command=self._pull_icon).pack(side="left", padx=(0, 8))
        ctk.CTkButton(artwork, text="Set Custom Poster Image...", command=self._pick_poster).pack(side="left")
        self.status = ctk.CTkLabel(body, text="", text_color=THEME["accent_gold"], font=ui_font(10))
        self.status.grid(row=22, column=0, columnspan=2, sticky="w", padx=12, pady=4)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=3, sticky="ew", padx=14, pady=10)
        ctk.CTkButton(footer, text="Cancel", command=self.destroy, fg_color=THEME["bg_elevated"]).pack(side="right", padx=5)
        ctk.CTkButton(footer, text="Save & Apply", command=self._save, fg_color=THEME["accent_gold"], text_color=THEME["text_on_gold"]).pack(side="right", padx=5)
        ctk.CTkButton(footer, text="Crawl Art, Wiki & GitHub", command=self._crawl, fg_color=THEME["bg_elevated"]).pack(side="left")

    def _crawl(self):
        self.status.configure(text="Crawling Wikipedia, GitHub and SteamGridDB...")
        title = self.fields["display_name"].get().strip() or self.entry["name"]
        self.parent.crawl_profile_async(self.entry["package"], title, self._metadata_done)

    def _metadata_done(self, result):
        if result.description:
            self.desc.delete("1.0", "end")
            self.desc.insert("1.0", result.description)
        if result.github_info:
            self.github.configure(text=result.github_info)
        self.status.configure(text="Metadata and available artwork updated.")

    def _pull_icon(self):
        self.status.configure(text="Pulling app icon from connected Android device...")
        self.parent.pull_icon_async(self.entry["package"], lambda _path: self.status.configure(text="App icon cached and views refreshed."))

    def _pick_poster(self):
        selected = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if selected:
            self.status.configure(text="Loading custom poster...")
            self.parent.set_custom_poster(self.entry["package"], selected, lambda _path: self.status.configure(text="Custom poster applied."))

    def _save(self):
        for key, entry in self.fields.items():
            self.profile[key] = entry.get().strip()
        for key, variable in self.vars.items():
            self.profile[key] = variable.get()
        self.profile["description"] = self.desc.get("1.0", "end").strip()
        self.parent.save_data()
        self.parent.art_cache.invalidate(self.entry["package"])
        self.parent.refresh_views()
        self.destroy()


class GlobalSettingsModal(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Global Settings — Screen+Play")
        self.geometry("620x470")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=THEME["bg_canvas"])
        self.grid_columnconfigure(1, weight=1)
        self.entries = {}
        settings = [("scrcpy_dir", "scrcpy folder"), ("shaderglass_exe", "ShaderGlass executable"),
            ("default_sgp", "Default .sgp profile"), ("wifi_target", "Wi-Fi ADB target"),
            ("steamgriddb_api_key", "SteamGridDB API key")]
        for row, (key, label) in enumerate(settings):
            ctk.CTkLabel(self, text=label, font=ui_font(11)).grid(row=row, column=0, sticky="w", padx=15, pady=7)
            entry = ctk.CTkEntry(self, show="*" if key.endswith("api_key") else "")
            entry.insert(0, str(parent.get_cfg(key) or ""))
            entry.grid(row=row, column=1, sticky="ew", padx=15, pady=7)
            self.entries[key] = entry
        ctk.CTkLabel(self, text="Display preset").grid(row=5, column=0, sticky="w", padx=15, pady=7)
        self.display = ctk.CTkComboBox(self, values=list(DISPLAY_PRESETS))
        self.display.set(parent.get_cfg("active_display_preset"))
        self.display.grid(row=5, column=1, sticky="ew", padx=15, pady=7)
        self.follow = ctk.BooleanVar(value=parent.get_cfg("follow_display_preset"))
        ctk.CTkCheckBox(self, text="Follow display preset", variable=self.follow).grid(row=6, column=1, sticky="w", padx=15, pady=7)
        self.borderless = ctk.BooleanVar(value=parent.get_cfg("borderless_mode"))
        ctk.CTkCheckBox(self, text="Borderless full-screen window", variable=self.borderless).grid(row=7, column=1, sticky="w", padx=15, pady=7)
        self.screen_off = ctk.BooleanVar(value=parent.get_cfg("default_turn_screen_off"))
        ctk.CTkCheckBox(self, text="Turn off phone screen on launch", variable=self.screen_off).grid(row=8, column=1, sticky="w", padx=15, pady=7)
        self.power_off = ctk.BooleanVar(value=parent.get_cfg("default_power_off_on_close"))
        ctk.CTkCheckBox(self, text="Lock phone when stream closes", variable=self.power_off).grid(row=9, column=1, sticky="w", padx=15, pady=7)
        ctk.CTkButton(self, text="Save Settings", command=self._save, fg_color=THEME["accent_gold"], text_color=THEME["text_on_gold"]).grid(row=10, column=1, sticky="e", padx=15, pady=16)

    def _save(self):
        self.parent.data["config"].update({key: entry.get().strip() for key, entry in self.entries.items()})
        self.parent.data["config"].update(active_display_preset=self.display.get(), follow_display_preset=self.follow.get(),
            borderless_mode=self.borderless.get(), default_turn_screen_off=self.screen_off.get(),
            default_power_off_on_close=self.power_off.get())
        self.parent.save_data()
        self.parent.apply_window_chrome()
        self.parent.refresh_views()
        self.destroy()
