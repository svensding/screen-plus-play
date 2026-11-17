from __future__ import annotations


def hotkeys_allowed(app, event=None, ctk_module=None) -> bool:
    """Return whether global launcher shortcuts should handle this key event."""
    if app.in_game_session:
        return False

    if ctk_module is None:
        import customtkinter as ctk_module

    for widget in app.winfo_children():
        if isinstance(widget, ctk_module.CTkToplevel):
            try:
                if widget.winfo_exists():
                    return False
            except Exception:
                # A widget being destroyed is not an active modal.
                continue

    event_widget = getattr(event, "widget", None)
    if isinstance(event_widget, (ctk_module.CTkEntry, ctk_module.CTkTextbox, ctk_module.CTkComboBox)):
        return False

    try:
        focused = app.focus_get()
    except Exception:
        focused = None
    focus_name = str(focused).lower() if focused is not None else ""
    if "combobox" in focus_name or "entry" in focus_name:
        return False

    return True
