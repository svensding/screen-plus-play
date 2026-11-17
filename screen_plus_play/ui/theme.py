from __future__ import annotations

from io import BytesIO

import customtkinter as ctk
from PIL import Image, ImageDraw

THEME = {
    "bg_canvas": "#0E1015", "bg_hud": "#13161E", "bg_surface": "#181C26",
    "bg_elevated": "#212734", "border_subtle": "#2A3140", "accent_gold": "#FFD43B",
    "accent_amber": "#F59F00", "accent_crimson": "#C10048", "text_primary": "#F4F5F7",
    "text_secondary": "#9CA3AF", "text_on_gold": "#0E1015", "status_ok": "#34D399",
    "status_err": "#F87171", "gh_badge": "#38BDF8",
}
FONT_FAMILY = "Google Sans Code"


def ui_font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def render_brand_logo(height: int = 32) -> Image.Image:
    """Render the overlapping display, portrait and D-pad mark as a supersampled PIL image."""
    scale, width, body_h = 6, 40, 35
    w, h = width * scale, body_h * scale
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (w, 25 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    for y in range(25 * scale):
        t = y / (25 * scale)
        color = (int(193 * (1-t) + 255*t), int(0 * (1-t) + 160*t), int(72 * (1-t)), 255)
        draw.line((0, y, w, y), fill=color)
    mask = Image.new("L", gradient.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, w-1, 25*scale-1), radius=3*scale, fill=255)
    md.rectangle((4*scale, 4*scale, 36*scale, 21*scale), fill=0)
    md.rectangle((13*scale, 21*scale, 31*scale, 27*scale), fill=0)
    image.paste(gradient, (0, 0), mask)
    pd = ImageDraw.Draw(image)
    gold = (255, 212, 59, 255)
    pd.rounded_rectangle((14*scale, 11*scale, 27*scale, h-1), radius=3*scale, outline=gold, width=3*scale)
    cx, cy = 25*scale, 23*scale
    pd.rounded_rectangle((cx-2*scale, cy-6*scale, cx+2*scale, cy+6*scale), radius=scale, fill=gold)
    pd.rounded_rectangle((cx-6*scale, cy-2*scale, cx+6*scale, cy+2*scale), radius=scale, fill=gold)
    return image.resize((round(height*w/h), height), Image.Resampling.LANCZOS)
