"""Playback status and current-frame visibility regressions."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow


APPLICATION = QApplication.instance() or QApplication([])


def service_for(tmp_path) -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", "en")
    return ShortcutSettingsService(settings)


def status(window: MainWindow) -> str:
    return window.timeline.playback_status_label.text()


def test_status_starts_stopped_and_tracks_playback(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    assert status(window) == "Stopped · Frame 1 / 1 · 12 FPS"
    window.set_playing(True)
    assert status(window) == "Playing · Frame 1 / 1 · 12 FPS"
    assert window.timeline.play_button.text() == "■"
    window.set_playing(False)
    assert status(window) == "Stopped · Frame 1 / 1 · 12 FPS"
    assert window.timeline.play_button.text() == "▶"
    window.close()


def test_status_tracks_frames_count_selection_and_fps(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.add_frame()
    assert status(window) == "Stopped · Frame 2 / 2 · 12 FPS"
    window.select_frame(0)
    assert status(window) == "Stopped · Frame 1 / 2 · 12 FPS"
    window.set_fps(24)
    assert status(window) == "Stopped · Frame 1 / 2 · 24 FPS"
    window.duplicate_frame()
    assert status(window) == "Stopped · Frame 2 / 3 · 24 FPS"
    window.delete_frame()
    assert status(window) == "Stopped · Frame 2 / 2 · 24 FPS"
    window.dirty = False
    window.close()


def test_playback_advance_moves_status_and_column_highlight(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.project.add_frame()
    window._refresh_all()
    window.set_playing(True)
    window._advance_playback()
    assert status(window) == "Playing · Frame 2 / 2 · 12 FPS"
    first = window.timeline.table.item(0, 0).background().color()
    second = window.timeline.table.item(0, 1).background().color()
    assert first != second
    assert second.name() == "#34495e"
    window.set_playing(False)
    window.close()


def test_non_loop_end_stops_status(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.project.add_frame()
    window.project.loop = False
    window.frame_index = 1
    window._refresh_all()
    window.set_playing(True)
    window._advance_playback()
    assert status(window) == "Stopped · Frame 2 / 2 · 12 FPS"
    assert not window.play_action.isChecked()
    window.close()


def test_playback_test_project_status(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.create_playback_test()
    assert status(window) == "Stopped · Frame 1 / 8 · 12 FPS"
    assert window.playback_test_action.statusTip().startswith("Create an 8-frame")
    window.dirty = False
    window.close()
