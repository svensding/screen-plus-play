from __future__ import annotations

import customtkinter as ctk

from .theme import THEME, ui_font


class HandoffOverlay(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.48, anchor="center")
        self.title_label = ctk.CTkLabel(center, text="SCREEN+ HANDOFF", font=ui_font(22, "bold"), text_color=THEME["accent_gold"])
        self.title_label.pack()
        self.subtitle = ctk.CTkLabel(center, text="Initializing virtual display...", font=ui_font(13), text_color=THEME["text_secondary"])
        self.subtitle.pack(pady=(8, 18))
        self.progress = ctk.CTkProgressBar(center, width=320, mode="indeterminate", progress_color=THEME["accent_gold"])
        self.progress.pack()

    def show(self, title: str, subtitle: str) -> None:
        self.title_label.configure(text=title)
        self.subtitle.configure(text=subtitle)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.progress.start()

    def hide(self) -> None:
        self.progress.stop()
        self.place_forget()


class StartupOverlay(ctk.CTkFrame):
    def __init__(self, parent, logo):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.48, anchor="center")
        ctk.CTkLabel(center, text="", image=logo).pack(pady=(0, 12))
        ctk.CTkLabel(center, text="SCREEN+PLAY", font=ui_font(28, "bold"), text_color=THEME["text_primary"]).pack()
        ctk.CTkLabel(center, text="Move off your phone screen, keep your session going.", font=ui_font(13), text_color=THEME["text_secondary"]).pack(pady=10)
        self.progress = ctk.CTkProgressBar(center, width=280, progress_color=THEME["accent_gold"])
        self.progress.pack()
        self.progress.set(0.35)

    def show_briefly(self, callback) -> None:
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.after(500, self.place_forget)
