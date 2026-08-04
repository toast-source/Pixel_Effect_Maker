"""Transient, non-serialized live preview state."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .effect_generator import TransformEmitterSettings


@dataclass
class GeneratorDraft:
    generator_id: str
    settings: TransformEmitterSettings
    revision: int = 0
    is_dirty: bool = False


@dataclass
class PreviewSession:
    generator_id: str
    revision: int
    frames: list[np.ndarray] = field(default_factory=list)
    render_state: str = "idle"
    error_message: str = ""

    @property
    def output_frame_count(self) -> int:
        return len(self.frames)
