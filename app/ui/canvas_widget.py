"""Integer-scaled pixel canvas widget."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import QWidget

from app.models.project import Project


class CanvasWidget(QWidget):
    """Render the current frame over a checkerboard without pixel smoothing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project: Project | None = None
        self.frame_index = 0
        self.layer_index = 0
        self.zoom = 8
        self.setMinimumSize(320, 320)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_project(self, project: Project) -> None:
        self.project = project
        self.frame_index = 0
        self.layer_index = 0
        self._fit_initial_zoom()
        self.update()

    def set_frame(self, index: int) -> None:
        self.frame_index = index
        self.update()

    def set_layer(self, index: int) -> None:
        self.layer_index = index
        self.update()

    def _fit_initial_zoom(self) -> None:
        if self.project:
            self.zoom = max(1, min(16, 512 // max(self.project.width, self.project.height)))

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = 1 if event.angleDelta().y() > 0 else -1
        self.zoom = max(1, min(32, self.zoom + delta))
        self.update()
        event.accept()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#20242b"))
        if not self.project or not self.project.frames:
            painter.setPen(QColor("#adb5bd"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No project")
            return

        width = self.project.width * self.zoom
        height = self.project.height * self.zoom
        origin = QPoint((self.width() - width) // 2, (self.height() - height) // 2)
        canvas_rect = QRect(origin.x(), origin.y(), width, height)
        painter.setClipRect(canvas_rect)

        checker = max(1, 8 * self.zoom)
        colors = (QColor("#b8bdc4"), QColor("#e1e4e8"))
        for y in range(origin.y(), origin.y() + height, checker):
            for x in range(origin.x(), origin.x() + width, checker):
                color = colors[((x - origin.x()) // checker + (y - origin.y()) // checker) % 2]
                painter.fillRect(x, y, checker, checker, color)

        pixels: np.ndarray = np.ascontiguousarray(
            self.project.compose_frame(self.frame_index)
        )
        image = QImage(
            pixels.data,
            self.project.width,
            self.project.height,
            pixels.strides[0],
            QImage.Format.Format_RGBA8888,
        ).copy()
        pixmap = QPixmap.fromImage(image)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(canvas_rect, pixmap)
        painter.setClipping(False)
        painter.setPen(QColor("#77808c"))
        painter.drawRect(canvas_rect.adjusted(0, 0, -1, -1))
