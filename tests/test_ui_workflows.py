"""Stable offscreen tests for editor selection and new-project settings."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog

from app.models.project import Project
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow
from app.ui.new_project_dialog import NewProjectDialog, NewProjectSettings
from app.ui.timeline_widget import TimelineWidget


@pytest.fixture(scope="module")
def application() -> QApplication:
    return QApplication.instance() or QApplication([])


def isolated_settings(tmp_path) -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "shortcuts.ini"), QSettings.Format.IniFormat)
    return ShortcutSettingsService(settings)


def test_new_project_dialog_defaults_and_settings(application) -> None:
    dialog = NewProjectDialog()
    assert dialog.settings() == NewProjectSettings("Untitled", 64, 64, 12, True)
    assert dialog.create_button.isEnabled()


def test_new_project_dialog_rejects_empty_name(application) -> None:
    dialog = NewProjectDialog()
    dialog.name_edit.setText("   ")
    assert not dialog.create_button.isEnabled()
    assert dialog.validation_label.text()
    with pytest.raises(ValueError, match="must not be empty"):
        dialog.settings()


def test_new_project_numeric_inputs_stay_within_model_limits(application) -> None:
    dialog = NewProjectDialog()
    dialog.width_spin.setValue(0)
    dialog.height_spin.setValue(2048)
    dialog.fps_spin.setValue(240)
    assert dialog.width_spin.value() == 1
    assert dialog.height_spin.value() == 1024
    assert dialog.fps_spin.value() == 120


def test_new_project_preset_and_custom_size(application) -> None:
    dialog = NewProjectDialog()
    dialog.preset_combo.setCurrentText("32 × 32")
    assert (dialog.width_spin.value(), dialog.height_spin.value()) == (32, 32)
    dialog.width_spin.setValue(40)
    assert dialog.preset_combo.currentText() == "Custom"
    assert dialog.width_spin.value() == 40
    assert dialog.height_spin.value() == 32


def test_new_project_settings_apply_to_model(application) -> None:
    dialog = NewProjectDialog()
    dialog.name_edit.setText("  Spark  ")
    dialog.width_spin.setValue(48)
    dialog.height_spin.setValue(32)
    dialog.fps_spin.setValue(24)
    dialog.loop_check.setChecked(False)
    settings = dialog.settings()
    project = Project.create_default(
        settings.name, settings.width, settings.height, settings.fps, settings.loop
    )
    assert (project.name, project.width, project.height) == ("Spark", 48, 32)
    assert (project.fps, project.loop) == (24, False)


def test_timeline_uses_continuous_position_headers(application) -> None:
    project = Project.create_default()
    project.add_frame()
    project.add_frame()
    project.add_layer()
    timeline = TimelineWidget()
    timeline.refresh(project, selected_layer=0, selected_frame=1)
    assert timeline.table.rowCount() == 2
    assert timeline.table.columnCount() == 3
    assert [
        timeline.table.horizontalHeaderItem(index).text() for index in range(3)
    ] == ["1", "2", "3"]

    project.delete_frame(1)
    timeline.refresh(project, selected_layer=0, selected_frame=1)
    assert [
        timeline.table.horizontalHeaderItem(index).text() for index in range(2)
    ] == ["1", "2"]


def test_timeline_cell_selects_layer_and_frame(application) -> None:
    project = Project.create_default()
    project.add_frame()
    project.add_layer("Glow")
    timeline = TimelineWidget()
    timeline.refresh(project)
    selected: list[tuple[int, int]] = []
    timeline.cell_selected.connect(lambda layer, frame: selected.append((layer, frame)))
    timeline.table.setCurrentCell(0, 1)
    assert selected[-1] == (1, 1)
    assert timeline.selection_label.text() == "Glow · Frame 2"


def test_main_window_synchronizes_selected_cell(application, tmp_path) -> None:
    window = MainWindow(isolated_settings(tmp_path))
    window.project.add_layer("Glow")
    window.project.add_frame()
    window._refresh_all()
    window.select_cell(1, 1)
    assert (window.layer_index, window.frame_index) == (1, 1)
    assert (window.canvas.layer_index, window.canvas.frame_index) == (1, 1)
    assert window.timeline.table.currentColumn() == 1
    window.close()


def test_cancelled_new_project_keeps_existing_project(
    application, monkeypatch, tmp_path
) -> None:
    window = MainWindow(isolated_settings(tmp_path))
    original = window.project

    class CancelledDialog:
        def __init__(self, parent) -> None:
            pass

        def exec(self) -> int:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("app.ui.main_window.NewProjectDialog", CancelledDialog)
    window.new_project()
    assert window.project is original
    window.close()


def test_accepted_new_project_applies_all_settings(
    application, monkeypatch, tmp_path
) -> None:
    window = MainWindow(isolated_settings(tmp_path))

    class AcceptedDialog:
        def __init__(self, parent) -> None:
            pass

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def settings(self) -> NewProjectSettings:
            return NewProjectSettings("Burst", 96, 48, 30, False)

    monkeypatch.setattr("app.ui.main_window.NewProjectDialog", AcceptedDialog)
    window.new_project()
    assert (
        window.project.name,
        window.project.width,
        window.project.height,
        window.project.fps,
        window.project.loop,
    ) == ("Burst", 96, 48, 30, False)
    window.close()
