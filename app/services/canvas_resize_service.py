"""Atomic canvas resize and nearest-neighbor project scaling."""

from __future__ import annotations

from enum import Enum

import numpy as np

from app.models.project import Project


class CanvasResizeError(ValueError):
    """Raised when a project cannot be resized safely."""


class CanvasAnchor(str, Enum):
    TOP_LEFT = "Top Left"
    TOP_CENTER = "Top Center"
    TOP_RIGHT = "Top Right"
    CENTER_LEFT = "Center Left"
    CENTER = "Center"
    CENTER_RIGHT = "Center Right"
    BOTTOM_LEFT = "Bottom Left"
    BOTTOM_CENTER = "Bottom Center"
    BOTTOM_RIGHT = "Bottom Right"


class CanvasResizeMode(str, Enum):
    CANVAS_ONLY = "Resize canvas only"
    SCALE = "Scale image and canvas"


def _validate_dimensions(width: int, height: int) -> None:
    if not (1 <= width <= 1024 and 1 <= height <= 1024):
        raise CanvasResizeError("canvas dimensions must be between 1 and 1024 pixels")


def _validated_buffers(project: Project) -> list[dict[str, np.ndarray]]:
    expected_shape = (project.height, project.width, 4)
    validated: list[dict[str, np.ndarray]] = []
    for frame_index, frame in enumerate(project.frames):
        frame_buffers: dict[str, np.ndarray] = {}
        for layer in project.layers:
            pixels = frame.layer_pixels.get(layer.id)
            if not isinstance(pixels, np.ndarray):
                raise CanvasResizeError(
                    f"frame {frame_index + 1}, layer {layer.name} has no pixel array"
                )
            if pixels.shape != expected_shape or pixels.dtype != np.uint8:
                raise CanvasResizeError(
                    f"frame {frame_index + 1}, layer {layer.name} has invalid "
                    f"pixels: shape={pixels.shape}, dtype={pixels.dtype}"
                )
            frame_buffers[layer.id] = pixels
        validated.append(frame_buffers)
    return validated


def _axis_offset(old_size: int, new_size: int, alignment: str) -> int:
    difference = new_size - old_size
    if alignment in {"left", "top"}:
        return 0
    if alignment == "center":
        # Floor division consistently gives an extra pixel to the right/bottom
        # when expanding and crops the extra pixel from the left/top when shrinking.
        return difference // 2
    return difference


def _anchor_offsets(
    old_width: int,
    old_height: int,
    new_width: int,
    new_height: int,
    anchor: CanvasAnchor,
) -> tuple[int, int]:
    vertical, horizontal = {
        CanvasAnchor.TOP_LEFT: ("top", "left"),
        CanvasAnchor.TOP_CENTER: ("top", "center"),
        CanvasAnchor.TOP_RIGHT: ("top", "right"),
        CanvasAnchor.CENTER_LEFT: ("center", "left"),
        CanvasAnchor.CENTER: ("center", "center"),
        CanvasAnchor.CENTER_RIGHT: ("center", "right"),
        CanvasAnchor.BOTTOM_LEFT: ("bottom", "left"),
        CanvasAnchor.BOTTOM_CENTER: ("bottom", "center"),
        CanvasAnchor.BOTTOM_RIGHT: ("bottom", "right"),
    }[anchor]
    return (
        _axis_offset(old_width, new_width, horizontal),
        _axis_offset(old_height, new_height, vertical),
    )


def _commit_buffers(
    project: Project,
    width: int,
    height: int,
    buffers: list[dict[str, np.ndarray]],
) -> None:
    for frame, frame_buffers in zip(project.frames, buffers, strict=True):
        frame.layer_pixels = frame_buffers
    project.width = width
    project.height = height


def resize_canvas(
    project: Project,
    new_width: int,
    new_height: int,
    anchor: CanvasAnchor = CanvasAnchor.CENTER,
) -> None:
    """Resize only the transparent canvas, preserving pixel size and RGBA values."""
    _validate_dimensions(new_width, new_height)
    source_buffers = _validated_buffers(project)
    anchor = CanvasAnchor(anchor)
    offset_x, offset_y = _anchor_offsets(
        project.width, project.height, new_width, new_height, anchor
    )
    source_x = max(0, -offset_x)
    source_y = max(0, -offset_y)
    destination_x = max(0, offset_x)
    destination_y = max(0, offset_y)
    copy_width = min(project.width - source_x, new_width - destination_x)
    copy_height = min(project.height - source_y, new_height - destination_y)

    transformed: list[dict[str, np.ndarray]] = []
    for frame_buffers in source_buffers:
        output_buffers: dict[str, np.ndarray] = {}
        for layer_id, source in frame_buffers.items():
            output = np.zeros((new_height, new_width, 4), dtype=np.uint8)
            if copy_width > 0 and copy_height > 0:
                output[
                    destination_y : destination_y + copy_height,
                    destination_x : destination_x + copy_width,
                ] = source[
                    source_y : source_y + copy_height,
                    source_x : source_x + copy_width,
                ]
            output_buffers[layer_id] = output
        transformed.append(output_buffers)
    _commit_buffers(project, new_width, new_height, transformed)


def scale_project(project: Project, new_width: int, new_height: int) -> None:
    """Scale every layer buffer with exact nearest-neighbor index sampling."""
    _validate_dimensions(new_width, new_height)
    source_buffers = _validated_buffers(project)
    x_indices = np.floor(
        np.arange(new_width, dtype=np.float64) * project.width / new_width
    ).astype(np.intp)
    y_indices = np.floor(
        np.arange(new_height, dtype=np.float64) * project.height / new_height
    ).astype(np.intp)

    transformed: list[dict[str, np.ndarray]] = []
    for frame_buffers in source_buffers:
        output_buffers = {
            layer_id: source[y_indices[:, None], x_indices[None, :], :].copy()
            for layer_id, source in frame_buffers.items()
        }
        transformed.append(output_buffers)
    _commit_buffers(project, new_width, new_height, transformed)
