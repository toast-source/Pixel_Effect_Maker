from __future__ import annotations

import os

import numpy as np
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.models.source_asset import SourceAsset
from app.models.project import Project
from app.services.canvas_resize_service import CanvasAnchor, CanvasResizeMode
from app.services.settings_service import ShortcutSettingsService
from app.ui.canvas_widget import CanvasWidget
from app.ui.main_window import MainWindow
from app.ui.project_settings_dialog import ProjectSettingsValues
from app.ui.resource_editor_v2.new_resource_dialog import NewResourceDialog
from app.ui.resource_editor_v2.resource_editor_state import ResourceEditorMode


APPLICATION = QApplication.instance() or QApplication([])


def service(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", "en")
    return ShortcutSettingsService(settings)


def png(tmp_path, name="drop.png"):
    path = tmp_path / name
    Image.fromarray(np.full((4, 4, 4), 255, dtype=np.uint8), "RGBA").save(path)
    return path


def drop_event(paths):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    event = QDropEvent(QPointF(4, 4), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    return mime, event


def test_resource_editor_accepts_mixed_case_drop_and_selects_first_success(tmp_path):
    upper = png(tmp_path, "DROP.PNG")
    unsupported = tmp_path / "ignore.txt"
    unsupported.write_text("ignored", encoding="utf-8")
    window = MainWindow(service(tmp_path))
    editor = window.resource_editor
    mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(upper)), QUrl.fromLocalFile(str(unsupported))])
    enter = QDragEnterEvent(QPoint(4, 4), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    editor.dragEnterEvent(enter)
    assert enter.isAccepted()
    drop_mime, drop = drop_event([upper, unsupported])
    editor.dropEvent(drop)
    assert len(window.project.source_assets) == 1
    assert editor.controller.state.mode is ResourceEditorMode.ASSET_INSPECT
    assert editor.controller.asset is window.project.source_assets[0]


def test_asset_list_and_composition_canvas_use_common_drop_path(tmp_path):
    first = png(tmp_path, "one.png")
    second = png(tmp_path, "two.png")
    window = MainWindow(service(tmp_path)); editor = window.resource_editor
    first_mime, first_drop = drop_event([first])
    assert editor.eventFilter(editor.browser.asset_list.viewport(), first_drop)
    second_mime, second_drop = drop_event([second])
    assert editor.eventFilter(editor.composition_canvas, second_drop)
    assert [asset.name for asset in window.project.source_assets] == ["one.png", "two.png"]


def test_canvas_ignores_preview_with_stale_shape():
    project = Project.create_default()
    canvas = CanvasWidget(); canvas.set_project(project)
    canvas.set_preview([np.full((7, 9, 4), 255, dtype=np.uint8)], None)
    result = canvas._compose_display_frame()
    assert result.shape == (project.height, project.width, 4)
    assert np.array_equal(result, project.compose_frame(0))


def test_resize_clears_preview_context_and_rejects_stale_results(tmp_path):
    window = MainWindow(service(tmp_path))
    old_context = window.preview_manager._context_revision
    window.active_preview_generator_id = "old"
    window.canvas.set_preview([np.zeros((64, 64, 4), dtype=np.uint8)], None)
    window.set_playing(True)
    values = ProjectSettingsValues(window.project.name, window.project.fps, window.project.loop, 600, 600, CanvasResizeMode.CANVAS_ONLY, CanvasAnchor.CENTER)
    assert window.apply_project_settings(values)
    assert (window.project.width, window.project.height) == (600, 600)
    assert window.canvas.preview_frames is None and window.active_preview_generator_id is None
    assert not window.play_timer.isActive()
    assert window.preview_manager._context_revision == old_context + 1
    window.preview_manager._worker_completed(old_context, "old", 0, [np.zeros((64, 64, 4), dtype=np.uint8)], "")
    assert not window.preview_manager.sessions


def prepared_composition(tmp_path):
    window = MainWindow(service(tmp_path)); editor = window.resource_editor
    asset = window.import_resources([png(tmp_path)])[0]
    editor.controller.select_asset("source_asset", asset.id)
    composition = editor.controller.create_resource("A", 4, 4, 12, 12, True)
    editor.browser.refresh(window.project, None, composition.id)
    return window, editor, asset, composition, composition.layers[0]


def test_asset_to_same_composition_restores_layer_frame_gizmo_and_model(tmp_path):
    window, editor, asset, composition, layer = prepared_composition(tmp_path)
    layer.add_property("position").set_keyframe(7, [3.0, 4.0])
    editor.controller.set_frame(7); editor.set_gizmo("rotate")
    before = composition.to_dict()
    asset_item = editor.browser.asset_list.item(0)
    QTest.mouseClick(editor.browser.asset_list.viewport(), Qt.MouseButton.LeftButton, pos=editor.browser.asset_list.visualItemRect(asset_item).center())
    resource_item = editor.browser.resource_list.item(0)
    QTest.mouseClick(editor.browser.resource_list.viewport(), Qt.MouseButton.LeftButton, pos=editor.browser.resource_list.visualItemRect(resource_item).center())
    assert editor.selected_layer is layer and editor.frame_index == 7
    assert editor.controller.state.gizmo_mode == "rotate"
    assert composition.to_dict() == before


def test_workspace_round_trip_and_refresh_preserve_selection(tmp_path):
    window, editor, _asset, composition, layer = prepared_composition(tmp_path)
    editor.controller.set_frame(6); editor.set_gizmo("scale")
    QTest.mouseClick(window.effect_workspace_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(window.resource_workspace_button, Qt.MouseButton.LeftButton)
    editor.refresh(window.project)
    assert editor.composition is composition and editor.selected_layer is layer
    assert editor.frame_index == 6 and editor.controller.state.gizmo_mode == "scale"


def test_new_resource_single_length_control_and_unit_fps_policy(tmp_path):
    asset = SourceAsset("a.png", np.zeros((4, 4, 4), dtype=np.uint8))
    localization = MainWindow(service(tmp_path)).localization
    dialog = NewResourceDialog(asset, localization)
    assert dialog.form.labelForField(dialog.length_row).text() == "Length"
    assert dialog.frames.isVisible() is False or dialog.length_stack.currentWidget() is dialog.frames
    dialog.frames.setValue(12); dialog.fps.setValue(24)
    assert dialog.frames.value() == 12 and dialog.duration.value() == .5
    dialog.length_unit.setCurrentIndex(1); dialog.duration.setValue(1.0); dialog.fps.setValue(12); dialog.fps.setValue(24)
    assert dialog.duration.value() == 1.0 and dialog.frames.value() == 24
    dialog.length_unit.setCurrentIndex(0)
    assert dialog.values()[4] == 24
