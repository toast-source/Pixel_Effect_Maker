"""Actual frame-navigation keys, localization, and input-safety tests."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from app.services.localization_service import LocalizationService
from app.services.settings_service import ShortcutSettingsService
from app.ui.effect_properties_panel import EffectPropertiesPanel
from app.ui.main_window import MainWindow


APPLICATION = QApplication.instance() or QApplication([])


def service_for(tmp_path, language="en") -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", language)
    return ShortcutSettingsService(settings)


def focused_window(tmp_path) -> MainWindow:
    window = MainWindow(service_for(tmp_path))
    window.project.add_frame()
    window.project.add_frame()
    window._refresh_all()
    window.show()
    window.activateWindow()
    window.canvas.setFocus()
    APPLICATION.processEvents()
    return window


def press(widget, key, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(widget, key, modifiers)
    APPLICATION.processEvents()


def test_left_right_less_greater_move_exactly_one_and_clamp(tmp_path) -> None:
    window = focused_window(tmp_path)
    press(window.canvas, Qt.Key.Key_Right)
    assert window.frame_index == 1
    press(window.canvas, Qt.Key.Key_Period, Qt.KeyboardModifier.ShiftModifier)
    assert window.frame_index == 2
    press(window.canvas, Qt.Key.Key_Right)
    assert window.frame_index == 2
    press(window.canvas, Qt.Key.Key_Left)
    assert window.frame_index == 1
    press(window.canvas, Qt.Key.Key_Comma, Qt.KeyboardModifier.ShiftModifier)
    assert window.frame_index == 0
    press(window.canvas, Qt.Key.Key_Left)
    assert window.frame_index == 0
    window.close()


def test_frame_navigation_stops_playback_and_works_on_timeline(tmp_path) -> None:
    window = focused_window(tmp_path)
    window.set_playing(True)
    press(window.canvas, Qt.Key.Key_Right)
    assert not window.play_timer.isActive()
    assert window.frame_index == 1
    window.timeline.table.setFocus()
    press(window.timeline.table, Qt.Key.Key_Right)
    assert window.frame_index == 2
    window.close()


def test_frame_shortcuts_do_not_override_inputs_or_library_lists(tmp_path) -> None:
    window = focused_window(tmp_path)
    window.frame_index = 1
    line = QLineEdit("abc", window)
    line.show()
    line.setFocus()
    press(line, Qt.Key.Key_Left)
    assert window.frame_index == 1
    window.effect_properties.output_frames.setFocus()
    press(window.effect_properties.output_frames, Qt.Key.Key_Right)
    assert window.frame_index == 1
    window.effect_library.asset_list.setFocus()
    press(window.effect_library.asset_list, Qt.Key.Key_Right)
    assert window.frame_index == 1
    window.close()


def test_localization_defaults_persists_and_switches_runtime(tmp_path) -> None:
    ko_settings = QSettings(str(tmp_path / "ko.ini"), QSettings.Format.IniFormat)
    ko = LocalizationService(ko_settings, system_locale="ko_KR")
    assert ko.language == "ko"
    assert ko.text("menu.file") == "파일"
    en_settings = QSettings(str(tmp_path / "en.ini"), QSettings.Format.IniFormat)
    en = LocalizationService(en_settings, system_locale="en_US")
    assert en.language == "en"
    assert en.text("missing.translation.key") == "missing.translation.key"
    en.set_language("ko")
    assert LocalizationService(en_settings, system_locale="en_US").language == "ko"

    window = MainWindow(service_for(tmp_path / "window", "en"))
    window.project.name = "User Project"
    window.localization.set_language("ko")
    assert window.file_menu.title() == "파일"
    assert window.effect_properties.generate_button.text() == "프레임에 적용"
    assert "프레임" in window.timeline.playback_status_label.text()
    assert window.project.name == "User Project"
    window.localization.set_language("en")
    assert window.file_menu.title() == "File"
    assert window.effect_library.title_label.text() == "Effect Library"
    window.close()


def test_properties_have_units_help_and_safe_wheel_behavior() -> None:
    panel = EffectPropertiesPanel()
    panel.widget().setEnabled(True)
    panel.show()
    APPLICATION.processEvents()
    assert panel.output_frames.suffix() == " frames"
    assert panel.origin_x.suffix() == " px"
    assert panel.rotation_start.suffix() == "°"
    assert panel.generate_button.toolTip()
    assert panel.emission_interval.toolTip()
    original = panel.output_frames.value()
    panel.output_frames.clearFocus()
    event = QWheelEvent(
        QPointF(2, 2), QPointF(2, 2), QPoint(), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate, False,
    )
    QApplication.sendEvent(panel.output_frames, event)
    assert panel.output_frames.value() == original
    QTest.mouseClick(panel.output_frames.lineEdit(), Qt.MouseButton.LeftButton)
    APPLICATION.processEvents()
    focused_event = QWheelEvent(
        QPointF(2, 2), QPointF(2, 2), QPoint(), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate, False,
    )
    QApplication.sendEvent(panel.output_frames, focused_event)
    assert panel.output_frames.value() == original + 1
    panel.close()
