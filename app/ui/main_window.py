"""Main application window and UI orchestration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project, ProjectError
from app.services.export_service import ExportError, export_png_frames
from app.services.project_io import ProjectIOError, load_project, save_project
from app.services.canvas_resize_service import (
    CanvasResizeError,
    CanvasResizeMode,
    resize_canvas,
    scale_project,
)
from app.services.sample_project_service import create_playback_test_project
from app.services.settings_service import SettingsError, ShortcutSettingsService
from app.shortcuts import DEFAULT_SHORTCUTS
from app.version import get_display_name

from .canvas_widget import CanvasWidget
from .keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from .new_project_dialog import NewProjectDialog
from .project_settings_dialog import ProjectSettingsDialog, ProjectSettingsValues
from .timeline_widget import TimelineWidget


class MainWindow(QMainWindow):
    """Coordinate project state, services, and editor widgets."""

    def __init__(
        self, settings_service: ShortcutSettingsService | None = None
    ) -> None:
        super().__init__()
        self.setWindowTitle(get_display_name())
        self.resize(1280, 800)
        self.project = Project.create_default()
        self.project_path: Path | None = None
        self.frame_index = 0
        self.layer_index = 0
        self.dirty = False
        self.settings_service = settings_service or ShortcutSettingsService()
        try:
            self.shortcuts = self.settings_service.load()
        except SettingsError:
            self.shortcuts = dict(DEFAULT_SHORTCUTS)
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance_playback)

        self._build_ui()
        self._build_menus()
        self._connect_signals()
        self._refresh_all()

    def _build_ui(self) -> None:
        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(4, 4, 4, 4)
        self.canvas = CanvasWidget()
        root_layout.addWidget(self.canvas, 1)
        self.timeline = TimelineWidget()
        root_layout.addWidget(self.timeline)
        self.setCentralWidget(container)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self.new_action = QAction("New Project…", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.open_action = QAction("Open…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.project_settings_action = QAction("Project Settings…", self)
        self.playback_test_action = QAction("Create Playback Test Project", self)
        self.export_action = QAction("Export PNG Frames…", self)
        file_menu.addActions(
            [self.new_action, self.open_action, self.save_action, self.save_as_action]
        )
        file_menu.addSeparator()
        file_menu.addAction(self.project_settings_action)
        file_menu.addAction(self.playback_test_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_action)

        edit_menu = self.menuBar().addMenu("Edit")
        self.keyboard_shortcuts_action = QAction("Keyboard Shortcuts…", self)
        edit_menu.addAction(self.keyboard_shortcuts_action)

        layer_menu = self.menuBar().addMenu("Layer")
        self.new_layer_action = QAction("New Layer", self)
        self.delete_layer_action = QAction("Delete Layer", self)
        layer_menu.addActions([self.new_layer_action, self.delete_layer_action])

        frame_menu = self.menuBar().addMenu("Frame")
        self.new_frame_action = QAction("New Frame (Duplicate Current)", self)
        self.new_empty_frame_action = QAction("New Empty Frame", self)
        self.delete_frame_action = QAction("Delete Frame", self)
        frame_menu.addActions(
            [
                self.new_frame_action,
                self.new_empty_frame_action,
                self.delete_frame_action,
            ]
        )

        animation_menu = self.menuBar().addMenu("Animation")
        self.play_action = QAction("Play / Stop Animation", self, checkable=True)
        animation_menu.addAction(self.play_action)

        view_menu = self.menuBar().addMenu("View")
        self.status_bar_action = QAction("Status Bar", self, checkable=True)
        self.status_bar_action.setChecked(True)
        view_menu.addAction(self.status_bar_action)

        export_menu = self.menuBar().addMenu("Export")
        export_menu.addAction(self.export_action)

        # Compatibility aliases for the existing action-oriented tests and code.
        self.add_layer_action = self.new_layer_action
        self.duplicate_frame_action = self.new_frame_action
        self.add_frame_action = self.new_empty_frame_action
        self.shortcut_actions = {
            "new_layer": self.new_layer_action,
            "new_frame": self.new_frame_action,
            "new_empty_frame": self.new_empty_frame_action,
            "play_stop_animation": self.play_action,
        }
        self._update_action_shortcuts(self.shortcuts)

    def _connect_signals(self) -> None:
        self.new_action.triggered.connect(self.new_project)
        self.open_action.triggered.connect(self.open_project)
        self.save_action.triggered.connect(self.save)
        self.save_as_action.triggered.connect(self.save_as)
        self.project_settings_action.triggered.connect(self.show_project_settings)
        self.playback_test_action.triggered.connect(self.create_playback_test)
        self.export_action.triggered.connect(self.export_frames)
        self.keyboard_shortcuts_action.triggered.connect(
            self.show_keyboard_shortcuts
        )
        self.new_frame_action.triggered.connect(self.duplicate_frame)
        self.new_empty_frame_action.triggered.connect(self.add_frame)
        self.delete_frame_action.triggered.connect(self.delete_frame)
        self.new_layer_action.triggered.connect(self.add_layer)
        self.delete_layer_action.triggered.connect(self.delete_layer)
        self.play_action.toggled.connect(self.set_playing)
        self.status_bar_action.toggled.connect(self.statusBar().setVisible)
        self.timeline.add_requested.connect(self.add_frame)
        self.timeline.duplicate_requested.connect(self.duplicate_frame)
        self.timeline.delete_requested.connect(self.delete_frame)
        self.timeline.add_layer_requested.connect(self.add_layer)
        self.timeline.delete_layer_requested.connect(self.delete_layer)
        self.timeline.cell_selected.connect(self.select_cell)
        self.timeline.play_requested.connect(self.play_action.trigger)
        self.timeline.fps_changed.connect(self.set_fps)

    def _refresh_all(self) -> None:
        self.frame_index = max(0, min(self.frame_index, len(self.project.frames) - 1))
        self.layer_index = max(0, min(self.layer_index, len(self.project.layers) - 1))
        self.canvas.set_project(self.project)
        self.canvas.set_frame(self.frame_index)
        self.canvas.set_layer(self.layer_index)
        self.timeline.refresh(self.project, self.layer_index, self.frame_index)
        self.timeline.set_playing(self.play_timer.isActive())
        self._update_title()
        self._refresh_selection_status()

    def _refresh_selection_status(self) -> None:
        self.statusBar().showMessage(
            f"{self.project.layers[self.layer_index].name} · "
            f"Frame {self.frame_index + 1}"
        )

    def _update_title(self) -> None:
        marker = "*" if self.dirty else ""
        self.setWindowTitle(f"{get_display_name()} - {self.project.name}{marker}")

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._update_title()

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Discard the unsaved changes?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        dialog = NewProjectDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.set_playing(False)
        settings = dialog.settings()
        self.project = Project.create_default(
            settings.name,
            settings.width,
            settings.height,
            settings.fps,
            settings.loop,
        )
        self.project_path = None
        self.frame_index = self.layer_index = 0
        self.dirty = False
        self._refresh_all()
        self.statusBar().showMessage("New project created", 3000)

    def open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "projects", "Pixel Effect Project (*.peffect.json)"
        )
        if not path:
            return
        try:
            self.project = load_project(path)
        except ProjectIOError as exc:
            QMessageBox.critical(self, "Open Failed", str(exc))
            return
        self.set_playing(False)
        self.project_path = Path(path)
        self.frame_index = self.layer_index = 0
        self.dirty = False
        self._refresh_all()
        self.statusBar().showMessage(f"Opened {path}", 4000)

    def save(self) -> bool:
        if self.project_path is None:
            return self.save_as()
        try:
            self.project_path = save_project(self.project, self.project_path)
        except ProjectIOError as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return False
        self.dirty = False
        self._update_title()
        self.statusBar().showMessage(f"Saved {self.project_path}", 4000)
        return True

    def save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(Path("projects") / f"{self.project.name}.peffect.json"),
            "Pixel Effect Project (*.peffect.json)",
        )
        if not path:
            return False
        self.project_path = Path(path)
        return self.save()

    def export_frames(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Export PNG Frames", str(Path("exports").resolve())
        )
        if not directory:
            return
        try:
            written = export_png_frames(self.project, directory)
        except ExportError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return
        QMessageBox.information(
            self, "Export Complete", f"Exported {len(written)} PNG frame(s)."
        )

    def create_project_settings_dialog(self) -> ProjectSettingsDialog:
        """Create an editable dialog from the latest project values."""
        return ProjectSettingsDialog(
            self.project,
            self.project_path,
            self.apply_project_settings,
            self,
        )

    def show_project_settings(self) -> None:
        self.create_project_settings_dialog().exec()

    def apply_project_settings(self, values: ProjectSettingsValues) -> bool:
        """Validate and atomically apply general and canvas settings."""
        size_changed = (values.width, values.height) != (
            self.project.width,
            self.project.height,
        )
        general_changed = (
            values.name != self.project.name
            or values.fps != self.project.fps
            or values.loop != self.project.loop
        )
        if not size_changed and not general_changed:
            return True
        if size_changed and self._canvas_change_needs_confirmation(values):
            if not self._confirm_canvas_change(values):
                return False
        if size_changed:
            try:
                if values.resize_mode is CanvasResizeMode.SCALE:
                    scale_project(self.project, values.width, values.height)
                else:
                    resize_canvas(
                        self.project, values.width, values.height, values.anchor
                    )
            except CanvasResizeError as exc:
                QMessageBox.critical(self, "Canvas Resize Failed", str(exc))
                return False
        self.project.name = values.name
        self.project.fps = values.fps
        self.project.loop = values.loop
        if self.play_timer.isActive():
            self.play_timer.setInterval(max(1, round(1000 / values.fps)))
        self._mark_dirty()
        self._refresh_all()
        return True

    def _canvas_change_needs_confirmation(
        self, values: ProjectSettingsValues
    ) -> bool:
        return (
            values.width < self.project.width
            or values.height < self.project.height
            or values.resize_mode is CanvasResizeMode.SCALE
            or self.dirty
        )

    def _confirm_canvas_change(self, values: ProjectSettingsValues) -> bool:
        answer = QMessageBox.question(
            self,
            "Confirm Canvas Change",
            f"Current size: {self.project.width} × {self.project.height}\n"
            f"New size: {values.width} × {values.height}\n"
            f"Mode: {values.resize_mode.value}\n\n"
            "This operation may crop or replace pixel data and cannot currently be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def create_playback_test(self) -> None:
        """Replace the current project with the built-in playback diagnostic."""
        if not self._confirm_discard():
            return
        self.set_playing(False)
        self.project = create_playback_test_project()
        self.project_path = None
        self.frame_index = self.layer_index = 0
        self.dirty = True
        self._refresh_all()
        self.statusBar().showMessage("Playback test project created", 3000)

    def show_keyboard_shortcuts(self) -> None:
        dialog = KeyboardShortcutsDialog(self.shortcuts, self)
        dialog.shortcuts_applied.connect(self.apply_shortcuts)
        dialog.exec()

    def apply_shortcuts(self, shortcuts: dict[str, str]) -> bool:
        """Persist shortcuts and update their QAction menu entries immediately."""
        try:
            normalized = self.settings_service.save(shortcuts)
        except (SettingsError, ValueError) as exc:
            QMessageBox.warning(self, "Shortcut Settings", str(exc))
            return False
        self.shortcuts = normalized
        self._update_action_shortcuts(normalized)
        return True

    def _update_action_shortcuts(self, shortcuts: dict[str, str]) -> None:
        for key, action in self.shortcut_actions.items():
            action.setShortcut(QKeySequence(shortcuts.get(key, "")))

    def add_frame(self) -> None:
        """Insert a transparent frame after the current frame and select it."""
        self.project.insert_empty_frame(self.frame_index)
        self.frame_index += 1
        self._mark_dirty()
        self._refresh_all()

    def duplicate_frame(self) -> None:
        """Duplicate the current frame immediately after it and select the copy."""
        self.project.duplicate_frame(self.frame_index)
        self.frame_index += 1
        self._mark_dirty()
        self._refresh_all()

    def delete_frame(self) -> None:
        try:
            self.project.delete_frame(self.frame_index)
        except ProjectError as exc:
            QMessageBox.information(self, "Cannot Delete Frame", str(exc))
            return
        self.frame_index = min(self.frame_index, len(self.project.frames) - 1)
        self._mark_dirty()
        self._refresh_all()

    def add_layer(self) -> None:
        """Add the next collision-free default layer and select it."""
        self.project.add_layer()
        self.layer_index = len(self.project.layers) - 1
        self._mark_dirty()
        self._refresh_all()

    def delete_layer(self) -> None:
        try:
            self.project.delete_layer(self.layer_index)
        except ProjectError as exc:
            QMessageBox.information(self, "Cannot Delete Layer", str(exc))
            return
        self.layer_index = min(self.layer_index, len(self.project.layers) - 1)
        self._mark_dirty()
        self._refresh_all()

    def select_cell(self, layer_index: int, frame_index: int) -> None:
        """Synchronize a timeline cell selection with the canvas."""
        if not (0 <= layer_index < len(self.project.layers)):
            return
        if not (0 <= frame_index < len(self.project.frames)):
            return
        self.layer_index = layer_index
        self.frame_index = frame_index
        self.canvas.set_layer(layer_index)
        self.canvas.set_frame(frame_index)
        self.timeline.set_current_cell(self.project, layer_index, frame_index)
        self._refresh_selection_status()

    def select_frame(self, index: int) -> None:
        if 0 <= index < len(self.project.frames):
            self.frame_index = index
            self.canvas.set_frame(index)
            self.timeline.set_current_cell(self.project, self.layer_index, index)
            self._refresh_selection_status()

    def set_fps(self, value: int) -> None:
        if self.project.fps != value:
            self.project.fps = value
            self._mark_dirty()
        if self.play_timer.isActive():
            self.play_timer.setInterval(max(1, round(1000 / value)))

    def set_playing(self, playing: bool) -> None:
        if self.play_action.isChecked() != playing:
            with QSignalBlocker(self.play_action):
                self.play_action.setChecked(playing)
        if playing:
            self.play_timer.start(max(1, round(1000 / self.project.fps)))
        else:
            self.play_timer.stop()
        self.timeline.set_playing(playing)

    def _advance_playback(self) -> None:
        next_index = self.frame_index + 1
        if next_index >= len(self.project.frames):
            if self.project.loop:
                next_index = 0
            else:
                self.set_playing(False)
                return
        self.select_frame(next_index)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
