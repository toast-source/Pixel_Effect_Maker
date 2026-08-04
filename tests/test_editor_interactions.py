from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPoint,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QGroupBox,QLabel,QStyle,QStyleOptionSpinBox

from app.models.source_asset import SourceAsset
from app.services.localization_service import LocalizationService
from app.services.settings_service import ShortcutSettingsService
from app.ui.interface_settings_dialog import InterfaceSettingsDialog,timeline_frame_width
from app.ui.main_window import MainWindow
from app.ui.resource_editor_v2.new_resource_dialog import NewResourceDialog


APP=QApplication.instance() or QApplication([])


def service(tmp_path,language="en"):
    settings=QSettings(str(tmp_path/"settings.ini"),QSettings.Format.IniFormat);settings.setValue("ui/language",language);return ShortcutSettingsService(settings)


def asset():return SourceAsset(name="asset",pixels=np.full((3,3,4),255,dtype=np.uint8),pivot_x=1.5,pivot_y=1.5)


def spin_button(spin,control):
    option=QStyleOptionSpinBox();spin.initStyleOption(option)
    return spin.style().subControlRect(QStyle.ComplexControl.CC_SpinBox,option,control,spin).center()


def test_duration_spin_repeated_mouse_and_keyboard_steps(tmp_path):
    dialog=NewResourceDialog(asset(),LocalizationService(service(tmp_path).settings,"en"));dialog.show();APP.processEvents();spin=dialog.duration;identity=id(spin)
    up=spin_button(spin,QStyle.SubControl.SC_SpinBoxUp);down=spin_button(spin,QStyle.SubControl.SC_SpinBoxDown)
    for _ in range(5):QTest.mouseClick(spin,Qt.MouseButton.LeftButton,pos=up)
    assert dialog.frames.value()==17 and dialog.duration.value()==pytest.approx(17/12,abs=1e-4)
    for _ in range(3):QTest.mouseClick(spin,Qt.MouseButton.LeftButton,pos=down)
    assert dialog.frames.value()==14
    spin.setFocus()
    for _ in range(5):QTest.keyClick(spin,Qt.Key.Key_Up)
    for _ in range(3):QTest.keyClick(spin,Qt.Key.Key_Down)
    assert dialog.frames.value()==16 and id(dialog.duration)==identity


@pytest.mark.parametrize("fps,frames",[(12,1),(12,2),(12,12),(24,1),(24,24),(24,48),(60,1),(60,60)])
def test_resource_timing_is_frame_exact(tmp_path,fps,frames):
    dialog=NewResourceDialog(asset(),LocalizationService(service(tmp_path).settings,"en"));dialog.fps.setValue(fps);dialog.frames.setValue(frames)
    assert dialog.duration.minimum()==pytest.approx(1/fps,abs=1e-4);assert dialog.duration.singleStep()==pytest.approx(1/fps,abs=1e-4);assert dialog.duration.value()==pytest.approx(frames/fps,abs=1e-4)


def test_timeline_width_settings_apply_and_persist(tmp_path):
    svc=service(tmp_path);window=MainWindow(svc);assert window.timeline.frame_cell_width==36
    for width in (20,64,96):window.apply_timeline_frame_width(width);assert window.timeline.frame_cell_width==width and window.resource_editor.composition_timeline.frame_cell_width==width
    window.apply_timeline_frame_width(64)
    assert MainWindow(service(tmp_path)).timeline.frame_cell_width==64
    svc.settings.setValue("ui/timeline_frame_width",999);assert timeline_frame_width(svc.settings)==96
    dialog=InterfaceSettingsDialog(svc.settings,window.localization);dialog.reset.click();assert dialog.spin.value()==36


def test_menu_policy_localization_and_tooltips(tmp_path):
    window=MainWindow(service(tmp_path,"ko"));file_actions=window.file_menu.actions();edit_actions=window.edit_menu.actions()
    assert window.project_settings_action not in file_actions and window.project_settings_action in edit_actions
    assert edit_actions.index(window.undo_action)<edit_actions.index(window.project_settings_action);assert window.interface_settings_action in window.settings_menu.actions()
    assert file_actions.count(window.export_action)==0 and window.export_menu.actions().count(window.export_action)==1
    assert window.undo_action.toolTip() and "Ctrl+Z" in window.undo_action.toolTip();assert window.resource_editor.composition_timeline.play.toolTip()
    labels=[label.text() for group in window.particle_properties.findChildren(QGroupBox) for label in group.findChildren(QLabel)]
    assert "최소 속도" in labels and "최대 수명" in labels and "시드" in labels
    window.localization.set_language("en");assert window.edit_menu.title()=="Edit" and "Ctrl+Z" in window.undo_action.toolTip()


def prepared_window(tmp_path):
    window=MainWindow(service(tmp_path));project=window.project;source=asset();project.source_assets.append(source);editor=window.resource_editor;editor.refresh(project);editor._last_asset=("source_asset",source.id);composition=editor.create_composition();layer=editor.add_selected_asset();APP.processEvents();return window,editor,layer


def test_resource_values_full_rotation_and_axis_gizmo_are_single_undo_steps(tmp_path):
    window,editor,layer=prepared_window(tmp_path);editor.add_property_to_layer("position");window.application_undo_stack.clear()
    editor._property_value("position",[7,3]);assert layer.value("position",0)==[7,3];window.application_undo_stack.undo();assert layer.value("position",0)==[0.0,0.0];window.application_undo_stack.redo();assert layer.value("position",0)==[7,3]
    editor.add_full_rotation();assert len(layer.tracks["rotation"].keyframes)==2;window.application_undo_stack.undo();assert "rotation" not in layer.tracks;window.application_undo_stack.redo();assert len(layer.tracks["rotation"].keyframes)==2
    canvas=editor.composition_canvas;canvas.resize(700,500);editor.set_gizmo("move");APP.processEvents();before=list(layer.value("position",0));x=canvas.move_handle_positions()["x"].toPoint();QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=x);QTest.mouseMove(canvas,x+QPoint(16,12));QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=x+QPoint(16,12));after=layer.value("position",0);assert after[0]!=before[0] and after[1]==before[1]
    window.application_undo_stack.undo();assert layer.value("position",0)==before
    editor.set_gizmo("scale");APP.processEvents();before_scale=list(layer.value("scale",0));sx=canvas.scale_handle_positions()["x"].toPoint();QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=sx);QTest.mouseMove(canvas,sx+QPoint(20,0));QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=sx+QPoint(20,0));assert layer.value("scale",0)[0]!=before_scale[0] and layer.value("scale",0)[1]==before_scale[1]


def test_effect_frame_layer_visibility_and_clean_state_undo(tmp_path):
    window=MainWindow(service(tmp_path));stack=window.application_undo_stack;stack.setClean();window.add_frame();assert len(window.project.frames)==2 and window.dirty
    stack.undo();assert len(window.project.frames)==1 and not window.dirty;stack.redo();assert len(window.project.frames)==2
    window.add_layer();assert len(window.project.layers)==2;stack.undo();assert len(window.project.layers)==1;stack.redo();assert len(window.project.layers)==2
    old=window.project.layers[0].visible;window._mark_dirty();window.set_layer_visibility(0,not old);assert window.project.layers[0].visible is not old;stack.undo();assert window.project.layers[0].visible is old and window.dirty
