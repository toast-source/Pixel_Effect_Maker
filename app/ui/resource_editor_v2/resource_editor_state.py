from dataclasses import dataclass
from enum import Enum


class ResourceEditorMode(Enum):
    EMPTY = "empty"
    ASSET_INSPECT = "asset_inspect"
    COMPOSITION = "composition"
    LAYER_EDIT = "layer_edit"


@dataclass
class ResourceEditorState:
    mode: ResourceEditorMode = ResourceEditorMode.EMPTY
    asset_type: str | None = None
    asset_id: str | None = None
    composition_id: str | None = None
    layer_id: str | None = None
    frame: int = 0
    gizmo_mode: str = "move"
