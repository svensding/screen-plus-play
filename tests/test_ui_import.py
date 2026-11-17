"""Import smoke test that does not create a Tk window or require a display/device."""


def test_ui_modules_import_without_creating_a_window():
    from screen_plus_play.ui.app import ScreenPlusPlayApp
    from screen_plus_play.ui.artwork import ArtworkCache, build_blurred_backdrop, build_card_image
    from screen_plus_play.ui.couch_view import CouchView
    from screen_plus_play.ui.library_view import LibraryView
    from screen_plus_play.ui.modals import ConnectionBridgeModal, GameConfigModal, GlobalSettingsModal
    from screen_plus_play.ui.overlays import HandoffOverlay, StartupOverlay

    assert all((
        ScreenPlusPlayApp,
        ArtworkCache,
        build_blurred_backdrop,
        build_card_image,
        CouchView,
        LibraryView,
        ConnectionBridgeModal,
        GameConfigModal,
        GlobalSettingsModal,
        HandoffOverlay,
        StartupOverlay,
    ))
