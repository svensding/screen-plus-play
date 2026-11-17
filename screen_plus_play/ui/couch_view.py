from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from PIL import Image

from .artwork import ArtworkCache, build_blurred_backdrop, build_card_image
from .theme import THEME, ui_font


class CouchView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.stage = ctk.CTkFrame(self, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.stage.grid(row=0, column=0, sticky="nsew")
        self.stage.bind("<Configure>", self._on_resize)
        self.backdrop = ctk.CTkLabel(self.stage, text="", fg_color=THEME["bg_canvas"])
        self.backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.backdrop.lower()
        self._resize_job = None
        self._backdrop_request = 0
        self._backdrop_package = None

        details = ctk.CTkFrame(self.stage, fg_color="transparent")
        details.place(x=48, rely=0.48, anchor="w")
        self.badge = ctk.CTkLabel(details, text="★ YOUR SHELF", font=ui_font(11, "bold"), text_color=THEME["accent_gold"])
        self.badge.pack(anchor="w")
        self.title = ctk.CTkLabel(details, text="Welcome to Screen+Play", font=ui_font(38, "bold"), text_color=THEME["text_primary"], anchor="w")
        self.title.pack(anchor="w", pady=3)
        self.description = ctk.CTkLabel(details, text="Connect your phone and add apps to your shelf.", font=ui_font(13), text_color="#E5E7EB", wraplength=680, justify="left", anchor="w")
        self.description.pack(anchor="w", pady=3)
        self.github = ctk.CTkLabel(details, text="", font=ui_font(11, "bold"), text_color=THEME["gh_badge"], wraplength=680, justify="left")
        self.github.pack(anchor="w", pady=3)
        self.meta = ctk.CTkLabel(details, text="", font=ui_font(12, "bold"), text_color=THEME["accent_gold"])
        self.meta.pack(anchor="w", pady=(2, 12))
        buttons = ctk.CTkFrame(details, fg_color="transparent")
        buttons.pack(anchor="w")
        self.play_button = ctk.CTkButton(buttons, text="▶  PLAY ON BIG SCREEN", command=app.launch_focused_app, fg_color=THEME["accent_gold"], hover_color=THEME["accent_amber"], text_color=THEME["text_on_gold"], font=ui_font(13, "bold"), height=44)
        self.resume_button = ctk.CTkButton(buttons, text="⇄  Resume Active Phone Session", command=app.launch_focused_app, fg_color=THEME["bg_surface"], border_width=1, border_color=THEME["accent_gold"], text_color=THEME["accent_gold"], font=ui_font(12, "bold"), height=44)
        self.tune_button = ctk.CTkButton(buttons, text="⚙ Tune", command=app.open_focused_game_modal, fg_color=THEME["bg_surface"], font=ui_font(12), height=44)
        self.pin_button = ctk.CTkButton(buttons, text="☆ Shelf", command=app.toggle_pin_focused_app, fg_color=THEME["bg_surface"], font=ui_font(12), height=44)

        shelf = ctk.CTkFrame(self, height=290, corner_radius=0, fg_color="#0A0C10")
        shelf.grid(row=1, column=0, sticky="ew")
        shelf.grid_propagate(False)
        shelf.grid_columnconfigure(0, weight=1)
        shelf.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(shelf, text="YOUR SHELF  •  MOVE OFF YOUR PHONE SCREEN", font=ui_font(11, "bold"), text_color=THEME["text_secondary"]).grid(row=0, column=0, sticky="w", padx=40, pady=(8, 0))
        self.carousel = ctk.CTkScrollableFrame(shelf, orientation="horizontal", fg_color="transparent")
        self.carousel.grid(row=1, column=0, sticky="nsew", padx=26, pady=4)
        self.tiles: list[tuple[ctk.CTkFrame, ctk.CTkLabel]] = []
        self.signature: tuple[str, ...] | None = None

    def _art_path(self, package: str, wide=False) -> Path | None:
        suffixes = ("_hero.png", "_poster.png", "_icon.png", "_sgdb_icon.png") if wide else ("_poster.png", "_hero.png", "_icon.png", "_sgdb_icon.png")
        for suffix in suffixes:
            path = self.app.cache_dir / f"{package}{suffix}"
            if path.exists(): return path
        return None

    def _profile(self, package):
        from screen_plus_play.core.config import DEFAULT_APP_PROFILE
        return self.app.data["apps"].get(package, DEFAULT_APP_PROFILE)

    def _card(self, app, height):
        package = app["package"]
        profile = self._profile(package)
        path = self._art_path(package)
        aspect = 2/3
        if path:
            try:
                with Image.open(path) as raw: aspect = raw.width / max(1, raw.height)
            except OSError: pass
        width = max(145, min(320, int(height * aspect)))
        key = (package, width, height, profile.get("fps"), profile.get("use_shaderglass"), profile.get("turn_screen_off"), str(path.stat().st_mtime_ns) if path and path.exists() else "")
        image = self.app.art_cache.cards.get(key)
        if image is None:
            pil = build_card_image(path, app["name"], package, (width, height), profile)
            image = self.app.art_cache.card(key, pil)
        return image, width, height

    def render(self, entries, focused: int):
        signature = tuple(item["package"] for item in entries)
        if signature != self.signature:
            for child in self.carousel.winfo_children(): child.destroy()
            self.tiles.clear()
            self.signature = signature
            for index, entry in enumerate(entries):
                tile = ctk.CTkFrame(self.carousel, corner_radius=10, fg_color=THEME["border_subtle"])
                tile.pack(side="left", padx=9, pady=8)
                label = ctk.CTkLabel(tile, text="", cursor="hand2")
                label.place(x=3, y=3)
                label.bind("<Button-1>", lambda event, i=index: self.app.set_focus(i))
                self.tiles.append((tile, label))
        for index, entry in enumerate(entries):
            height = 220 if index == focused else 190
            image, width, height = self._card(entry, height)
            tile, label = self.tiles[index]
            tile.configure(width=width+6, height=height+6, fg_color=THEME["accent_gold"] if index == focused else THEME["border_subtle"])
            tile.pack_propagate(False)
            tile.pack_configure(pady=(4 if index == focused else 18, 5))
            label.configure(image=image, width=width, height=height)
        self._render_stage(entries, focused)

    def _render_stage(self, entries, focused):
        for button in (self.play_button, self.resume_button, self.tune_button, self.pin_button): button.pack_forget()
        if not entries:
            self.title.configure(text="Shelf Empty")
            self.description.configure(text="Open Library & Apps to browse and shelf games.")
            self.github.configure(text="")
            self.meta.configure(text="")
            return
        app = entries[focused]
        profile = self._profile(app["package"])
        package = app["package"]
        is_home = package == "__ANDROID_HOME__"
        self.title.configure(text=profile.get("display_name") or app["name"])
        self.description.configure(text=profile.get("description", ""))
        self.github.configure(text=f"⌥ {profile.get('github_info', '')}" if profile.get("github_info") else "")
        self.badge.configure(text="⇄ HANDOFF • ACTIVE PHONE SCREEN" if is_home else ("★ SHELVED GAME" if profile.get("pinned") else "PHONE GAME"))
        self.meta.configure(text=f"{profile.get('resolution', '1368x912')} • {profile.get('fps', '40')} FPS • {'Console' if profile.get('turn_screen_off') else 'Dual-Screen'}")
        (self.resume_button if is_home else self.play_button).pack(side="left", padx=(0, 8))
        self.tune_button.pack(side="left", padx=5)
        self.pin_button.configure(text="★ Shelved" if profile.get("pinned") else "☆ Shelf")
        self.pin_button.pack(side="left", padx=5)
        self._request_backdrop(package)

    def _request_backdrop(self, package):
        width, height = max(800, self.stage.winfo_width()), max(320, self.stage.winfo_height())
        key = (package, width, height)
        cached = self.app.art_cache.backdrops.get(key)
        if cached:
            self.backdrop.configure(image=cached)
            self.backdrop.image = cached
            self.backdrop.lower()
            return
        if self._backdrop_package == key: return
        self._backdrop_package = key
        self._backdrop_request += 1
        request_id = self._backdrop_request
        path = self._art_path(package, wide=True)
        # Worker returns a pure PIL image. CTkImage/widget work remains on the UI thread.
        self.app.run_worker(lambda: build_blurred_backdrop(path, (width, height)),
            lambda pil: self._apply_backdrop(request_id, key, pil))

    def _apply_backdrop(self, request_id, key, pil):
        if request_id != self._backdrop_request: return
        image = self.app.art_cache.backdrop(key, pil)
        self.backdrop.configure(image=image)
        self.backdrop.image = image
        self.backdrop.lower()

    def _on_resize(self, _event):
        if self._resize_job: self.after_cancel(self._resize_job)
        self._resize_job = self.after(180, self._apply_resize)

    def _apply_resize(self):
        self._resize_job = None
        if self.app.visible_apps:
            self._request_backdrop(self.app.visible_apps[self.app.focused_index]["package"])
