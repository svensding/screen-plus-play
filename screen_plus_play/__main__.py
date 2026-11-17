from __future__ import annotations

from screen_plus_play.ui.app import ScreenPlusPlayApp
from screen_plus_play.ui.hotkeys import hotkeys_allowed

# Install the focused-input/modal guard for the normal package entry point.
ScreenPlusPlayApp._hotkeys_allowed = hotkeys_allowed


def main() -> None:
    app = ScreenPlusPlayApp()
    app.mainloop()


if __name__ == "__main__":
    main()
