from types import SimpleNamespace

from screen_plus_play.ui.hotkeys import hotkeys_allowed


class FakeWidget:
    def __init__(self, exists=True):
        self.exists = exists

    def winfo_exists(self):
        return self.exists


class FakeToplevel(FakeWidget):
    pass


class FakeEntry(FakeWidget):
    pass


class FakeTextbox(FakeWidget):
    pass


class FakeComboBox(FakeWidget):
    pass


class FakeCTk:
    CTkToplevel = FakeToplevel
    CTkEntry = FakeEntry
    CTkTextbox = FakeTextbox
    CTkComboBox = FakeComboBox


def fake_app(children=(), focus=None, in_game=False):
    app = SimpleNamespace(
        in_game_session=in_game,
        winfo_children=lambda: list(children),
        focus_get=lambda: focus,
    )
    return app


def test_hotkeys_blocked_while_modal_exists():
    assert not hotkeys_allowed(fake_app([FakeToplevel()]), ctk_module=FakeCTk)


def test_hotkeys_blocked_for_combo_and_entry_focus_names():
    assert not hotkeys_allowed(fake_app(focus=".!ctkcombobox.!entry"), ctk_module=FakeCTk)
    assert not hotkeys_allowed(fake_app(focus=".!ctkentry"), ctk_module=FakeCTk)


def test_hotkeys_allowed_for_normal_focus_and_blocked_in_game():
    assert hotkeys_allowed(fake_app(focus=".!ctklabel"), ctk_module=FakeCTk)
    assert not hotkeys_allowed(fake_app(focus=".!ctklabel", in_game=True), ctk_module=FakeCTk)
