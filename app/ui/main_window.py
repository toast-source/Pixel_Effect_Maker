"""Main application window and UI orchestration."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy

from PySide6.QtCore import QSignalBlocker, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QSplitter,
    QStackedWidget,
    QPushButton,
)

from app.models.effect_generator import TransformEmitter, TransformEmitterSettings
from app.models.frame import empty_pixels
from app.models.project import Project, ProjectError
from app.models.source_asset import SourceAsset
from app.models.particle_emitter import ParticleEmitter, ParticleEmitterSettings
from app.services.clip_service import create_clip_from_generator, update_clip_from_generator
from app.services.particle_render_service import apply_particle_frames, render_particle_frames
from app.services.particle_preview_service import ParticlePreviewManager
from app.services.preview_export_service import export_preview_sequence
from app.services.export_service import ExportError, export_png_frames
from app.services.effect_render_service import (
    EffectRenderError,
    apply_rendered_frames,
    generate_emitter,
)
from app.services.preview_service import (
    PreviewManager,
    PreviewRenderSnapshot,
    render_preview_snapshot,
)
from app.services.localization_service import LocalizationService
from app.services.project_io import ProjectIOError, load_project, save_project
from app.services.canvas_resize_service import (
    CanvasResizeError,
    CanvasResizeMode,
    resize_canvas,
    scale_project,
)
from app.services.sample_project_service import create_playback_test_project
from app.services.source_import_service import SourceImportError, import_source_asset
from app.services.resource_import_service import ResourceImportError, import_resource
from app.services.aseprite_import_service import import_aseprite
from app.services.aseprite_locator_service import locate_aseprite, validate_aseprite
from app.services.resource_composition_render_service import invalidate_composition_cache
from app.services.settings_service import SettingsError, ShortcutSettingsService
from app.shortcuts import DEFAULT_SHORTCUTS
from app.version import get_display_name

from .canvas_widget import CanvasWidget
from .effect_library_panel import EffectLibraryPanel
from .effect_properties_panel import EffectPropertiesPanel
from .particle_properties_panel import ParticlePropertiesPanel
from .frame_shortcut_controller import FrameShortcutController
from .keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from .new_project_dialog import NewProjectDialog
from .playback_shortcut_controller import PlaybackShortcutController
from .project_settings_dialog import ProjectSettingsDialog, ProjectSettingsValues
from .timeline_widget import TimelineWidget
from .resource_editor_v2 import ResourceEditorWidget
from .external_tools_dialog import ExternalToolsDialog
from .interface_settings_dialog import InterfaceSettingsDialog, timeline_frame_width
from .undo_commands import EditorOperationCommand, EditorValueCommand


class MainWindow(QMainWindow):
    """Coordinate project state, services, and editor widgets."""

    def __init__(
        self, settings_service: ShortcutSettingsService | None = None, initial_project: Project | None = None
    ) -> None:
        super().__init__()
        self.setWindowTitle(get_display_name())
        self.resize(1280, 800)
        self.project = initial_project or Project.create_default()
        self.project_path: Path | None = None
        self.frame_index = 0
        self.layer_index = 0
        self.dirty = False
        self._non_undo_dirty=False
        self.settings_service = settings_service or ShortcutSettingsService()
        self.localization = LocalizationService(self.settings_service.settings)
        self.application_undo_stack = QUndoStack(self)
        self.preview_manager = PreviewManager(
            self.settings_service.settings, parent=self
        )
        self.particle_preview_manager = ParticlePreviewManager(self)
        self.active_preview_generator_id: str | None = None
        try:
            self.shortcuts = self.settings_service.load()
        except SettingsError:
            self.shortcuts = dict(DEFAULT_SHORTCUTS)
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance_playback)

        self._build_ui()
        self._build_menus()
        self.resource_editor.set_undo_stack(self.application_undo_stack)
        self.application_undo_stack.indexChanged.connect(self._undo_index_changed)
        self._connect_signals()
        self.playback_shortcut_controller = PlaybackShortcutController(
            self, self.toggle_workspace_playback
        )
        self.playback_shortcut_controller.set_sequences(
            self.shortcuts.get("play_stop_animation", [])
        )
        self.frame_shortcut_controller = FrameShortcutController(
            self,
            self.previous_workspace_frame,
            self.next_workspace_frame,
            [self.timeline.table,self.resource_editor.composition_timeline.table,self.resource_editor.asset_strip],
        )
        self.frame_shortcut_controller.set_sequences(self.shortcuts)
        self.localization.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()
        self._refresh_all()

    def _build_ui(self) -> None:
        outer = QWidget(); outer_layout = QVBoxLayout(outer); outer_layout.setContentsMargins(4,4,4,4)
        workspace_row=QHBoxLayout();self.effect_workspace_button=QPushButton("Effect Editor");self.resource_workspace_button=QPushButton("Resource Editor")
        for button in (self.effect_workspace_button,self.resource_workspace_button):button.setCheckable(True);workspace_row.addWidget(button)
        workspace_row.addStretch();outer_layout.addLayout(workspace_row);self.workspace_stack=QStackedWidget();outer_layout.addWidget(self.workspace_stack,1)
        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(4, 4, 4, 4)
        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor_splitter.setObjectName("editorSplitter")
        self.editor_splitter.setChildrenCollapsible(False)
        self.effect_library = EffectLibraryPanel()
        self.editor_splitter.addWidget(self.effect_library)
        self.canvas = CanvasWidget()
        self.editor_splitter.addWidget(self.canvas)
        self.effect_properties = EffectPropertiesPanel()
        self.effect_properties.auto_preview_check.setChecked(
            self.preview_manager.auto_preview
        )
        self.particle_properties = ParticlePropertiesPanel()
        self.properties_stack = QStackedWidget(); self.properties_stack.setMinimumWidth(360)
        self.properties_stack.addWidget(self.effect_properties); self.properties_stack.addWidget(self.particle_properties)
        self.editor_splitter.addWidget(self.properties_stack)
        self.editor_splitter.setStretchFactor(0, 0)
        self.editor_splitter.setStretchFactor(1, 1)
        self.editor_splitter.setStretchFactor(2, 0)
        self._restore_splitter_sizes()
        self.editor_splitter.splitterMoved.connect(self._save_splitter_sizes)
        root_layout.addWidget(self.editor_splitter, 1)
        self.timeline = TimelineWidget()
        self.timeline.set_frame_cell_width(timeline_frame_width(self.settings_service.settings))
        root_layout.addWidget(self.timeline)
        self.resource_editor=ResourceEditorWidget(self.settings_service.settings)
        self.workspace_stack.addWidget(container);self.workspace_stack.addWidget(self.resource_editor);self.workspace_stack.setCurrentIndex(0);self.effect_workspace_button.setChecked(True)
        self.effect_workspace_button.clicked.connect(lambda:self.set_workspace("effect"));self.resource_workspace_button.clicked.connect(lambda:self.set_workspace("resource"))
        self.setCentralWidget(outer)

    def set_workspace(self, workspace: str) -> None:
        resource=workspace=="resource"
        if resource:self.resource_editor.refresh(self.project)
        self.workspace_stack.setCurrentIndex(1 if resource else 0);self.effect_workspace_button.setChecked(not resource);self.resource_workspace_button.setChecked(resource);self.settings_service.settings.setValue("ui/workspace",workspace)

    def toggle_workspace_playback(self) -> None:
        if self.workspace_stack.currentIndex()==1:self.resource_editor.toggle_play()
        else:self.play_action.trigger()

    def previous_workspace_frame(self) -> None:
        if self.workspace_stack.currentIndex()==1:self.resource_editor.previous_frame()
        else:self.previous_frame()

    def next_workspace_frame(self) -> None:
        if self.workspace_stack.currentIndex()==1:self.resource_editor.next_frame()
        else:self.next_frame()

    def _restore_splitter_sizes(self) -> None:
        value = self.settings_service.settings.value("ui/editor_splitter_sizes")
        try:
            sizes = [int(item) for item in value] if isinstance(value, (list, tuple)) else []
        except (TypeError, ValueError):
            sizes = []
        if len(sizes) != 3 or min(sizes) < 100 or sizes[2] < 340:
            sizes = [230, 680, 370]
        self.editor_splitter.setSizes(sizes)

    def _save_splitter_sizes(self, *args) -> None:
        sizes = self.editor_splitter.sizes()
        if len(sizes) == 3 and sizes[2] >= 340:
            self.settings_service.settings.setValue("ui/editor_splitter_sizes", sizes)

    def _build_menus(self) -> None:
        self.file_menu = self.menuBar().addMenu("File")
        self.new_action = QAction("New Project…", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.open_action = QAction("Open…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.project_settings_action = QAction("Project Settings…", self)
        self.exit_action=QAction("Exit",self)
        self.import_source_action = QAction("Import Source Asset…", self)
        self.import_resources_action = QAction("Import Resources…", self)
        self.external_tools_action = QAction("External Tools…", self)
        self.playback_test_action = QAction("Create Playback Test Project", self)
        self.playback_test_action.setStatusTip(
            "Create an 8-frame sample project for checking animation playback."
        )
        self.export_action = QAction("Export PNG Frames…", self)
        self.file_menu.addActions(
            [self.new_action, self.open_action, self.save_action, self.save_as_action]
        )
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.import_source_action)
        self.file_menu.addAction(self.import_resources_action)
        self.file_menu.addSeparator();self.file_menu.addAction(self.exit_action)

        self.edit_menu = self.menuBar().addMenu("Edit")
        self.undo_action=self.application_undo_stack.createUndoAction(self)
        self.redo_action=self.application_undo_stack.createRedoAction(self)
        self.undo_action.setShortcuts([QKeySequence("Ctrl+Z")]);self.redo_action.setShortcuts([QKeySequence("Ctrl+Shift+Z"),QKeySequence("Ctrl+Y")])
        self.keyboard_shortcuts_action = QAction("Keyboard Shortcuts…", self)
        self.edit_menu.addActions([self.undo_action,self.redo_action]);self.edit_menu.addSeparator();self.edit_menu.addAction(self.project_settings_action);self.edit_menu.addAction(self.keyboard_shortcuts_action)

        self.layer_menu = self.menuBar().addMenu("Layer")
        self.new_layer_action = QAction("New Layer", self)
        self.delete_layer_action = QAction("Delete Layer", self)
        self.layer_menu.addActions([self.new_layer_action, self.delete_layer_action])

        self.frame_menu = self.menuBar().addMenu("Frame")
        self.new_frame_action = QAction("New Frame (Duplicate Current)", self)
        self.new_empty_frame_action = QAction("New Empty Frame", self)
        self.delete_frame_action = QAction("Delete Frame", self)
        self.frame_menu.addActions(
            [
                self.new_frame_action,
                self.new_empty_frame_action,
                self.delete_frame_action,
            ]
        )

        self.animation_menu = self.menuBar().addMenu("Animation")
        self.play_action = QAction("Play / Stop Animation", self, checkable=True)

        self.view_menu = self.menuBar().addMenu("View")
        self.status_bar_action = QAction("Status Bar", self, checkable=True)
        self.status_bar_action.setChecked(True)
        self.view_menu.addAction(self.status_bar_action)

        self.export_menu = self.menuBar().addMenu("Export")
        self.export_menu.addAction(self.export_action)

        self.settings_menu = self.menuBar().addMenu("Settings")
        self.interface_settings_action=QAction("Interface Settings…",self)
        self.language_menu = self.settings_menu.addMenu("Language")
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self.korean_action = QAction("한국어", self, checkable=True)
        self.english_action = QAction("English", self, checkable=True)
        self.language_group.addAction(self.korean_action)
        self.language_group.addAction(self.english_action)
        self.language_menu.addActions([self.korean_action, self.english_action])
        self.settings_menu.addSeparator();self.settings_menu.addAction(self.interface_settings_action);self.settings_menu.addAction(self.external_tools_action)
        self.korean_action.triggered.connect(
            lambda: self.localization.set_language("ko")
        )
        self.english_action.triggered.connect(
            lambda: self.localization.set_language("en")
        )

        # Compatibility aliases for the existing action-oriented tests and code.
        self.add_layer_action = self.new_layer_action
        self.duplicate_frame_action = self.new_frame_action
        self.add_frame_action = self.new_empty_frame_action
        self.shortcut_actions = {
            "undo": self.undo_action,
            "redo": self.redo_action,
            "new_layer": self.new_layer_action,
            "new_frame": self.new_frame_action,
            "new_empty_frame": self.new_empty_frame_action,
        }
        self._update_action_shortcuts(self.shortcuts)

    def retranslate_ui(self, *args) -> None:
        t = self.localization.text
        self.file_menu.setTitle(t("menu.file"))
        self.edit_menu.setTitle(t("menu.edit"))
        self.layer_menu.setTitle(t("menu.layer"))
        self.frame_menu.setTitle(t("menu.frame"))
        self.animation_menu.setTitle(t("menu.animation"))
        self.view_menu.setTitle(t("menu.view"))
        self.export_menu.setTitle(t("menu.export"))
        self.settings_menu.setTitle(t("menu.settings"))
        self.language_menu.setTitle(t("menu.language"))
        mapping = {
            self.new_action: "action.new_project",
            self.open_action: "action.open",
            self.save_action: "action.save",
            self.save_as_action: "action.save_as",
            self.project_settings_action: "action.project_settings",
            self.exit_action: "action.exit",
            self.import_source_action: "action.import_source",
            self.import_resources_action: "resource.import",
            self.external_tools_action: "external.title",
            self.playback_test_action: "action.playback_test",
            self.export_action: "action.export_frames",
            self.keyboard_shortcuts_action: "action.keyboard_shortcuts",
            self.new_layer_action: "action.new_layer",
            self.delete_layer_action: "action.delete_layer",
            self.new_frame_action: "action.new_frame",
            self.new_empty_frame_action: "action.new_empty_frame",
            self.delete_frame_action: "action.delete_frame",
            self.play_action: "action.play_stop",
            self.status_bar_action: "action.status_bar",
            self.interface_settings_action: "interface.title",
        }
        for action, key in mapping.items():
            action.setText(t(key))
        self.korean_action.setText(t("language.ko"))
        self.english_action.setText(t("language.en"))
        self.korean_action.setChecked(self.localization.language == "ko")
        self.english_action.setChecked(self.localization.language == "en")
        self.effect_library.retranslate_ui(self.localization)
        self.effect_properties.retranslate_ui(self.localization)
        self.particle_properties.retranslate_ui(self.localization)
        self.resource_editor.retranslate_ui(self.localization)
        self.effect_workspace_button.setText(t("workspace.effect"));self.resource_workspace_button.setText(t("workspace.resource"))
        self.timeline.retranslate_ui(self.localization)
        self.undo_action.setText(t("action.undo") if not self.application_undo_stack.undoText() else t("action.undo_named").format(name=self.application_undo_stack.undoText()))
        self.redo_action.setText(t("action.redo") if not self.application_undo_stack.redoText() else t("action.redo_named").format(name=self.application_undo_stack.redoText()))
        self.undo_action.setToolTip(t("tooltip.undo"));self.undo_action.setStatusTip(t("tooltip.undo"));self.redo_action.setToolTip(t("tooltip.redo"));self.redo_action.setStatusTip(t("tooltip.redo"))
        self.canvas.preview_badge_text = t("effects.preview_badge")
        self.canvas.update()
        self._refresh_playback_status()

    def _connect_signals(self) -> None:
        self.new_action.triggered.connect(self.new_project)
        self.open_action.triggered.connect(self.open_project)
        self.save_action.triggered.connect(self.save)
        self.save_as_action.triggered.connect(self.save_as)
        self.project_settings_action.triggered.connect(self.show_project_settings)
        self.exit_action.triggered.connect(self.close)
        self.import_source_action.triggered.connect(self.import_source_asset)
        self.import_resources_action.triggered.connect(self.import_resources)
        self.external_tools_action.triggered.connect(self.show_external_tools)
        self.interface_settings_action.triggered.connect(self.show_interface_settings)
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
        self.timeline.scrub_started.connect(lambda: self.set_playing(False))
        self.timeline.play_requested.connect(self.play_action.trigger)
        self.timeline.fps_changed.connect(self.set_fps)
        self.timeline.layer_visibility_requested.connect(self.set_layer_visibility)
        self.effect_library.import_requested.connect(self.import_source_asset)
        self.effect_library.add_emitter_requested.connect(self.add_transform_emitter)
        self.effect_library.asset_selected.connect(self.select_source_asset)
        self.effect_library.generator_selected.connect(self.select_generator)
        self.effect_library.delete_asset_requested.connect(self.delete_source_asset)
        self.effect_library.delete_generator_requested.connect(self.delete_generator)
        self.effect_library.create_clip_requested.connect(self.create_animation_clip)
        self.effect_library.add_particle_requested.connect(self.add_particle_emitter)
        self.effect_library.clip_selected.connect(self.select_animation_clip)
        self.effect_library.particle_selected.connect(self.select_particle_emitter)
        self.effect_library.resource_open_requested.connect(self.open_resource_editor)
        self.effect_properties.generate_requested.connect(self.generate_effect)
        self.effect_properties.reset_requested.connect(self.reset_generator_settings)
        self.effect_properties.draft_changed.connect(self.update_generator_draft)
        self.effect_properties.refresh_preview_requested.connect(
            self.refresh_generator_preview
        )
        self.effect_properties.revert_requested.connect(self.revert_generator_draft)
        self.effect_properties.auto_preview_changed.connect(
            self.preview_manager.set_auto_preview
        )
        self.effect_properties.gizmo_mode_changed.connect(self._set_gizmo_mode)
        self.canvas.gizmo_changed.connect(self._gizmo_changed)
        self.preview_manager.state_changed.connect(self._preview_state_changed)
        self.preview_manager.preview_ready.connect(self._preview_ready)
        self.preview_manager.preview_failed.connect(self._preview_failed)
        self.particle_properties.draft_changed.connect(self.update_particle_draft)
        self.particle_properties.refresh_requested.connect(self.refresh_particle_preview)
        self.particle_properties.bake_requested.connect(self.bake_particle_emitter)
        self.particle_properties.revert_requested.connect(self.revert_particle_draft)
        self.particle_properties.export_requested.connect(self.export_particle_preview)
        self.particle_preview_manager.preview_ready.connect(self._particle_preview_ready)
        self.particle_preview_manager.preview_failed.connect(self._particle_preview_failed)
        self.resource_editor.import_requested.connect(self.import_resources)
        self.resource_editor.pivot_changed.connect(self.update_resource_pivot)
        self.resource_editor.create_emitter_requested.connect(self.create_particle_from_resource)
        self.resource_editor.reimport_requested.connect(self.reimport_resource)
        self.resource_editor.delete_requested.connect(self.delete_resource)
        self.resource_editor.composition_changed.connect(self.resource_composition_changed)

    def _refresh_all(self) -> None:
        self.frame_index = max(0, min(self.frame_index, self._display_frame_count() - 1))
        self.layer_index = max(0, min(self.layer_index, len(self.project.layers) - 1))
        self.canvas.set_project(self.project)
        self.canvas.set_frame(self.frame_index)
        self.canvas.set_layer(self.layer_index)
        self.timeline.refresh(
            self.project,
            self.layer_index,
            self.frame_index,
            display_frame_count=self._display_frame_count(),
            preview=self.active_preview_generator_id is not None,
        )
        self.timeline.set_playing(self.play_timer.isActive())
        self._refresh_playback_status()
        self._refresh_effect_panels()
        self._update_title()
        self._refresh_selection_status()

    def _display_frame_count(self) -> int:
        if self.active_preview_generator_id and self.canvas.preview_frames is not None:
            return len(self.canvas.preview_frames)
        if self.active_preview_generator_id:
            session = self.preview_manager.current_session(
                self.active_preview_generator_id
            )
            if session is not None:
                return session.output_frame_count
        return len(self.project.frames)

    def _refresh_selection_status(self) -> None:
        self.statusBar().showMessage(
            f"{self.project.layers[self.layer_index].name} · "
            f"Frame {self.frame_index + 1}"
        )

    def _update_title(self) -> None:
        marker = "*" if self.dirty else ""
        self.setWindowTitle(f"{get_display_name()} - {self.project.name}{marker}")

    def _mark_dirty(self) -> None:
        self._non_undo_dirty=True
        self.dirty = True
        self._update_title()

    def _undo_index_changed(self, *args) -> None:
        self.dirty = self._non_undo_dirty or not self.application_undo_stack.isClean()
        self._update_title()
        self.retranslate_ui()

    def apply_undo_value(self,target_id,field,value) -> None:
        if field=="effect_visibility":
            layer=next((item for item in self.project.layers if item.id==target_id),None)
            if layer:layer.visible=bool(value);self.canvas.update();self.timeline.refresh(self.project,self.layer_index,self.frame_index,display_frame_count=self._display_frame_count(),preview=self.active_preview_generator_id is not None)
        elif field=="particle_settings":
            emitter=next((item for item in self.project.particle_emitters if item.id==target_id),None)
            if emitter:self.particle_preview_manager.update(self.project,emitter,value);self.particle_properties.set_settings(value)

    def apply_undo_operation(self,operation,state,forward) -> None:
        if operation in {"add_frame","duplicate_frame"}:
            index=state["index"]+1
            if forward:
                if "frame" not in state:state["frame"]=self.project.insert_empty_frame(state["index"]) if operation=="add_frame" else self.project.duplicate_frame(state["index"])
                else:self.project.frames.insert(index,state["frame"])
                self.frame_index=index
            else:self.project.frames.pop(index);self.frame_index=state["index"]
        elif operation=="delete_frame":
            index=state["index"]
            if forward:self.project.frames.pop(index);self.frame_index=min(index,len(self.project.frames)-1)
            else:self.project.frames.insert(index,state["frame"]);self.frame_index=index
        elif operation=="add_layer":
            if forward:
                if "layer" not in state:state["layer"]=self.project.add_layer(state["name"])
                else:
                    self.project.layers.append(state["layer"])
                    for frame in self.project.frames:frame.layer_pixels[state["layer"].id]=empty_pixels(self.project.width,self.project.height)
                self.layer_index=len(self.project.layers)-1
            else:self.project.delete_layer(len(self.project.layers)-1);self.layer_index=max(0,len(self.project.layers)-1)
        elif operation=="delete_layer":
            index=state["index"]
            if forward:self.project.delete_layer(index);self.layer_index=min(index,len(self.project.layers)-1)
            else:
                self.project.layers.insert(index,state["layer"])
                for frame,pixels in zip(self.project.frames,state["pixels"]):frame.layer_pixels[state["layer"].id]=pixels
                self.layer_index=index
        self._refresh_all()

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            self.localization.text("message.unsaved_title"),
            self.localization.text("message.discard_unsaved"),
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard

    def new_project(self) -> None:
        if not self._confirm_unapplied_previews() or not self._confirm_discard():
            return
        dialog = NewProjectDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        self.apply_new_project_settings(settings)
        self.statusBar().showMessage(self.localization.text("status.new_project"), 3000)

    def apply_new_project_settings(self, settings) -> None:
        self.set_playing(False)
        self.preview_manager.reset_context()
        self.particle_preview_manager.reset_context()
        self._clear_preview()
        self.project = Project.create_default(
            settings.name,
            settings.width,
            settings.height,
            settings.fps,
            settings.loop,
        )
        while len(self.project.frames) < settings.frame_count:
            self.project.add_frame()
        self.project_path = None
        self.application_undo_stack.clear()
        self.frame_index = self.layer_index = 0
        self.dirty = False
        self._non_undo_dirty=False
        self.set_workspace("effect")
        self._refresh_all()

    def open_project(self) -> None:
        if not self._confirm_unapplied_previews() or not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "projects", "Pixel Effect Project (*.peffect.json)"
        )
        if not path:
            return
        try:
            self.project = load_project(path)
        except ProjectIOError as exc:
            QMessageBox.critical(self, self.localization.text("error.open"), str(exc))
            return
        self.set_playing(False)
        self.preview_manager.reset_context()
        self.particle_preview_manager.reset_context()
        self._clear_preview()
        self.project_path = Path(path)
        self.application_undo_stack.clear()
        self.frame_index = self.layer_index = 0
        self.dirty = False
        self._non_undo_dirty=False
        self.application_undo_stack.setClean()
        self._refresh_all()
        saved_workspace=str(self.settings_service.settings.value("ui/workspace","effect"))
        self.set_workspace("resource" if saved_workspace=="resource" and (self.project.source_assets or self.project.animation_clips) else "effect")
        self.statusBar().showMessage(self.localization.text("status.opened").format(path=path), 4000)

    def save(self) -> bool:
        if self.project_path is None:
            return self.save_as()
        try:
            self.project_path = save_project(self.project, self.project_path)
        except ProjectIOError as exc:
            QMessageBox.critical(self, self.localization.text("error.save"), str(exc))
            return False
        self.dirty = False
        self._non_undo_dirty=False
        self.application_undo_stack.setClean()
        self._update_title()
        self.statusBar().showMessage(self.localization.text("status.saved").format(path=self.project_path), 4000)
        if self.preview_manager.dirty_generator_ids():
            self.statusBar().showMessage(
                self.localization.text("message.saved_without_preview"), 5000
            )
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
        if self.preview_manager.dirty_generator_ids():
            self.statusBar().showMessage(
                self.localization.text("message.export_without_preview"), 5000
            )
        directory = QFileDialog.getExistingDirectory(
            self, "Export PNG Frames", str(Path("exports").resolve())
        )
        if not directory:
            return
        try:
            written = export_png_frames(self.project, directory)
        except ExportError as exc:
            QMessageBox.critical(self, self.localization.text("error.export"), str(exc))
            return
        QMessageBox.information(
            self, "Export Complete", f"Exported {len(written)} PNG frame(s)."
        )

    def set_layer_visibility(self, index: int, visible: bool) -> None:
        if not 0 <= index < len(self.project.layers): return
        layer=self.project.layers[index];self.application_undo_stack.push(EditorValueCommand(self,layer.id,"effect_visibility",layer.visible,bool(visible),"Layer Visibility"))

    def import_source_asset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Source Asset", "", "PNG Images (*.png)"
        )
        if path:
            self.import_source_asset_path(path)

    def show_external_tools(self) -> None:
        ExternalToolsDialog(self.settings_service.settings,self.localization,self).exec()

    def import_resources(self, paths=None) -> list:
        if isinstance(paths,bool) or paths is None:
            paths,_=QFileDialog.getOpenFileNames(self,self.localization.text("resource.import"),"","Resources (*.png *.gif *.ase *.aseprite)")
        if not paths:return []
        imported=[];failures=[]
        for value in paths:
            path=Path(value)
            try:
                if path.suffix.lower() in {".ase",".aseprite"}:
                    executable=locate_aseprite(self.settings_service.settings)
                    if executable is None:
                        dialog=ExternalToolsDialog(self.settings_service.settings,self.localization,self)
                        if dialog.exec()!=QDialog.DialogCode.Accepted:raise ResourceImportError("Aseprite executable was not configured")
                        executable=locate_aseprite(self.settings_service.settings)
                    if executable is None:raise ResourceImportError("Aseprite executable was not found")
                    resource=import_aseprite(path,executable)
                else:resource=import_resource(path)
                all_names={r.name for r in self.project.source_assets}|{r.name for r in self.project.animation_clips};base=resource.name;number=2
                while resource.name in all_names:resource.name=f"{Path(base).stem} ({number}){Path(base).suffix}";number+=1
                (self.project.source_assets if isinstance(resource,SourceAsset) else self.project.animation_clips).append(resource);imported.append(resource)
            except (ResourceImportError,OSError,ValueError) as exc:failures.append(f"{path.name}: {exc}")
        if imported:
            self._mark_dirty();first=imported[0];kind="source_asset" if isinstance(first,SourceAsset) else "animation_clip";self.resource_editor.refresh(self.project,(kind,first.id));self.set_workspace("resource");self._refresh_effect_panels()
        message=self.localization.text("resource.import_summary").format(success=len(imported),failed=len(failures));self.statusBar().showMessage(message,6000)
        if failures:QMessageBox.warning(self,self.localization.text("resource.import"),message+"\n"+"\n".join(failures))
        return imported

    def update_resource_pivot(self,kind: str,identifier: str,x: float,y: float) -> None:
        resources=self.project.source_assets if kind=="source_asset" else self.project.animation_clips;resource=next((r for r in resources if r.id==identifier),None)
        if resource is None:return
        resource.pivot_x=float(x);resource.pivot_y=float(y)
        for generator in self.project.generators:
            if kind=="source_asset" and generator.settings.source_asset_id==identifier:self.preview_manager.sessions.pop(generator.id,None)
        for emitter in self.project.particle_emitters:
            if emitter.settings.resource_type==kind and emitter.settings.resource_id==identifier:self.particle_preview_manager.sessions.pop(emitter.id,None)
        self._mark_dirty();self.statusBar().showMessage(self.localization.text("resource.preview_invalidated"),4000)

    def create_particle_from_resource(self,kind: str,identifier: str):
        if kind=="animation_clip":emitter=self.add_particle_emitter(identifier)
        elif kind=="resource_composition":
            composition=next((r for r in self.project.resource_compositions if r.id==identifier),None)
            if composition is None:return None
            emitter=ParticleEmitter(name=f"Particle Emitter {len(self.project.particle_emitters)+1}",settings=ParticleEmitterSettings(identifier,resource_type="resource_composition",origin_x=self.project.width/2,origin_y=self.project.height/2));self.project.particle_emitters.append(emitter);self._mark_dirty();self.effect_library.refresh(self.project)
        else:
            source=next((r for r in self.project.source_assets if r.id==identifier),None)
            if source is None:return None
            emitter=ParticleEmitter(name=f"Particle Emitter {len(self.project.particle_emitters)+1}",settings=ParticleEmitterSettings(identifier,resource_type="source_asset",origin_x=self.project.width/2,origin_y=self.project.height/2));self.project.particle_emitters.append(emitter);self._mark_dirty();self.effect_library.refresh(self.project)
        if emitter:self.set_workspace("effect");self.select_particle_emitter(emitter.id);self.particle_preview_manager.ensure_draft(emitter);self.particle_preview_manager.schedule(self.project,emitter.id)
        return emitter

    def resource_composition_changed(self,identifier: str) -> None:
        """Invalidate only previews that consume the edited composition."""
        if not self.resource_editor._applying_command:self._mark_dirty()
        for emitter in self.project.particle_emitters:
            if emitter.settings.resource_type=="resource_composition" and emitter.settings.resource_id==identifier:
                self.particle_preview_manager.sessions.pop(emitter.id,None)
        self._refresh_effect_panels()

    def reimport_resource(self,kind: str,identifier: str) -> bool:
        resources=self.project.source_assets if kind=="source_asset" else self.project.animation_clips;old=next((r for r in resources if r.id==identifier),None)
        if old is None:return False
        path=Path(old.source_path) if old.source_path else None
        if path is None or not path.exists():
            selected,_=QFileDialog.getOpenFileName(self,self.localization.text("resource.reimport"),"","Resources (*.png *.gif *.ase *.aseprite)")
            if not selected:return False
            path=Path(selected)
        try:
            if path.suffix.lower() in {".ase",".aseprite"}:
                executable=locate_aseprite(self.settings_service.settings)
                if executable is None:raise ResourceImportError("Aseprite executable was not found")
                new=import_aseprite(path,executable)
            else:new=import_resource(path)
            if (kind=="source_asset") != isinstance(new,SourceAsset):raise ResourceImportError("the selected file has a different resource type")
        except (ResourceImportError,OSError,ValueError) as exc:QMessageBox.warning(self,self.localization.text("resource.reimport"),str(exc));return False
        new.id=old.id;new.name=old.name;new.pivot_x=old.pivot_x;new.pivot_y=old.pivot_y;resources[resources.index(old)]=new
        for composition in self.project.resource_compositions:
            if any(layer.source_type==kind and layer.source_id==new.id for layer in composition.layers):composition.touch();invalidate_composition_cache(composition.id)
        self.update_resource_pivot(kind,new.id,new.pivot_x,new.pivot_y);self.resource_editor.refresh(self.project,(kind,new.id));return True

    def delete_resource(self,kind: str,identifier: str) -> bool:
        used=(kind=="source_asset" and any(g.settings.source_asset_id==identifier for g in self.project.generators)) or any(e.settings.resource_type==kind and e.settings.resource_id==identifier for e in self.project.particle_emitters)
        if used:QMessageBox.warning(self,self.localization.text("resource.delete"),self.localization.text("resource.in_use"));return False
        resources=self.project.source_assets if kind=="source_asset" else self.project.animation_clips;resource=next((r for r in resources if r.id==identifier),None)
        if resource is None:return False
        if QMessageBox.question(self,self.localization.text("resource.delete"),self.localization.text("resource.delete_confirm"))!=QMessageBox.StandardButton.Yes:return False
        resources.remove(resource);self._mark_dirty();self.resource_editor.resource=None;self.resource_editor.refresh(self.project);self._refresh_effect_panels();return True

    def import_source_asset_path(self, path: str | Path) -> SourceAsset | None:
        """Import and register one embedded source; exposed for UI-level tests."""
        try:
            asset = import_source_asset(path)
        except SourceImportError as exc:
            QMessageBox.critical(self, self.localization.text("error.import"), str(exc))
            return None
        self.project.source_assets.append(asset)
        self._mark_dirty()
        self.effect_library.refresh(self.project)
        self.effect_library.select_asset(asset.id)
        self.select_source_asset(asset.id)
        self.statusBar().showMessage(self.localization.text("status.imported").format(name=asset.name), 4000)
        return asset

    def add_transform_emitter(self) -> TransformEmitter | None:
        if not self.project.source_assets:
            QMessageBox.information(
                self, "Transform Emitter", "Import a Source Asset first."
            )
            return None
        asset_id = self.effect_library.current_asset_id()
        if asset_id not in {item.id for item in self.project.source_assets}:
            asset_id = self.project.source_assets[0].id
        number = 1
        names = {item.name for item in self.project.generators}
        while f"Transform Emitter {number}" in names:
            number += 1
        emitter = TransformEmitter(
            name=f"Transform Emitter {number}",
            settings=TransformEmitterSettings(
                source_asset_id=asset_id,
                origin_x=self.project.width / 2.0,
                origin_y=self.project.height / 2.0,
                line_end_x=self.project.width * 0.75,
                line_end_y=self.project.height / 2.0,
                radius=min(self.project.width, self.project.height) / 4.0,
            ),
        )
        self.project.generators.append(emitter)
        self._mark_dirty()
        self.effect_library.refresh(self.project)
        self.effect_library.select_generator(emitter.id)
        self.select_generator(emitter.id)
        return emitter

    def select_source_asset(self, asset_id: str) -> None:
        asset = next(
            (item for item in self.project.source_assets if item.id == asset_id), None
        )
        self.effect_library.show_asset(asset)
        self.effect_properties.set_generator(None, self.project)
        self.properties_stack.setCurrentWidget(self.effect_properties)

    def select_generator(self, generator_id: str) -> None:
        self.properties_stack.setCurrentWidget(self.effect_properties)
        generator = next(
            (item for item in self.project.generators if item.id == generator_id), None
        )
        self.effect_properties.set_generator(generator, self.project)
        if generator is None:
            self._clear_preview()
            return
        draft = self.preview_manager.ensure_draft(generator)
        self.effect_properties.set_settings(draft.settings)
        self._set_gizmo_mode(self.effect_properties.current_gizmo_mode(), self.effect_properties.edit_end_check.isChecked())
        session = self.preview_manager.current_session(generator.id)
        if session is not None:
            self._activate_preview(generator, session.frames)
            self.effect_properties.set_preview_state("ready")
        else:
            self._clear_preview()
            self.effect_properties.set_preview_state(
                "settings_changed" if draft.is_dirty else "applied"
            )

    def create_animation_clip(self, generator_id: str):
        generator = next((g for g in self.project.generators if g.id == generator_id), None)
        if generator is None: return None
        try: clip = create_clip_from_generator(self.project, generator)
        except ValueError as exc:
            QMessageBox.information(self, self.localization.text("effects.create_clip"), str(exc)); return None
        self._mark_dirty(); self.effect_library.refresh(self.project); self.statusBar().showMessage(self.localization.text("status.created").format(name=clip.name), 4000); return clip

    def update_animation_clip(self, clip_id: str, generator_id: str) -> bool:
        clip=next((c for c in self.project.animation_clips if c.id==clip_id),None); generator=next((g for g in self.project.generators if g.id==generator_id),None)
        if clip is None or generator is None:return False
        try:update_clip_from_generator(self.project,clip,generator)
        except ValueError:return False
        for emitter in self.project.particle_emitters:
            if emitter.settings.clip_asset_id==clip.id:self.particle_preview_manager.sessions.pop(emitter.id,None)
        self._mark_dirty(); return True

    def select_animation_clip(self, clip_id: str) -> None:
        self._clear_preview(); self.canvas.set_gizmo(None); self.properties_stack.setCurrentWidget(self.effect_properties); self.effect_properties.set_generator(None,self.project)

    def open_resource_editor(self,kind: str,identifier: str) -> None:
        self.set_workspace("resource");self.resource_editor.select_resource(kind,identifier)

    def add_particle_emitter(self, clip_id: str):
        clip=next((c for c in self.project.animation_clips if c.id==clip_id),None)
        if clip is None:return None
        emitter=ParticleEmitter(name=f"Particle Emitter {len(self.project.particle_emitters)+1}",settings=ParticleEmitterSettings(clip_asset_id=clip.id,origin_x=self.project.width/2,origin_y=self.project.height/2,line_end_x=self.project.width*.75,line_end_y=self.project.height/2,radius=min(self.project.width,self.project.height)/4))
        self.project.particle_emitters.append(emitter); self._mark_dirty(); self.effect_library.refresh(self.project); self.select_particle_emitter(emitter.id); return emitter

    def select_particle_emitter(self, emitter_id: str) -> None:
        emitter=next((e for e in self.project.particle_emitters if e.id==emitter_id),None); self.properties_stack.setCurrentWidget(self.particle_properties); self.particle_properties.set_emitter(emitter,self.project)
        if emitter is None:return
        draft=self.particle_preview_manager.ensure_draft(emitter); self.particle_properties.set_settings(draft.settings)
        session=self.particle_preview_manager.sessions.get(emitter.id)
        if session:self._activate_particle_preview(emitter,session.frames)
        else:self._clear_preview()

    def update_particle_draft(self, emitter_id: str, settings: ParticleEmitterSettings) -> None:
        emitter=next((e for e in self.project.particle_emitters if e.id==emitter_id),None)
        if emitter:
            draft=self.particle_preview_manager.ensure_draft(emitter);before=draft.settings
            self.application_undo_stack.push(EditorValueCommand(self,emitter_id,"particle_settings",before,settings,"Particle Settings",700))

    def refresh_particle_preview(self, emitter_id: str) -> None:
        emitter=next((e for e in self.project.particle_emitters if e.id==emitter_id),None)
        if emitter:
            if emitter_id not in self.particle_preview_manager.drafts:self.particle_preview_manager.ensure_draft(emitter)
            self.particle_preview_manager.schedule(self.project,emitter_id)

    def _particle_preview_ready(self, emitter_id: str, revision: int, frames: list) -> None:
        if self.particle_properties.emitter_id!=emitter_id:return
        emitter=next((e for e in self.project.particle_emitters if e.id==emitter_id),None)
        if emitter:self._activate_particle_preview(emitter,frames)

    def _activate_particle_preview(self, emitter, frames):
        self.active_preview_generator_id=emitter.id; self.canvas.set_preview(frames,emitter.generated_layer_id); self.canvas.set_gizmo(None); self.frame_index=min(self.frame_index,len(frames)-1); self.timeline.refresh(self.project,self.layer_index,self.frame_index,display_frame_count=len(frames),preview=True); self._refresh_playback_status()

    def _particle_preview_failed(self, emitter_id: str, revision: int, message: str) -> None:
        if self.particle_properties.emitter_id==emitter_id:self.statusBar().showMessage(message,5000)

    def revert_particle_draft(self, emitter_id: str) -> None:
        emitter=next((e for e in self.project.particle_emitters if e.id==emitter_id),None)
        if emitter:self.particle_properties.set_settings(self.particle_preview_manager.revert(emitter).settings); self._clear_preview()

    def bake_particle_emitter(self, emitter_id: str, settings: ParticleEmitterSettings) -> bool:
        emitter=next((e for e in self.project.particle_emitters if e.id==emitter_id),None)
        if emitter is None:return False
        draft=self.particle_preview_manager.update(self.project,emitter,settings,immediate=True); session=self.particle_preview_manager.sessions.get(emitter_id)
        try: outputs=[f.copy() for f in session.frames] if session and session.revision==draft.revision else render_particle_frames(self.project,ParticleEmitter(id=emitter.id,name=emitter.name,settings=deepcopy(settings))); layer=apply_particle_frames(self.project,emitter,outputs)
        except (ValueError,MemoryError) as exc: QMessageBox.critical(self,self.localization.text("effects.bake"),str(exc)); return False
        emitter.settings=deepcopy(settings); self.particle_preview_manager.mark_applied(emitter); self._clear_preview(); self.layer_index=self.project.layers.index(layer); self._mark_dirty(); self._refresh_all(); return True

    def export_particle_preview(self, emitter_id: str) -> None:
        draft=self.particle_preview_manager.drafts.get(emitter_id); session=self.particle_preview_manager.sessions.get(emitter_id)
        if draft is None or session is None or session.revision!=draft.revision:return
        directory=QFileDialog.getExistingDirectory(self,self.localization.text("effects.export_preview"),str(Path("exports").resolve()))
        if not directory:return
        emitter=next(e for e in self.project.particle_emitters if e.id==emitter_id)
        try: export_preview_sequence(session.frames,directory,emitter.name)
        except (ValueError,FileExistsError,OSError) as exc: QMessageBox.critical(self,self.localization.text("effects.export_preview"),str(exc))
    def _refresh_effect_panels(self) -> None:
        selected_generator = self.effect_library.current_generator_id()
        self.effect_library.refresh(self.project)
        generator = next(
            (
                item
                for item in self.project.generators
                if item.id == selected_generator
            ),
            None,
        )
        self.effect_properties.set_generator(generator, self.project)
        if generator is not None:
            draft = self.preview_manager.ensure_draft(generator)
            self.effect_properties.set_settings(draft.settings)

    def generate_effect(
        self, generator_id: str, settings: TransformEmitterSettings
    ) -> bool:
        generator = next(
            (item for item in self.project.generators if item.id == generator_id), None
        )
        if generator is None:
            return False
        draft = self.preview_manager.update_draft(self.project, generator, settings)
        session = self.preview_manager.current_session(generator_id)
        try:
            if session is not None:
                outputs = [frame.copy() for frame in session.frames]
            else:
                snapshot = PreviewRenderSnapshot.from_project(
                    self.project, generator.id, draft.revision, draft.settings
                )
                outputs = render_preview_snapshot(snapshot)
            layer = apply_rendered_frames(self.project, generator, outputs)
        except (EffectRenderError, ValueError, MemoryError) as exc:
            QMessageBox.critical(self, self.localization.text("error.generation"), str(exc))
            return False
        generator.settings = deepcopy(draft.settings)
        self.preview_manager.mark_applied(generator.id, generator.settings)
        self._clear_preview()
        self.layer_index = self.project.layers.index(layer)
        self.frame_index = min(self.frame_index, len(self.project.frames) - 1)
        self._mark_dirty()
        self._refresh_all()
        self.effect_library.select_generator(generator.id)
        self.select_generator(generator.id)
        self.statusBar().showMessage(self.localization.text("status.generated").format(name=generator.name), 4000)
        return True

    def reset_generator_settings(self, generator_id: str) -> None:
        generator = next(
            (item for item in self.project.generators if item.id == generator_id), None
        )
        if generator is None:
            return
        source_id = generator.settings.source_asset_id
        defaults = TransformEmitterSettings(
            source_asset_id=source_id,
            origin_x=self.project.width / 2.0,
            origin_y=self.project.height / 2.0,
            line_end_x=self.project.width * 0.75,
            line_end_y=self.project.height / 2.0,
            radius=min(self.project.width, self.project.height) / 4.0,
        )
        self.effect_properties.set_settings(defaults)
        self.update_generator_draft(generator.id, defaults)
        self.effect_properties.settings_status.setText(
            "Defaults loaded; Apply to Frames to commit"
        )

    def update_generator_draft(
        self, generator_id: str, settings: TransformEmitterSettings
    ) -> None:
        generator = next(
            (item for item in self.project.generators if item.id == generator_id), None
        )
        if generator is None:
            return
        self.preview_manager.update_draft(self.project, generator, settings)
        if self.effect_properties.generator_id == generator_id:
            self.canvas.set_gizmo(generator_id, settings, mode=self.effect_properties.current_gizmo_mode(), edit_end=self.effect_properties.edit_end_check.isChecked(), locked=self.play_timer.isActive())

    def _set_gizmo_mode(self, mode: str, edit_end: bool) -> None:
        generator_id = self.effect_properties.generator_id
        draft = self.preview_manager.drafts.get(generator_id) if generator_id else None
        self.canvas.set_gizmo(generator_id, None if draft is None else draft.settings, mode=mode, edit_end=edit_end, locked=self.play_timer.isActive())

    def _gizmo_changed(self, generator_id: str, settings: TransformEmitterSettings) -> None:
        if self.play_timer.isActive(): self.set_playing(False)
        self.effect_properties.set_settings(settings)
        self.update_generator_draft(generator_id, settings)

    def refresh_generator_preview(self, generator_id: str) -> None:
        generator = next(
            (item for item in self.project.generators if item.id == generator_id), None
        )
        if generator is None:
            return
        self.preview_manager.ensure_draft(generator)
        self.preview_manager.schedule(self.project, generator_id, immediate=True)

    def revert_generator_draft(self, generator_id: str) -> None:
        if generator_id not in self.preview_manager.drafts:
            return
        draft = self.preview_manager.revert(generator_id)
        self._clear_preview()
        if self.effect_properties.generator_id == generator_id:
            self.effect_properties.set_settings(draft.settings)
            self.effect_properties.set_preview_state("applied")

    def _preview_state_changed(self, generator_id: str, state: str) -> None:
        if self.effect_properties.generator_id == generator_id:
            self.effect_properties.set_preview_state(state)

    def _preview_ready(
        self, generator_id: str, revision: int, frames: list
    ) -> None:
        if self.effect_properties.generator_id != generator_id:
            return
        generator = next(
            (item for item in self.project.generators if item.id == generator_id), None
        )
        if generator is not None:
            self._activate_preview(generator, frames)

    def _preview_failed(self, generator_id: str, revision: int, message: str) -> None:
        if self.effect_properties.generator_id == generator_id:
            self.statusBar().showMessage(
                "Preview failed. Applied frames were not changed.", 5000
            )

    def _activate_preview(self, generator: TransformEmitter, frames: list) -> None:
        self.active_preview_generator_id = generator.id
        self.frame_index = min(self.frame_index, len(frames) - 1)
        self.canvas.set_preview(frames, generator.generated_layer_id)
        self.canvas.set_frame(self.frame_index)
        self.timeline.refresh(
            self.project,
            self.layer_index,
            self.frame_index,
            display_frame_count=len(frames),
            preview=True,
        )
        self._refresh_playback_status()

    def _clear_preview(self) -> None:
        if self.active_preview_generator_id is not None and self.play_timer.isActive():
            self.set_playing(False)
        self.active_preview_generator_id = None
        self.canvas.clear_preview()
        self.frame_index = min(self.frame_index, len(self.project.frames) - 1)
        self.canvas.set_frame(self.frame_index)
        self.timeline.refresh(self.project, self.layer_index, self.frame_index)
        self._refresh_playback_status()

    def delete_source_asset(self, asset_id: str) -> None:
        asset = next(
            (item for item in self.project.source_assets if item.id == asset_id), None
        )
        if asset is None:
            return
        if any(
            item.settings.source_asset_id == asset_id for item in self.project.generators
        ):
            QMessageBox.warning(
                self,
                "Source Asset In Use",
                "Delete its Transform Emitter before deleting this Source Asset.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Delete Source Asset",
            f"Delete source asset '{asset.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.project.source_assets.remove(asset)
        self._mark_dirty()
        self._refresh_effect_panels()

    def delete_generator(self, generator_id: str) -> None:
        generator = next(
            (item for item in self.project.generators if item.id == generator_id), None
        )
        if generator is None:
            return
        if not self._resolve_generator_draft(generator_id):
            return
        answer = QMessageBox.question(
            self,
            "Delete Generator",
            f"Delete '{generator.name}' and its Generated Layer?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        layer = next(
            (
                item
                for item in self.project.layers
                if item.id == generator.generated_layer_id
            ),
            None,
        )
        if layer is not None:
            if len(self.project.layers) == 1:
                self.project.add_layer()
            layer_index = self.project.layers.index(layer)
            self.project.delete_layer(layer_index)
        self.project.generators.remove(generator)
        self.layer_index = min(self.layer_index, len(self.project.layers) - 1)
        self._mark_dirty()
        self._refresh_all()

    def create_project_settings_dialog(self) -> ProjectSettingsDialog:
        """Create an editable dialog from the latest project values."""
        return ProjectSettingsDialog(
            self.project,
            self.project_path,
            self.apply_project_settings,
            self,
            localization=self.localization,
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
            self.set_playing(False)
            self.preview_manager.reset_context()
            self.particle_preview_manager.reset_context()
            self._clear_preview()
            try:
                if values.resize_mode is CanvasResizeMode.SCALE:
                    scale_project(self.project, values.width, values.height)
                else:
                    resize_canvas(
                        self.project, values.width, values.height, values.anchor
                    )
            except CanvasResizeError as exc:
                QMessageBox.critical(self, self.localization.text("error.canvas_resize"), str(exc))
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
        if not self._confirm_unapplied_previews() or not self._confirm_discard():
            return
        self.set_playing(False)
        self.preview_manager.reset_context()
        self.particle_preview_manager.reset_context()
        self._clear_preview()
        self.project = create_playback_test_project()
        self.project_path = None
        self.frame_index = self.layer_index = 0
        self.dirty = True
        self._refresh_all()
        self.statusBar().showMessage(self.localization.text("status.playback_test"), 3000)

    def show_keyboard_shortcuts(self) -> None:
        dialog = KeyboardShortcutsDialog(
            self.shortcuts, self, localization=self.localization
        )
        dialog.shortcuts_applied.connect(self.apply_shortcuts)
        dialog.exec()

    def show_interface_settings(self) -> None:
        dialog=InterfaceSettingsDialog(self.settings_service.settings,self.localization,self)
        dialog.frame_width_changed.connect(self.apply_timeline_frame_width)
        dialog.exec()

    def apply_timeline_frame_width(self,width:int) -> None:
        width=max(20,min(96,int(width)));self.settings_service.settings.setValue("ui/timeline_frame_width",width)
        self.timeline.set_frame_cell_width(width);self.resource_editor.set_timeline_frame_width(width)

    def apply_shortcuts(self, shortcuts: dict[str, str | list[str]]) -> bool:
        """Persist shortcuts and update their QAction menu entries immediately."""
        try:
            normalized = self.settings_service.save(shortcuts)
        except (SettingsError, ValueError) as exc:
            QMessageBox.warning(self, self.localization.text("error.shortcuts"), str(exc))
            return False
        self.shortcuts = normalized
        self._update_action_shortcuts(normalized)
        self.playback_shortcut_controller.set_sequences(
            normalized.get("play_stop_animation", [])
        )
        self.frame_shortcut_controller.set_sequences(normalized)
        return True

    def _update_action_shortcuts(self, shortcuts: dict[str, list[str]]) -> None:
        for key, action in self.shortcut_actions.items():
            action.setShortcuts(
                [QKeySequence(item) for item in shortcuts.get(key, [])]
            )

    def add_frame(self) -> None:
        """Insert a transparent frame after the current frame and select it."""
        self.application_undo_stack.push(EditorOperationCommand(self,"add_frame",{"index":self.frame_index},"Add Frame"))

    def duplicate_frame(self) -> None:
        """Duplicate the current frame immediately after it and select the copy."""
        self.application_undo_stack.push(EditorOperationCommand(self,"duplicate_frame",{"index":self.frame_index},"Duplicate Frame"))

    def delete_frame(self) -> None:
        try:
            if len(self.project.frames)<=1:raise ProjectError("a project must contain at least one frame")
        except ProjectError as exc:
            QMessageBox.information(self, self.localization.text("error.delete_frame"), str(exc))
            return
        self.application_undo_stack.push(EditorOperationCommand(self,"delete_frame",{"index":self.frame_index,"frame":self.project.frames[self.frame_index]},"Delete Frame"))

    def add_layer(self) -> None:
        """Add the next collision-free default layer and select it."""
        self.application_undo_stack.push(EditorOperationCommand(self,"add_layer",{"name":self.project.next_layer_name()},"Add Layer"))

    def delete_layer(self) -> None:
        try:
            if len(self.project.layers)<=1:raise ProjectError("a project must contain at least one layer")
        except ProjectError as exc:
            QMessageBox.information(self, self.localization.text("error.delete_layer"), str(exc))
            return
        layer=self.project.layers[self.layer_index];pixels=[frame.layer_pixels[layer.id] for frame in self.project.frames]
        self.application_undo_stack.push(EditorOperationCommand(self,"delete_layer",{"index":self.layer_index,"layer":layer,"pixels":pixels},"Delete Layer"))

    def select_cell(self, layer_index: int, frame_index: int) -> None:
        """Synchronize a timeline cell selection with the canvas."""
        if not (0 <= layer_index < len(self.project.layers)):
            return
        if not (0 <= frame_index < self._display_frame_count()):
            return
        self.layer_index = layer_index
        self.frame_index = frame_index
        self.canvas.set_layer(layer_index)
        self.canvas.set_frame(frame_index)
        self.timeline.set_current_cell(
            self.project,
            layer_index,
            frame_index,
            display_frame_count=self._display_frame_count(),
        )
        self._refresh_selection_status()
        self._refresh_playback_status()

    def select_frame(self, index: int) -> None:
        if 0 <= index < self._display_frame_count():
            self.frame_index = index
            self.canvas.set_frame(index)
            self.timeline.set_current_cell(
                self.project,
                self.layer_index,
                index,
                display_frame_count=self._display_frame_count(),
            )
            self._refresh_selection_status()
            self._refresh_playback_status()

    def set_fps(self, value: int) -> None:
        if self.project.fps != value:
            self.project.fps = value
            self._mark_dirty()
        if self.play_timer.isActive():
            self.play_timer.setInterval(max(1, round(1000 / value)))
        self._refresh_playback_status()

    def set_playing(self, playing: bool) -> None:
        if self.play_action.isChecked() != playing:
            with QSignalBlocker(self.play_action):
                self.play_action.setChecked(playing)
        if playing:
            self.play_timer.start(max(1, round(1000 / self.project.fps)))
        else:
            self.play_timer.stop()
        self.timeline.set_playing(playing)
        self._refresh_playback_status()

    def _refresh_playback_status(self) -> None:
        self.timeline.update_playback_status(
            self.play_timer.isActive(),
            self.frame_index,
            self._display_frame_count(),
            self.project.fps,
            preview=self.active_preview_generator_id is not None,
        )

    def _advance_playback(self) -> None:
        next_index = self.frame_index + 1
        if next_index >= self._display_frame_count():
            if self.project.loop:
                next_index = 0
            else:
                self.set_playing(False)
                return
        self.select_frame(next_index)

    def _resolve_generator_draft(self, generator_id: str) -> bool:
        draft = self.preview_manager.drafts.get(generator_id)
        if draft is None or not draft.is_dirty:
            return True
        choice = self._ask_unapplied_choice()
        if choice == "cancel":
            return False
        if choice == "apply":
            return self.generate_effect(generator_id, draft.settings)
        self.preview_manager.discard(generator_id)
        if self.active_preview_generator_id == generator_id:
            self._clear_preview()
        return True

    def _confirm_unapplied_previews(self) -> bool:
        dirty_ids = self.preview_manager.dirty_generator_ids()
        if not dirty_ids:
            return True
        choice = self._ask_unapplied_choice()
        if choice == "cancel":
            return False
        if choice == "apply":
            for generator_id in list(dirty_ids):
                draft = self.preview_manager.drafts.get(generator_id)
                if draft is not None and not self.generate_effect(
                    generator_id, draft.settings
                ):
                    return False
        else:
            for generator_id in list(dirty_ids):
                self.preview_manager.discard(generator_id)
            self._clear_preview()
        return True

    def _ask_unapplied_choice(self) -> str:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Unapplied Preview")
        dialog.setText(self.localization.text("message.unapplied"))
        apply_button = dialog.addButton("Apply", QMessageBox.ButtonRole.AcceptRole)
        discard_button = dialog.addButton(
            "Discard", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is apply_button:
            return "apply"
        if clicked is discard_button:
            return "discard"
        return "cancel"

    def previous_frame(self) -> None:
        self.set_playing(False)
        self.select_frame(max(0, self.frame_index - 1))

    def next_frame(self) -> None:
        self.set_playing(False)
        self.select_frame(min(self._display_frame_count() - 1, self.frame_index + 1))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._confirm_unapplied_previews() and self._confirm_discard():
            self.preview_manager.close()
            self.particle_preview_manager.reset_context()
            event.accept()
        else:
            event.ignore()
