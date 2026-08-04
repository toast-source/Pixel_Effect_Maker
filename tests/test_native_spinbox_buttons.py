from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractSpinBox, QStyle, QStyleOptionSpinBox, QWidget

from app.models.project import Project
from app.models.source_asset import SourceAsset
from app.services.localization_service import LocalizationService
from app.ui.effect_properties_panel import EffectPropertiesPanel
from app.ui.focus_wheel_widgets import FocusWheelDoubleSpinBox, FocusWheelSpinBox
from app.ui.interface_settings_dialog import InterfaceSettingsDialog
from app.ui.new_project_dialog import NewProjectDialog
from app.ui.particle_properties_panel import ParticlePropertiesPanel
from app.ui.project_settings_dialog import ProjectSettingsDialog
from app.ui.resource_editor_v2.composition_inspector import LayerInspector
from app.ui.resource_editor_v2.new_resource_dialog import NewResourceDialog


APP = QApplication.instance() or QApplication([])


def localization(tmp_path):
    settings = QSettings(str(tmp_path / "native-spin.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", "en")
    return settings, LocalizationService(settings, "en")


def source_asset():
    pixels = np.full((143, 91, 4), 255, dtype=np.uint8)
    return SourceAsset(name="native-buttons", pixels=pixels, pivot_x=45.5, pivot_y=71.5)


def button_center(spinbox, control):
    option = QStyleOptionSpinBox(); spinbox.initStyleOption(option)
    rect = spinbox.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option, control, spinbox)
    assert rect.isValid() and rect.width() > 0 and rect.height() > 0
    return rect.center()


def click(spinbox, control, count=1):
    point = button_center(spinbox, control)
    for _ in range(count): QTest.mouseClick(spinbox, Qt.MouseButton.LeftButton, pos=point)


def wheel(spinbox, delta):
    local = QPointF(spinbox.rect().center()); global_pos = QPointF(spinbox.mapToGlobal(local.toPoint()))
    event = QWheelEvent(local, global_pos, QPoint(), QPoint(0, delta), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False)
    QApplication.sendEvent(spinbox, event)
    return event


@pytest.fixture
def dialog(tmp_path):
    _, language = localization(tmp_path); value = NewResourceDialog(source_asset(), language); value.show(); APP.processEvents()
    yield value
    value.close()


@pytest.mark.parametrize("name", ["width", "height", "fps", "duration", "frames"])
def test_new_resource_native_first_click_and_repeated_up_down(dialog, name):
    spinbox = getattr(dialog, name); identity = id(spinbox); start = spinbox.value(); step = spinbox.singleStep()
    dialog.create.setFocus(); spinbox.clearFocus(); APP.processEvents()
    click(spinbox, QStyle.SubControl.SC_SpinBoxUp)
    assert spinbox.value() == pytest.approx(start + step, abs=1e-4)
    click(spinbox, QStyle.SubControl.SC_SpinBoxUp, 4)
    click(spinbox, QStyle.SubControl.SC_SpinBoxDown, 3)
    assert spinbox.value() == pytest.approx(start + 2 * step, abs=1e-4)
    assert id(getattr(dialog, name)) == identity
    assert spinbox.isEnabled() and not spinbox.isReadOnly() and spinbox.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.UpDownArrows


def test_selected_text_and_fast_clicks_do_not_block_native_buttons(dialog):
    dialog.height.setValue(143); dialog.height.setFocus(); dialog.height.lineEdit().selectAll(); APP.processEvents()
    click(dialog.height, QStyle.SubControl.SC_SpinBoxUp); assert dialog.height.value() == 144
    dialog.width.setValue(91); click(dialog.width, QStyle.SubControl.SC_SpinBoxUp, 10); assert dialog.width.value() == 101
    click(dialog.width, QStyle.SubControl.SC_SpinBoxDown, 10); assert dialog.width.value() == 91


def test_mouse_press_hold_uses_qt_native_auto_repeat(dialog):
    spinbox=dialog.width;spinbox.setValue(91);point=button_center(spinbox,QStyle.SubControl.SC_SpinBoxUp)
    QTest.mousePress(spinbox,Qt.MouseButton.LeftButton,pos=point);QTest.qWait(800);QTest.mouseRelease(spinbox,Qt.MouseButton.LeftButton,pos=point)
    assert spinbox.value() >= 93


def test_keyboard_and_timing_remain_native_and_frame_exact(dialog):
    dialog.width.setValue(91); dialog.width.setFocus()
    for _ in range(5): QTest.keyClick(dialog.width, Qt.Key.Key_Up)
    for _ in range(3): QTest.keyClick(dialog.width, Qt.Key.Key_Down)
    assert dialog.width.value() == 93
    QTest.keyClick(dialog.width, Qt.Key.Key_PageUp); assert dialog.width.value() > 93
    for fps in (12, 24, 60):
        dialog.fps.setValue(fps); dialog.frames.setValue(fps)
        assert dialog.duration.value() == pytest.approx(1.0, abs=1e-4)
    dialog.fps.setValue(12); dialog.frames.setValue(1); assert dialog.duration.value() == pytest.approx(1 / 12, abs=1e-4)


def test_focus_wheel_policy_does_not_intercept_mouse_buttons(dialog):
    spinbox = dialog.width; dialog.create.setFocus(); spinbox.clearFocus(); before = spinbox.value()
    ignored = wheel(spinbox, 120); assert spinbox.value() == before and not ignored.isAccepted()
    click(spinbox, QStyle.SubControl.SC_SpinBoxUp); after_click = spinbox.value(); assert spinbox.hasFocus() or spinbox.lineEdit().hasFocus()
    accepted = wheel(spinbox, 120); assert spinbox.value() == after_click + spinbox.singleStep() and accepted.isAccepted()
    point = button_center(spinbox, QStyle.SubControl.SC_SpinBoxUp); target = dialog.childAt(spinbox.mapTo(dialog, point)); assert target in (spinbox, spinbox.lineEdit())


def test_focus_wheel_common_classes_keep_qt_default_mouse_handlers():
    assert "mousePressEvent" not in FocusWheelSpinBox.__mro__[1].__dict__
    assert "mouseReleaseEvent" not in FocusWheelSpinBox.__mro__[1].__dict__
    assert "focusInEvent" not in FocusWheelSpinBox.__mro__[1].__dict__
    assert "focusOutEvent" not in FocusWheelSpinBox.__mro__[1].__dict__


def test_representative_dialog_and_panel_spinboxes_keep_native_buttons(tmp_path):
    settings, language = localization(tmp_path); project = Project.create_default()
    project_dialog = NewProjectDialog(localization=language)
    settings_dialog = ProjectSettingsDialog(project, None, lambda values: True, localization=language)
    interface_dialog = InterfaceSettingsDialog(settings, language)
    layer_panel = LayerInspector(); particle_panel = ParticlePropertiesPanel(); effect_panel = EffectPropertiesPanel()
    particle_panel.widget().setEnabled(True); effect_panel.widget().setEnabled(True)
    containers=(project_dialog,settings_dialog,interface_dialog,layer_panel,particle_panel,effect_panel)
    for container in containers:container.show()
    APP.processEvents();widgets = (project_dialog.width_spin, settings_dialog.width_spin, interface_dialog.spin, layer_panel.start, particle_panel.output_frame_count, effect_panel.output_frames)
    for spinbox in widgets:
        spinbox.show(); APP.processEvents(); start = spinbox.value(); click(spinbox, QStyle.SubControl.SC_SpinBoxUp); assert spinbox.value() == start + spinbox.singleStep()
    for widget in containers: widget.close()
