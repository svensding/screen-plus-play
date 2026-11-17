from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import customtkinter as ctk

from screen_plus_play.core.android import AndroidManager
from screen_plus_play.core.config import DEFAULT_APP_PROFILE, DEFAULT_CONFIG, DISPLAY_PRESETS
from screen_plus_play.core.data_store import load_data, save_data
from screen_plus_play.core.launcher import SessionRunner, build_scrcpy_cmd
from screen_plus_play.core.metadata import GameMetadataCrawler
from screen_plus_play.core.platform_win import GamepadPoller
from screen_plus_play.core.models import MetadataResult
from .artwork import ArtworkCache
from .couch_view import CouchView
from .library_view import LibraryView
from .modals import ConnectionBridgeModal, GameConfigModal, GlobalSettingsModal
from .overlays import HandoffOverlay, StartupOverlay
from .theme import THEME, render_brand_logo, ui_font


class ScreenPlusPlayApp(ctk.CTk):
    """UI composition root. Worker results are drained on the Tk main loop."""
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("SCREEN+PLAY")
        self.configure(fg_color=THEME["bg_canvas"])
        self.base_dir = Path(__file__).resolve().parents[2]
        self.data_file = self.base_dir / "launcher_data.json"
        self.cache_dir = self.base_dir / "art_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.data = load_data(self.data_file, self.base_dir / "profiles_v2.json", self.base_dir / "profiles.json")
        self.android = AndroidManager(self.get_cfg, self.cache_dir)
        self.runner = SessionRunner(self.android, self.get_cfg("scrcpy_dir"), self.get_cfg("shaderglass_exe"), self.get_cfg("default_sgp"))
        self.controller = GamepadPoller(self._on_gamepad_event)
        self.controller.start()
        self.art_cache = ArtworkCache()
        self.surface_mode = "couch"
        self.library_filter = "all"
        self.library_layout = self.get_cfg("library_layout") or "poster_wall"
        self.device_apps_cache = []
        self.visible_apps = []
        self.focused_index = 0
        self.in_game_session = False
        self._results: queue.Queue = queue.Queue()
        self._resize_job = None
        self.geometry("1280x800")
        self._build_shell()
        # Mount CouchView immediately so startup has a real, visible home surface.
        self.couch_view.grid(row=0, column=0, sticky="nsew")
        self.library_view.grid_remove()
        logo_pil = render_brand_logo(64)
        logo = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=logo_pil.size)
        self.startup_overlay = StartupOverlay(self, logo)
        self.handoff_overlay = HandoffOverlay(self)
        self.startup_overlay.show_briefly(None)
        self._bind_keys()
        self.after(20, self._drain_results)
        self.after(250, self.detect_device_async)
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.refresh_views()

    def _build_shell(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, height=58, corner_radius=0, fg_color=THEME["bg_hud"])
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(3, weight=1)
        logo_pil = render_brand_logo(30)
        self.logo = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=logo_pil.size)
        ctk.CTkLabel(header, text="", image=self.logo).grid(row=0, column=0, padx=(18, 5), pady=8)
        ctk.CTkLabel(header, text="SCREEN+PLAY", font=ui_font(16, "bold"), text_color=THEME["text_primary"]).grid(row=0, column=1, padx=5)
        self.device_button = ctk.CTkButton(header, text="● Connect Phone", command=self.open_connection_modal, font=ui_font(11), fg_color=THEME["bg_surface"])
        self.device_button.grid(row=0, column=2, padx=6)
        self.status_label = ctk.CTkLabel(header, text="Ready.", text_color=THEME["accent_gold"], font=ui_font(10))
        self.status_label.grid(row=0, column=3, sticky="e", padx=8)
        ctk.CTkButton(header, text="Couch", command=lambda: self.switch_surface_mode("couch"), width=72).grid(row=0, column=4, padx=3)
        ctk.CTkButton(header, text="Library", command=lambda: self.switch_surface_mode("library"), width=72).grid(row=0, column=5, padx=3)
        ctk.CTkButton(header, text="↻", command=self.detect_device_async, width=34).grid(row=0, column=6, padx=3)
        ctk.CTkButton(header, text="⚙", command=self.open_global_settings_modal, width=34).grid(row=0, column=7, padx=3)
        ctk.CTkButton(header, text="✕", command=self._quit, width=34, fg_color="#5B1824").grid(row=0, column=8, padx=(3, 14))
        self.workspace = ctk.CTkFrame(self, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.workspace.grid(row=1, column=0, sticky="nsew")
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(0, weight=1)
        self.couch_view = CouchView(self.workspace, self)
        self.couch_view.grid(row=0, column=0, sticky="nsew")
        self.library_view = LibraryView(self.workspace, self)
        self.library_view.grid(row=0, column=0, sticky="nsew")
        footer = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=THEME["bg_hud"])
        footer.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(footer, text="[D-Pad / Arrows] Navigate     [A / Enter] Launch     [LB/RB / Tab] Switch views     [F11] Window frame", text_color=THEME["text_secondary"], font=ui_font(10)).pack(side="left", padx=18, pady=6)

    def get_cfg(self, key):
        return self.data["config"].get(key, DEFAULT_CONFIG.get(key))

    def save_data(self):
        save_data(self.data_file, self.data)

    def get_or_create_profile(self, package, name=""):
        if package not in self.data["apps"]:
            self.data["apps"][package] = {**DEFAULT_APP_PROFILE, "display_name": name,
                "encoder": self.android.device_info.recommended_encoder, "input_mode": self.android.device_info.recommended_input}
        return self.data["apps"][package]

    def run_worker(self, work, on_result, on_error=None):
        def worker():
            try: result = work()
            except Exception as exc:
                self._results.put((on_error, exc))
            else: self._results.put((on_result, result))
        threading.Thread(target=worker, daemon=True).start()

    def _drain_results(self):
        try:
            while True:
                callback, value = self._results.get_nowait()
                if callback: callback(value)
        except queue.Empty: pass
        if self.winfo_exists(): self.after(20, self._drain_results)

    def find_art_path(self, package):
        for suffix in ("_poster.png", "_hero.png", "_icon.png", "_sgdb_icon.png"):
            path = self.cache_dir / f"{package}{suffix}"
            if path.exists(): return path
        return None

    def get_visible_entries(self):
        query = self.library_view.search_var.get().lower().strip()
        favorites_only = self.surface_mode == "couch" or self.library_filter == "favorites"
        if favorites_only:
            entries = []
            for package, profile in self.data["apps"].items():
                if profile.get("pinned"):
                    name = profile.get("display_name") or package.split(".")[-1].capitalize()
                    entries.append({"name": name, "package": package, "last_played": profile.get("last_played", 0)})
            entries.sort(key=lambda item: (-item["last_played"], item["name"].lower()))
        else:
            entries = [{"name": "Android Full Screen", "package": "__ANDROID_HOME__"}, *self.device_apps_cache]
        if query:
            entries = [item for item in entries if query in item["name"].lower() or query in item["package"].lower()]
        return entries

    def refresh_views(self):
        self.visible_apps = self.get_visible_entries()
        if self.visible_apps: self.focused_index = min(max(0, self.focused_index), len(self.visible_apps)-1)
        else: self.focused_index = 0
        self.couch_view.render(self.visible_apps, self.focused_index)
        self.library_view.render(self.visible_apps, self.focused_index)

    def set_focus(self, index):
        if not self.visible_apps: return
        self.focused_index = max(0, min(index, len(self.visible_apps)-1))
        self.refresh_views()

    def set_library_filter(self, value):
        self.library_filter = value
        self.refresh_views()

    def set_library_layout(self, value):
        self.library_layout = value
        self.data["config"]["library_layout"] = value
        self.save_data()
        self.refresh_views()

    def switch_surface_mode(self, mode):
        self.surface_mode = mode
        if mode == "couch":
            self.library_view.grid_remove()
            self.couch_view.grid(row=0, column=0, sticky="nsew")
        else:
            self.couch_view.grid_remove()
            self.library_view.grid(row=0, column=0, sticky="nsew")
            if not self.device_apps_cache and self.android.conn_flag: self.fetch_apps_async()
        self.refresh_views()

    def _bind_keys(self):
        self.bind("<Left>", lambda e: self._move(-1))
        self.bind("<Right>", lambda e: self._move(1))
        self.bind("<Up>", lambda e: self._move(-1))
        self.bind("<Down>", lambda e: self._move(1))
        self.bind("<Return>", lambda e: self.launch_focused_app())
        self.bind("<Tab>", lambda e: self.switch_surface_mode("library" if self.surface_mode == "couch" else "couch"))
        self.bind("<F11>", lambda e: self.toggle_window_chrome())

    def _move(self, delta):
        if not self.in_game_session: self.set_focus(self.focused_index + delta)

    def _on_gamepad_event(self, action):
        if self.in_game_session: return
        self._results.put((lambda value: self._handle_gamepad(value), action))

    def _handle_gamepad(self, action):
        if self.in_game_session: return
        if action in ("LEFT", "UP"): self._move(-1)
        elif action in ("RIGHT", "DOWN"): self._move(1)
        elif action == "A": self.launch_focused_app()
        elif action in ("LB", "RB"): self.switch_surface_mode("library" if self.surface_mode == "couch" else "couch")
        elif action == "BACK": self.toggle_window_chrome()

    def select_and_launch(self, index):
        self.focused_index = index
        self.launch_focused_app()

    def toggle_pin_index(self, index):
        self.focused_index = index
        self.toggle_pin_focused_app()

    def tune_index(self, index):
        self.focused_index = index
        self.open_focused_game_modal()

    def toggle_pin_focused_app(self):
        if not self.visible_apps: return
        app = self.visible_apps[self.focused_index]
        profile = self.get_or_create_profile(app["package"], app["name"])
        profile["pinned"] = not profile.get("pinned", False)
        self.save_data()
        self.refresh_views()

    def launch_focused_app(self):
        if self.in_game_session or not self.visible_apps: return
        if not self.android.conn_flag:
            self.open_connection_modal()
            return
        item = self.visible_apps[self.focused_index]
        package = item["package"]
        profile = dict(self.get_or_create_profile(package, item["name"]))
        config = dict(self.data["config"])
        preset = DISPLAY_PRESETS.get(config.get("active_display_preset"), {}) if config.get("follow_display_preset") else {}
        resolution = preset.get("resolution", profile.get("resolution", "1368x912"))
        dpi = preset.get("dpi", profile.get("dpi", "160"))
        bitrate = profile.get("usb_bitrate", "16M") if self.android.conn_flag == "-d" else profile.get("wifi_bitrate", "10M")
        command = build_scrcpy_cmd(scrcpy_exe=self.android.scrcpy_exe, adb_flag=self.android.conn_flag,
            app_name=package.split(".")[-1], profile=profile, config=config,
            source_mode="android_home" if package == "__ANDROID_HOME__" else package,
            resolution=resolution, dpi=dpi, bitrate=bitrate, soc_vendor=self.android.device_info.soc_vendor)
        self.in_game_session = True
        self.controller.set_paused(True)
        self.handoff_overlay.show(f"SCREEN+ HANDOFF • {item['name'].upper()}", f"{self.android.device_info.model} → {resolution} @ {profile.get('fps', '40')} FPS")
        self.runner.scrcpy_dir = self.get_cfg("scrcpy_dir")
        self.runner.shaderglass_exe = self.get_cfg("shaderglass_exe")
        self.runner.default_sgp = self.get_cfg("default_sgp")
        self.runner.start(command, package=package, app_name=item["name"], profile=profile,
            on_handoff_ready=lambda: self._results.put((self._handoff_ready, None)),
            on_session_end=lambda: self._results.put((self._session_ended, None)),
            on_status=lambda text: self._results.put((self._set_status, text)))

    def _handoff_ready(self, _value=None):
        self.handoff_overlay.hide()
        if self.get_cfg("borderless_mode"): self.withdraw()
        else: self.iconify()

    def _session_ended(self, _value=None):
        self.in_game_session = False
        self.deiconify()
        self.apply_window_chrome()
        self.lift()
        self.focus_force()
        self.handoff_overlay.hide()
        self.controller.set_paused(False)

    def _set_status(self, text): self.status_label.configure(text=text)

    def detect_device_async(self, mode="auto"):
        def done(connected):
            if connected:
                self.device_button.configure(text=f"● {self.android.device_info.model} • {self.android.conn_type}", text_color=THEME["status_ok"])
                if self.surface_mode == "library": self.fetch_apps_async()
            else: self.device_button.configure(text="● Connect Phone", text_color=THEME["status_err"])
        self.run_worker(lambda: self.android.detect_connection(mode), done,
                        lambda exc: self._set_status(f"Connection error: {exc}"))

    def fetch_apps_async(self):
        self.run_worker(self.android.fetch_all_device_apps, self._apps_loaded,
                        lambda exc: self._set_status(f"Scan failed: {exc}"))

    def _apps_loaded(self, apps):
        self.device_apps_cache = apps
        self.refresh_views()
        self._set_status(f"Found {len(apps)} phone apps")

    def crawl_profile_async(self, package, title, callback):
        api_key = self.get_cfg("steamgriddb_api_key") or ""
        crawler = GameMetadataCrawler(api_key, cache_dir=self.cache_dir)
        self.run_worker(lambda: crawler.fetch_metadata(package, title),
                        lambda result: self._apply_metadata(result, package, callback),
                        lambda exc: self._set_status(f"Metadata error: {exc}"))

    def _apply_metadata(self, result: MetadataResult, package, callback):
        profile = self.get_or_create_profile(package)
        if result.description: profile["description"] = result.description
        if result.github_info:
            profile["github_info"], profile["github_url"] = result.github_info, result.github_url
        if result.sgdb_game_id is not None: profile["sgdb_game_id"] = result.sgdb_game_id
        self.save_data()
        self.art_cache.invalidate(package)
        callback(result)
        self.refresh_views()

    def open_connection_modal(self): ConnectionBridgeModal(self)

    def open_focused_game_modal(self):
        if self.visible_apps:
            item = self.visible_apps[self.focused_index]
            GameConfigModal(self, item, self.get_or_create_profile(item["package"], item["name"]))

    def open_global_settings_modal(self): GlobalSettingsModal(self)

    def apply_window_chrome(self):
        if self.get_cfg("borderless_mode"):
            self.overrideredirect(True)
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        else:
            self.overrideredirect(False)
            self.geometry("1280x800")
            self.minsize(1000, 650)

    def toggle_window_chrome(self):
        if self.in_game_session: return
        self.data["config"]["borderless_mode"] = not self.get_cfg("borderless_mode")
        self.save_data()
        self.apply_window_chrome()

    def _quit(self):
        self.controller.stop()
        self.runner.stop()
        self.destroy()
