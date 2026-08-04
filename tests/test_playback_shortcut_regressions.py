"""Actual-key-event regressions for focus-safe playback shortcuts."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QKeySequenceEdit,
    QLineEdit,
    QMessageBox,
)

from app.services.settings_service import ShortcutSettingsService
from app.shortcuts import DEFAULT_SHORTCUTS
from app.ui.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from app.ui.main_window import MainWindow
from app.ui.new_project_dialog import NewProjectDialog


APPLICATION = QApplication.instance() or QApplication([])


def service_for(tmp_path) -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", "en")
    return ShortcutSettingsService(settings)


def focused_window(tmp_path) -> MainWindow:
    window = MainWindow(service_for(tmp_path))
    window.show()
    window.activateWindow()
    window.canvas.setFocus()
    APPLICATION.processEvents()
    return window


def press(widget, key: Qt.Key, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(widget, key, modifiers)
    APPLICATION.processEvents()


def test_animation_menu_remains_empty_and_command_is_internal(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    assert window.animation_menu.title() == "Animation"
    assert window.animation_menu.actions() == []
    assert window.play_action.text() == "Play / Stop Animation"
    assert window.play_action.shortcut().isEmpty()
    assert "play_stop_animation" in window.shortcuts
    dialog = KeyboardShortcutsDialog(window.shortcuts)
    assert "play_stop_animation" in dialog.editors
    window.close()


def test_main_return_and_keypad_enter_each_toggle_once(tmp_path) -> None:
    window = focused_window(tmp_path)
    toggles: list[bool] = []
    window.play_action.toggled.connect(toggles.append)

    press(window.canvas, Qt.Key.Key_Return)
    assert toggles == [True]
    assert window.play_timer.isActive()
    press(window.canvas, Qt.Key.Key_Return)
    assert toggles == [True, False]
    assert not window.play_timer.isActive()

    press(window.canvas, Qt.Key.Key_Enter)
    assert toggles == [True, False, True]
    assert window.play_timer.isActive()
    press(window.canvas, Qt.Key.Key_Enter)
    assert toggles == [True, False, True, False]
    window.close()


def test_timeline_selection_focus_allows_return(tmp_path) -> None:
    window = focused_window(tmp_path)
    window.timeline.table.setFocus()
    APPLICATION.processEvents()
    press(window.timeline.table, Qt.Key.Key_Return)
    assert window.play_timer.isActive()
    window.set_playing(False)
    window.close()


def test_line_edit_spinbox_and_key_sequence_edit_block_return(tmp_path) -> None:
    window = focused_window(tmp_path)
    line_edit = QLineEdit(window.centralWidget())
    line_edit.show()
    line_edit.setFocus()
    APPLICATION.processEvents()
    press(line_edit, Qt.Key.Key_Return)
    assert not window.play_timer.isActive()

    window.timeline.fps_spin.setFocus()
    APPLICATION.processEvents()
    press(window.timeline.fps_spin, Qt.Key.Key_Return)
    assert not window.play_timer.isActive()

    sequence_edit = QKeySequenceEdit(window.centralWidget())
    sequence_edit.show()
    sequence_edit.setFocus()
    APPLICATION.processEvents()
    press(sequence_edit, Qt.Key.Key_Return)
    assert not window.play_timer.isActive()
    window.close()


def test_modal_dialogs_and_message_box_block_return_then_restore(tmp_path) -> None:
    window = focused_window(tmp_path)
    dialog_factories = (
        lambda: NewProjectDialog(window),
        window.create_project_settings_dialog,
        lambda: KeyboardShortcutsDialog(window.shortcuts, window),
    )
    for create_dialog in dialog_factories:
        dialog = create_dialog()
        dialog.open()
        APPLICATION.processEvents()
        press(dialog, Qt.Key.Key_Return)
        assert not window.play_timer.isActive()
        dialog.reject()
        dialog.deleteLater()
        APPLICATION.processEvents()

    message = QMessageBox(QMessageBox.Icon.Question, "Confirm", "Test", parent=window)
    message.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    message.open()
    APPLICATION.processEvents()
    press(message, Qt.Key.Key_Return)
    assert not window.play_timer.isActive()
    message.reject()
    message.deleteLater()
    APPLICATION.processEvents()

    window.activateWindow()
    window.canvas.setFocus()
    APPLICATION.processEvents()
    assert QApplication.activeModalWidget() is None
    press(window.canvas, Qt.Key.Key_Return)
    assert window.play_timer.isActive()
    window.set_playing(False)
    window.close()


def test_open_menu_blocks_return(tmp_path) -> None:
    window = focused_window(tmp_path)
    window.animation_menu.popup(window.mapToGlobal(QPoint(10, 10)))
    APPLICATION.processEvents()
    press(window.animation_menu, Qt.Key.Key_Return)
    assert not window.play_timer.isActive()
    window.animation_menu.close()
    window.close()


def test_custom_playback_shortcut_replaces_enter_and_persists(tmp_path) -> None:
    service = service_for(tmp_path)
    window = MainWindow(service)
    window.show()
    window.canvas.setFocus()
    APPLICATION.processEvents()
    changed = dict(DEFAULT_SHORTCUTS)
    changed["play_stop_animation"] = "Space"
    assert window.apply_shortcuts(changed)
    assert window.playback_shortcut_controller.sequence_text == "Space"
    assert window.playback_shortcut_controller.active_shortcut_count() == 1

    press(window.canvas, Qt.Key.Key_Return)
    press(window.canvas, Qt.Key.Key_Enter)
    assert not window.play_timer.isActive()
    press(window.canvas, Qt.Key.Key_Space)
    assert window.play_timer.isActive()
    window.set_playing(False)

    for _ in range(3):
        assert window.apply_shortcuts(changed)
    assert window.playback_shortcut_controller.active_shortcut_count() == 1
    window.close()

    restored = MainWindow(service_for(tmp_path))
    assert restored.shortcuts["play_stop_animation"] == ["Space"]
    assert restored.playback_shortcut_controller.active_shortcut_count() == 1
    restored.close()


def test_restore_defaults_reinstates_both_enter_keys(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    changed = dict(DEFAULT_SHORTCUTS)
    changed["play_stop_animation"] = "Space"
    window.apply_shortcuts(changed)
    window.apply_shortcuts(dict(DEFAULT_SHORTCUTS))
    assert window.playback_shortcut_controller.sequence_text == "Enter"
    assert window.playback_shortcut_controller.active_shortcut_count() == 2
    window.close()
