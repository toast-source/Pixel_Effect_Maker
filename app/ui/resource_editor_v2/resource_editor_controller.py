from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.models.animation_clip import AnimationClipAsset
from app.models.resource_composition import CompositionLayer, ResourceComposition
from app.models.source_asset import SourceAsset
from app.services.resource_composition_render_service import invalidate_composition_cache

from .resource_editor_state import ResourceEditorMode, ResourceEditorState


class ResourceEditorController(QObject):
    state_changed = Signal(object)
    frame_changed = Signal(int)
    composition_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.state = ResourceEditorState()
        self._composition_sessions: dict[str, tuple[str | None, int, str]] = {}

    @property
    def asset(self):
        if self.project is None or self.state.asset_id is None:
            return None
        items = self.project.source_assets if self.state.asset_type == "source_asset" else self.project.animation_clips
        return next((item for item in items if item.id == self.state.asset_id), None)

    @property
    def composition(self):
        if self.project is None or self.state.composition_id is None:
            return None
        return next((item for item in self.project.resource_compositions if item.id == self.state.composition_id), None)

    @property
    def layer(self):
        composition = self.composition
        return None if composition is None else next((item for item in composition.layers if item.id == self.state.layer_id), None)

    def set_project(self, project):
        if self.project is not None and self.project is not project:
            self._composition_sessions.clear()
            self.state = ResourceEditorState()
        self.project = project
        self.reconcile_with_project()

    def clear(self):
        self.state = ResourceEditorState()
        self.state_changed.emit(self.state)

    def _remember_composition_session(self):
        if self.state.composition_id is not None:
            self._composition_sessions[self.state.composition_id] = (
                self.state.layer_id,
                self.state.frame,
                self.state.gizmo_mode,
            )

    def reconcile_with_project(self):
        composition = self.composition
        asset = self.asset
        if composition is not None:
            if self.layer is None:
                self.state.layer_id = None
            self.state.frame = max(0, min(self.state.frame, composition.frame_count - 1))
            self._derive_mode()
        elif asset is not None:
            self.state.composition_id = None
            self.state.layer_id = None
            self._derive_mode()
        else:
            self.clear()

    def select_asset(self, kind: str, identifier: str):
        self._remember_composition_session()
        self.state.asset_type = kind
        self.state.asset_id = identifier
        self.state.composition_id = None
        self.state.layer_id = None
        self.state.frame = 0
        self._derive_mode()

    def select_composition(self, identifier: str, layer_id: str | None = None):
        self._remember_composition_session()
        remembered_layer, remembered_frame, remembered_gizmo = self._composition_sessions.get(
            identifier, (None, 0, "move")
        )
        self.state.asset_type = None
        self.state.asset_id = None
        self.state.composition_id = identifier
        self.state.layer_id = layer_id if layer_id is not None else remembered_layer
        self.state.frame = remembered_frame
        self.state.gizmo_mode = remembered_gizmo
        composition = self.composition
        if composition is not None:
            self.state.frame = max(0, min(self.state.frame, composition.frame_count - 1))
            if self.layer is None:
                self.state.layer_id = None
        self._derive_mode()

    def select_layer(self, identifier: str | None):
        self.state.layer_id = identifier
        self._remember_composition_session()
        self._derive_mode()

    def _derive_mode(self):
        if self.layer is not None:
            self.state.mode = ResourceEditorMode.LAYER_EDIT
        elif self.composition is not None:
            self.state.mode = ResourceEditorMode.COMPOSITION
        elif self.asset is not None:
            self.state.mode = ResourceEditorMode.ASSET_INSPECT
        else:
            self.state.mode = ResourceEditorMode.EMPTY
        self.state_changed.emit(self.state)

    def set_frame(self, frame: int):
        maximum = self.composition.frame_count - 1 if self.composition else max(0, len(self.asset.frames) - 1) if isinstance(self.asset, AnimationClipAsset) else 0
        self.state.frame = max(0, min(int(frame), maximum))
        self._remember_composition_session()
        self.frame_changed.emit(self.state.frame)

    def set_gizmo(self, mode: str):
        self.state.gizmo_mode = mode
        self._remember_composition_session()

    def create_resource(self, name: str, width: int, height: int, fps: int, frames: int, loop: bool):
        asset = self.asset
        if asset is None:
            return None
        existing = {item.name for item in self.project.resource_compositions}
        base = name.strip() or Path(asset.name).stem
        safe = base
        number = 2
        while safe in existing:
            safe = f"{base} ({number})"
            number += 1
        composition = ResourceComposition(safe, width, height, fps, frames, loop)
        layer = CompositionLayer(asset.name, self.state.asset_type, asset.id, 0, frames - 1, pivot_x=asset.pivot_x, pivot_y=asset.pivot_y)
        composition.layers.append(layer)
        self.project.resource_compositions.append(composition)
        self.select_composition(composition.id, layer.id)
        self.composition_changed.emit(composition.id)
        return composition

    def create_blank_resource(self, name: str, width: int, height: int, fps: int, frames: int, loop: bool):
        existing = {item.name for item in self.project.resource_compositions}
        base = name.strip() or "Resource 1"; safe = base; number = 2
        while safe in existing:
            safe = f"{base} ({number})"; number += 1
        composition = ResourceComposition(safe, width, height, fps, frames, loop)
        self.project.resource_compositions.append(composition)
        self.select_composition(composition.id)
        self.composition_changed.emit(composition.id)
        return composition

    def changed(self):
        composition = self.composition
        if composition is None:
            return
        composition.touch()
        invalidate_composition_cache(composition.id)
        self.composition_changed.emit(composition.id)
        self.state_changed.emit(self.state)

    def full_rotation(self):
        composition, layer = self.composition, self.layer
        if composition is None or layer is None:
            return
        track = layer.add_property("rotation")
        track.keyframes.clear()
        track.set_keyframe(0, 0.0, "Linear")
        track.set_keyframe(composition.frame_count - 1, 360.0, "Linear")
        self.changed()
