"""Offscreen tests for playback QAction, loop behavior, and sample replacement."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow


APPLICATION = QApplication.instance() or QApplication([])


def service_for(tmp_path) -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return ShortcutSettingsService(settings)


def focused_window(tmp_path) -> MainWindow:
    window = MainWindow(service_for(tmp_path))
    window.show()
    window.activateWindow()
    window.setFocus()
    APPLICATION.processEvents()
    return window


def test_enter_toggles_playback_once_and_synchronizes_button(tmp_path) -> None:
    window = focused_window(tmp_path)
    QTest.keyClick(window, Qt.Key.Key_Enter)
    APPLICATION.processEvents()
    assert window.play_timer.isActive()
    assert window.play_action.isChecked()
    assert window.timeline.play_button.text() == "■"

    QTest.keyClick(window, Qt.Key.Key_Enter)
    APPLICATION.processEvents()
    assert not window.play_timer.isActive()
    assert not window.play_action.isChecked()
    assert window.timeline.play_button.text() == "▶"
    window.close()


def test_play_button_uses_same_action_state(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.timeline.play_button.click()
    assert window.play_action.isChecked()
    assert window.play_timer.isActive()
    window.timeline.play_button.click()
    assert not window.play_action.isChecked()
    assert not window.play_timer.isActive()
    window.close()


def test_loop_wraps_and_non_loop_stops_at_last_frame(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.project.add_frame()
    window._refresh_all()
    window.frame_index = 1
    window.project.loop = True
    window._advance_playback()
    assert window.frame_index == 0

    window.frame_index = 1
    window.project.loop = False
    window.set_playing(True)
    window._advance_playback()
    assert window.frame_index == 1
    assert not window.play_timer.isActive()
    assert not window.play_action.isChecked()
    window.close()


def test_fps_change_updates_active_timer_interval(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.set_playing(True)
    window.set_fps(25)
    assert window.play_timer.interval() == 40
    window.set_playing(False)
    window.dirty = False
    window.close()


def test_modal_project_settings_blocks_main_enter_shortcut(tmp_path) -> None:
    window = focused_window(tmp_path)
    dialog = window.create_project_settings_dialog()
    dialog.open()
    APPLICATION.processEvents()
    QTest.keyClick(window, Qt.Key.Key_Enter)
    APPLICATION.processEvents()
    assert not window.play_timer.isActive()
    assert not window.play_action.isChecked()
    dialog.reject()
    window.close()


def test_playback_test_project_replacement_is_safe(tmp_path, monkeypatch) -> None:
    window = MainWindow(service_for(tmp_path))
    original = window.project
    window.dirty = True
    monkeypatch.setattr(window, "_confirm_discard", lambda: False)
    window.create_playback_test()
    assert window.project is original

    monkeypatch.setattr(window, "_confirm_discard", lambda: True)
    window.create_playback_test()
    assert window.project.name == "Playback Test"
    assert len(window.project.frames) == 8
    assert window.timeline.table.columnCount() == 8
    assert window.dirty
    window.dirty = False
    window.close()


def test_playback_test_frames_visibly_advance(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.create_playback_test()
    assert window.frame_index == 0
    window._advance_playback()
    assert window.frame_index == 1
    window.dirty = False
    window.close()


def test_timeline_has_no_large_title_but_keeps_controls(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    visible_text = [label.text() for label in window.timeline.findChildren(QLabel)]
    assert "Layer × Frame Timeline" not in visible_text
    assert window.timeline.table.rowCount() == 1
    assert window.timeline.table.columnCount() == 1
    assert window.timeline.play_button is not None
    window.close()
