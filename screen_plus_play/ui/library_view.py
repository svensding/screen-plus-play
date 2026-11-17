from __future__ import annotations

import customtkinter as ctk
from PIL import Image

from .artwork import build_card_image
from .theme import THEME, ui_font


class LibraryView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(self, fg_color=THEME["bg_surface"], corner_radius=10, height=54)
        bar.grid(row=0, column=0, sticky="ew", padx=22, pady=(14, 8))
        bar.grid_columnconfigure(2, weight=1)
        self.filter_var = ctk.StringVar(value="all")
        ctk.CTkButton(bar, text="📱 All Phone Apps", command=lambda: app.set_library_filter("all"), font=ui_font(11)).grid(row=0, column=0, padx=8, pady=8)
        ctk.CTkButton(bar, text="★ Shelved Only", command=lambda: app.set_library_filter("favorites"), font=ui_font(11)).grid(row=0, column=1, padx=4, pady=8)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: app.refresh_views())
        ctk.CTkEntry(bar, textvariable=self.search_var, placeholder_text="Search apps and package names...").grid(row=0, column=2, sticky="ew", padx=8, pady=8)
        self.layout = ctk.StringVar(value=app.library_layout)
        for col, (name, value) in enumerate((("Poster Wall", "poster_wall"), ("Detail List", "detail_list"), ("Showcase Split", "showcase_split")), 3):
            ctk.CTkButton(bar, text=name, width=105, command=lambda v=value: app.set_library_layout(v), font=ui_font(10)).grid(row=0, column=col, padx=2, pady=8)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 12))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def render(self, entries, focused):
        for child in self.content.winfo_children(): child.destroy()
        if not entries:
            ctk.CTkLabel(self.content, text="No apps found. Connect a phone and refresh the device list.", text_color=THEME["text_secondary"], font=ui_font(14)).pack(pady=100)
            return
        layout = self.app.library_layout
        if layout == "detail_list": self._detail_list(entries, focused)
        elif layout == "showcase_split": self._showcase(entries, focused)
        else: self._poster_wall(entries, focused)

    def _profile(self, pkg):
        from screen_plus_play.core.config import DEFAULT_APP_PROFILE
        return self.app.data["apps"].get(pkg, DEFAULT_APP_PROFILE)

    def _card(self, item, size=(160, 225)):
        pkg, profile = item["package"], self._profile(item["package"])
        path = self.app.find_art_path(pkg)
        pil = build_card_image(path, item["name"], pkg, size, profile)
        key = ("lib", pkg, size, profile.get("fps"), profile.get("pinned"), profile.get("turn_screen_off"), profile.get("use_shaderglass"))
        return self.app.art_cache.card(key, pil)

    def _poster_wall(self, entries, focused):
        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        for index, item in enumerate(entries):
            profile = self._profile(item["package"])
            card = ctk.CTkFrame(scroll, fg_color=THEME["bg_surface"], border_width=2 if index == focused else 1,
                                border_color=THEME["accent_gold"] if index == focused else THEME["border_subtle"], corner_radius=10)
            card.pack(side="left", padx=7, pady=8)
            image = self._card(item)
            ctk.CTkLabel(card, text="", image=image, cursor="hand2").pack(padx=4, pady=4)
            ctk.CTkLabel(card, text=("★ " if profile.get("pinned") else "") + item["name"][:20], font=ui_font(11, "bold")).pack(padx=6, pady=(0, 5))
            ctk.CTkButton(card, text="Select / Launch", height=28, command=lambda i=index: self.app.select_and_launch(i)).pack(fill="x", padx=5, pady=(0, 5))

    def _detail_list(self, entries, focused):
        scroll = ctk.CTkScrollableFrame(self.content, fg_color=THEME["bg_surface"], corner_radius=10)
        scroll.grid(row=0, column=0, sticky="nsew")
        for index, item in enumerate(entries):
            profile = self._profile(item["package"])
            row = ctk.CTkFrame(scroll, fg_color=THEME["bg_elevated"] if index == focused else THEME["bg_canvas"], height=58, corner_radius=8)
            row.pack(fill="x", padx=8, pady=4)
            row.pack_propagate(False)
            ctk.CTkButton(row, text="★" if profile.get("pinned") else "☆", width=38, command=lambda i=index: self.app.toggle_pin_index(i)).pack(side="left", padx=7, pady=7)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="y", pady=5)
            ctk.CTkLabel(info, text=item["name"], font=ui_font(12, "bold")).pack(anchor="w")
            ctk.CTkLabel(info, text=item["package"], font=ui_font(10), text_color=THEME["text_secondary"]).pack(anchor="w")
            ctk.CTkLabel(row, text=f"{profile.get('fps', '40')} FPS • {'Console' if profile.get('turn_screen_off') else 'Dual'}", text_color=THEME["accent_gold"], font=ui_font(10)).pack(side="right", padx=12)
            ctk.CTkButton(row, text="⚙ Tune", width=76, command=lambda i=index: self.app.tune_index(i)).pack(side="right", padx=4)
            ctk.CTkButton(row, text="▶ Launch", width=84, fg_color=THEME["accent_gold"], text_color=THEME["text_on_gold"], command=lambda i=index: self.app.select_and_launch(i)).pack(side="right", padx=4)

    def _showcase(self, entries, focused):
        split = ctk.CTkFrame(self.content, fg_color="transparent")
        split.grid(row=0, column=0, sticky="nsew")
        split.grid_columnconfigure((0, 1), weight=1)
        split.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(split, fg_color=THEME["bg_surface"], corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        for i, item in enumerate(entries):
            profile = self._profile(item["package"])
            ctk.CTkButton(left, text=("★ " if profile.get("pinned") else "") + item["name"], anchor="w",
                          fg_color=THEME["accent_gold"] if i == focused else "transparent",
                          text_color=THEME["text_on_gold"] if i == focused else THEME["text_primary"],
                          command=lambda index=i: self.app.set_focus(index)).pack(fill="x", padx=6, pady=3)
        item = entries[focused]
        profile = self._profile(item["package"])
        right = ctk.CTkFrame(split, fg_color=THEME["bg_surface"], corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        art = self._card(item, (190, 260))
        ctk.CTkLabel(right, text="", image=art).pack(pady=(14, 8))
        ctk.CTkLabel(right, text=item["name"], font=ui_font(20, "bold")).pack()
        ctk.CTkLabel(right, text=item["package"], font=ui_font(10), text_color=THEME["text_secondary"]).pack(pady=3)
        description = profile.get("description") or "No Wikipedia snippet yet. Use Tune to fetch metadata."
        ctk.CTkLabel(right, text=description, wraplength=430, justify="center", font=ui_font(11)).pack(padx=20, pady=8)
        if profile.get("github_info"):
            ctk.CTkLabel(right, text=f"⌥ {profile['github_info']}", text_color=THEME["gh_badge"], wraplength=430, font=ui_font(10, "bold")).pack(padx=16, pady=5)
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.pack(pady=8)
        ctk.CTkButton(actions, text="▶ Launch", command=lambda: self.app.select_and_launch(focused), fg_color=THEME["accent_gold"], text_color=THEME["text_on_gold"]).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="⚙ Tune", command=lambda: self.app.tune_index(focused)).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="★ Shelf", command=lambda: self.app.toggle_pin_index(focused)).pack(side="left", padx=4)
