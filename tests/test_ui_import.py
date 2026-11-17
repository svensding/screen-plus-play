from __future__ import annotations

import customtkinter as ctk
from tkinter import filedialog

from screen_plus_play.core.config import DEFAULT_APP_PROFILE, DISPLAY_PRESETS
from .theme import THEME, ui_font


def test_ui_modules_import_without_creating_a_window():
    """Import smoke test intentionally avoids CTk() so CI needs no display server or phone."""
    from screen_plus_play.ui.app import ScreenPlusPlayApp
    from screen_plus_play.ui.artwork import ArtworkCache, build_blurred_backdrop, build_card_image
    from screen_plus_play.ui.couch_view import CouchView
    from screen_plus_play.ui.library_view import LibraryView
    from screen_plus_play.ui.modals import ConnectionBridgeModal, GameConfigModal, GlobalSettingsModal
    from screen_plus_play.ui.overlays import HandoffOverlay, StartupOverlay

    assert ScreenPlusPlayApp and ArtworkCache and build_blurred_backdrop and build_card_image
    assert CouchView and LibraryView and ConnectionBridgeModal and GameConfigModal and GlobalSettingsModal
    assert HandoffOverlay and StartupOverlay
