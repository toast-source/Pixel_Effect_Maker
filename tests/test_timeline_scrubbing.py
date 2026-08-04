from __future__ import annotations

import os
from copy import deepcopy

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.models.resource_composition import CompositionLayer, ResourceComposition
from app.models.source_asset import SourceAsset
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow


APPLICATION = QApplication.instance() or QApplication([])


def service(tmp_path):
    return ShortcutSettingsService(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def drag_cells(table, start_column, end_column, row=0):
    start = table.visualItemRect(table.item(row, start_column)).center()
    end = table.visualItemRect(table.item(row, end_column)).center()
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(table.viewport(), end, delay=5)
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=end)
    APPLICATION.processEvents()


def drag_path(table, columns, row=0):
    points = [table.visualItemRect(table.item(row, column)).center() for column in columns]
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=points[0])
    for point in points[1:]:
        QTest.mouseMove(table.viewport(), point, delay=2)
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=points[-1])
    APPLICATION.processEvents()


def test_effect_timeline_mouse_drag_scrubs_without_model_or_undo_change(tmp_path):
    window = MainWindow(service(tmp_path))
    for _ in range(11):
        window.project.add_frame()
    window._refresh_all(); window.show(); APPLICATION.processEvents()
    before = deepcopy(window.project.to_dict()); undo_count = window.application_undo_stack.count()
    window.set_playing(True)
    drag_cells(window.timeline.table, 0, 5)
    assert window.frame_index == 5 and window.canvas.frame_index == 5
    assert window.timeline.table.currentColumn() == 5 and not window.play_timer.isActive()
    assert window.project.to_dict() == before and window.application_undo_stack.count() == undo_count
    window.dirty = False; window.close()


def test_resource_timeline_mouse_drag_scrubs_and_preserves_tracks(tmp_path):
    window = MainWindow(service(tmp_path)); project = window.project
    asset = SourceAsset("a", np.full((4, 4, 4), 255, dtype=np.uint8)); project.source_assets.append(asset)
    composition = ResourceComposition("A", 4, 4, 12, 12, True)
    layer = CompositionLayer("a", "source_asset", asset.id, 0, 11)
    layer.add_property("position").set_keyframe(0, [0, 0]); layer.tracks["position"].set_keyframe(11, [6, 0])
    composition.layers.append(layer); project.resource_compositions.append(composition)
    editor = window.resource_editor; editor.refresh(project); editor.controller.select_composition(composition.id, layer.id)
    window.set_workspace("resource"); window.show(); APPLICATION.processEvents()
    before = deepcopy(composition.to_dict()); undo_count = window.application_undo_stack.count()
    editor.toggle_play(); assert editor._playing
    drag_cells(editor.composition_timeline.table, 0, 9)
    assert editor.frame_index == 9 and editor.composition_canvas.frame == 9
    assert editor.selected_layer is layer and not editor._playing
    assert composition.to_dict() == before and window.application_undo_stack.count() == undo_count
    window.dirty = False; window.close()


@pytest.mark.parametrize("frame_width", [20, 36, 64, 96])
def test_effect_scrub_reverses_direction_at_each_frame_width(tmp_path, frame_width):
    window = MainWindow(service(tmp_path))
    for _ in range(11):
        window.project.add_frame()
    window.timeline.set_frame_cell_width(frame_width)
    window._refresh_all(); window.show(); APPLICATION.processEvents()
    drag_path(window.timeline.table, [0, 5, 2, 9])
    assert window.frame_index == 9
    assert window.timeline.table.currentColumn() == 9
    assert window.timeline.table.columnWidth(0) == frame_width
    window.dirty = False; window.close()


def test_effect_scrub_clamps_at_left_and_right_edges(tmp_path):
    window = MainWindow(service(tmp_path))
    for _ in range(5):
        window.project.add_frame()
    window._refresh_all(); window.show(); APPLICATION.processEvents()
    table = window.timeline.table
    first = table.visualItemRect(table.item(0, 0)).center()
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseMove(table.viewport(), first - table.viewport().rect().topRight())
    QTest.mouseMove(table.viewport(), table.viewport().rect().topRight() + first)
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=table.viewport().rect().topRight() + first)
    APPLICATION.processEvents()
    assert window.frame_index == 5
    assert table.currentColumn() == 5
    window.dirty = False; window.close()
