from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .theme import THEME


def fit_image(image: Image.Image, size: tuple[int, int], centering=(0.5, 0.5)) -> Image.Image:
    return ImageOps.fit(image.convert("RGBA"), size, method=Image.Resampling.LANCZOS, centering=centering)


def build_card_image(art_path: Path | None, title: str, package: str, size: tuple[int, int], profile: dict) -> Image.Image:
    width, height = size
    if art_path and art_path.exists():
        try:
            base = fit_image(Image.open(art_path), size)
        except (OSError, ValueError):
            base = None
    else:
        base = None
    if base is None:
        base = Image.new("RGBA", size, (24, 28, 38, 255))
        draw = ImageDraw.Draw(base)
        radius = int(min(width, height) * 0.2)
        cx, cy = width // 2, int(height * 0.38)
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=(33, 39, 52, 255))
        draw.text((cx-5, cy-7), "⇄" if package == "__ANDROID_HOME__" else title[:1].upper(), fill=(255, 212, 59, 255))
        draw.text((12, int(height * 0.68)), title[:18], fill=(244, 245, 247, 255))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, height-30, width, height), fill=(14, 16, 21, 215))
    labels = []
    if profile.get("turn_screen_off"): labels.append("CONSOLE")
    if profile.get("use_shaderglass"): labels.append("SHADER")
    draw.text((10, height-21), " • ".join(labels) if labels else f"{profile.get('fps', '40')}FPS", fill=(255, 212, 59, 255))
    return Image.alpha_composite(base, overlay)


def build_blurred_backdrop(art_path: Path | None, size: tuple[int, int]) -> Image.Image:
    width, height = size
    background = Image.new("RGBA", size, (14, 16, 21, 255))
    if art_path and art_path.exists():
        try:
            source = Image.open(art_path).convert("RGBA")
            small_size = (max(240, width // 3), max(135, height // 3))
            fitted = ImageOps.fit(source, small_size, method=Image.Resampling.BILINEAR, centering=(0.5, 0.3))
            blurred = fitted.filter(ImageFilter.GaussianBlur(radius=8)).resize(size, Image.Resampling.BILINEAR)
            tint = Image.new("RGBA", size, (14, 16, 21, 130))
            background = Image.alpha_composite(blurred, tint)
        except (OSError, ValueError):
            pass
    fade = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(fade)
    fade_width = int(width * 0.68)
    for x in range(0, fade_width, 4):
        alpha = int(170 * (1 - x / max(1, fade_width)))
        draw.rectangle((x, 0, x+3, height), fill=(14, 16, 21, alpha))
    return Image.alpha_composite(background, fade).convert("RGB")


class ArtworkCache:
    """Bounded UI-thread cache; construction of CTkImage must happen on the Tk thread."""
    def __init__(self, max_items: int = 90, backdrop_items: int = 20):
        self.cards: OrderedDict[tuple, ctk.CTkImage] = OrderedDict()
        self.backdrops: OrderedDict[tuple, ctk.CTkImage] = OrderedDict()
        self.max_items, self.backdrop_items = max_items, backdrop_items

    @staticmethod
    def _remember(cache: OrderedDict, key, value, limit: int):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)
        return value

    def card(self, key: tuple, image: Image.Image) -> ctk.CTkImage:
        cached = self.cards.get(key)
        if cached is not None:
            self.cards.move_to_end(key)
            return cached
        return self._remember(self.cards, key, ctk.CTkImage(light_image=image, dark_image=image, size=image.size), self.max_items)

    def backdrop(self, key: tuple, image: Image.Image) -> ctk.CTkImage:
        cached = self.backdrops.get(key)
        if cached is not None:
            self.backdrops.move_to_end(key)
            return cached
        return self._remember(self.backdrops, key, ctk.CTkImage(light_image=image, dark_image=image, size=image.size), self.backdrop_items)

    def invalidate(self, package: str) -> None:
        for cache in (self.cards, self.backdrops):
            for key in list(cache):
                if package in key:
                    del cache[key]
