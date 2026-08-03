"""Integrated layer-by-frame timeline controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project


class TimelineWidget(QWidget):
    """Show layers as rows and sequential frame numbers as columns."""

    cell_selected = Signal(int, int)
    add_requested = Signal()
    duplicate_requested = Signal()
    delete_requested = Signal()
    add_layer_requested = Signal()
    delete_layer_requested = Signal()
    play_toggled = Signal(bool)
    fps_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Layer × Frame Timeline"))
        self.selection_label = QLabel("Layer 1 · Frame 1")
        self.selection_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self.selection_label)
        toolbar.addStretch(1)

        for label, signal, tooltip in (
            ("+ Frame", self.add_requested, "Add frame"),
            ("⧉ Frame", self.duplicate_requested, "Duplicate selected frame"),
            ("− Frame", self.delete_requested, "Delete selected frame"),
            ("+ Layer", self.add_layer_requested, "Add layer"),
            ("− Layer", self.delete_layer_requested, "Delete selected layer"),
        ):
            button = QPushButton(label)
            button.setToolTip(tooltip)
            button.clicked.connect(signal)
            toolbar.addWidget(button)

        self.play_button = QPushButton("▶")
        self.play_button.setCheckable(True)
        self.play_button.toggled.connect(self._on_play_toggled)
        toolbar.addWidget(self.play_button)
        toolbar.addWidget(QLabel("FPS"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.valueChanged.connect(self.fps_changed)
        toolbar.addWidget(self.fps_spin)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setMinimumHeight(150)
        self.table.setMaximumHeight(280)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.currentCellChanged.connect(self._on_current_cell_changed)
        layout.addWidget(self.table)

    def _on_play_toggled(self, playing: bool) -> None:
        self.play_button.setText("■" if playing else "▶")
        self.play_toggled.emit(playing)

    def _on_current_cell_changed(
        self, row: int, column: int, previous_row: int, previous_column: int
    ) -> None:
        if self._project is None or row < 0 or column < 0:
            return
        layer_index = len(self._project.layers) - 1 - row
        if not (0 <= layer_index < len(self._project.layers)):
            return
        if not (0 <= column < len(self._project.frames)):
            return
        self._update_selection_label(layer_index, column)
        self.cell_selected.emit(layer_index, column)

    def refresh(
        self, project: Project, selected_layer: int = 0, selected_frame: int = 0
    ) -> None:
        """Rebuild the table while preserving a valid model selection."""
        self._project = project
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setRowCount(len(project.layers))
        self.table.setColumnCount(len(project.frames))
        self.table.setHorizontalHeaderLabels(
            [str(index) for index in range(1, len(project.frames) + 1)]
        )
        self.table.setVerticalHeaderLabels(
            [
                f"{'◉' if layer.visible else '○'}  {layer.name}"
                for layer in reversed(project.layers)
            ]
        )
        for display_row, layer in enumerate(reversed(project.layers)):
            for frame_index, frame in enumerate(project.frames):
                pixels = frame.layer_pixels.get(layer.id)
                marker = "■" if pixels is not None and pixels[..., 3].any() else "·"
                item = QTableWidgetItem(marker)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(
                    f"{layer.name} · Frame {frame_index + 1}"
                )
                self.table.setItem(display_row, frame_index, item)
        self.table.blockSignals(False)
        self.set_current_cell(project, selected_layer, selected_frame)
        self.fps_spin.blockSignals(True)
        self.fps_spin.setValue(project.fps)
        self.fps_spin.blockSignals(False)

    def set_current_cell(
        self, project: Project, layer_index: int, frame_index: int
    ) -> None:
        """Select the cell corresponding to model indices without emitting edits."""
        if not project.layers or not project.frames:
            return
        layer_index = max(0, min(layer_index, len(project.layers) - 1))
        frame_index = max(0, min(frame_index, len(project.frames) - 1))
        display_row = len(project.layers) - 1 - layer_index
        self.table.blockSignals(True)
        self.table.setCurrentCell(display_row, frame_index)
        self.table.blockSignals(False)
        self._update_selection_label(layer_index, frame_index)

    def _update_selection_label(self, layer_index: int, frame_index: int) -> None:
        if self._project is None:
            return
        self.selection_label.setText(
            f"{self._project.layers[layer_index].name} · Frame {frame_index + 1}"
        )
