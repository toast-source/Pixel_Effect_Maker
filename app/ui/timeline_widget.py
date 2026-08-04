"""Integrated layer-by-frame timeline controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
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
from app.ui.timeline_scrub_controller import TimelineScrubController


class TimelineWidget(QWidget):
    """Show layers as rows and sequential frame numbers as columns."""

    cell_selected = Signal(int, int)
    add_requested = Signal()
    duplicate_requested = Signal()
    delete_requested = Signal()
    add_layer_requested = Signal()
    delete_layer_requested = Signal()
    play_requested = Signal()
    fps_changed = Signal(int)
    layer_visibility_requested = Signal(int, bool)
    scrub_started = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._playing = False
        self._preview = False
        self._display_frame_count = 1
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.selection_label = QLabel("Layer 1 · Frame 1")
        self.selection_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self.selection_label)
        self.playback_status_label = QLabel("Stopped · Frame 1 / 1 · 12 FPS")
        toolbar.addWidget(self.playback_status_label)
        toolbar.addStretch(1)

        self.edit_buttons: list[QPushButton] = []
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
            self.edit_buttons.append(button)

        self.play_button = QPushButton("▶")
        self.play_button.clicked.connect(self.play_requested)
        toolbar.addWidget(self.play_button)
        self.fps_label = QLabel("FPS")
        toolbar.addWidget(self.fps_label)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.valueChanged.connect(self.fps_changed)
        toolbar.addWidget(self.fps_spin)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.frame_cell_width = 36
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setMinimumHeight(150)
        self.table.setMaximumHeight(280)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setDefaultSectionSize(self.frame_cell_width)
        self.table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.currentCellChanged.connect(self._on_current_cell_changed)
        self.scrub_controller = TimelineScrubController(
            self.table, self._scrub_to, self.scrub_started.emit, self
        )
        self.table.verticalHeader().sectionClicked.connect(self._toggle_visibility)
        layout.addWidget(self.table)

    def _scrub_to(self, row: int, column: int) -> None:
        self.table.setCurrentCell(row, column)

    def set_frame_cell_width(self, width: int) -> None:
        self.frame_cell_width = max(20, min(96, int(width)))
        self.table.horizontalHeader().setDefaultSectionSize(self.frame_cell_width)
        for column in range(self.table.columnCount()):
            self.table.setColumnWidth(column, self.frame_cell_width)

    def _toggle_visibility(self, row: int) -> None:
        if self._project is None:return
        index=len(self._project.layers)-1-row
        if 0<=index<len(self._project.layers):
            layer=self._project.layers[index]; self.layer_visibility_requested.emit(index,not layer.visible)

    def retranslate_ui(self, localization) -> None:
        self._localization = localization
        labels = (
            ("+ Frame", "Add an empty frame after the current frame."),
            ("⧉ Frame", "Duplicate the selected frame."),
            ("− Frame", "Delete the selected frame."),
            ("+ Layer", "Add a new layer."),
            ("− Layer", "Delete the selected layer."),
        )
        if localization.language == "ko":
            labels = (
                ("+ 프레임", "현재 프레임 뒤에 빈 프레임을 추가합니다."),
                ("⧉ 프레임", "선택한 프레임을 복제합니다."),
                ("− 프레임", "선택한 프레임을 삭제합니다."),
                ("+ 레이어", "새 레이어를 추가합니다."),
                ("− 레이어", "선택한 레이어를 삭제합니다."),
            )
        for button, (text, tooltip) in zip(self.edit_buttons, labels, strict=True):
            button.setText(text)
            button.setToolTip(tooltip)
            button.setStatusTip(tooltip)
        self.fps_spin.setToolTip("Animation frames per second." if localization.language == "en" else "초당 재생 프레임 수입니다.")
        self.table.setToolTip("Select a layer and frame cell." if localization.language == "en" else "레이어와 프레임 교차 셀을 선택합니다.")

    def set_playing(self, playing: bool) -> None:
        """Synchronize the button display with the main playback QAction."""
        self._playing = playing
        self.play_button.setText("■" if playing else "▶")
        self.play_button.setToolTip(
            "Stop animation" if playing else "Play animation"
        )
        if self._project is not None:
            self.update_playback_status(
                playing,
                max(0, self.table.currentColumn()),
                self._display_frame_count,
                self._project.fps,
                preview=self._preview,
            )

    def update_playback_status(
        self,
        playing: bool,
        frame_index: int,
        frame_count: int,
        fps: int,
        preview: bool = False,
    ) -> None:
        """Show playback state even when every project pixel is transparent."""
        self._playing = playing
        self._preview = preview
        self._display_frame_count = frame_count
        localization = getattr(self, "_localization", None)
        if localization is None:
            state = "Playing" if playing else "Stopped"
            if preview:
                state = f"Preview {state}"
            frame_word = "Frame"
        else:
            key = (
                "play.preview_playing" if preview and playing
                else "play.preview_stopped" if preview
                else "play.playing" if playing
                else "play.stopped"
            )
            state = localization.text(key)
            frame_word = localization.text("play.frame")
        current = min(max(frame_index + 1, 1), max(frame_count, 1))
        self.playback_status_label.setText(
            f"{state} · {frame_word} {current} / {frame_count} · {fps} FPS"
        )

    def _on_current_cell_changed(
        self, row: int, column: int, previous_row: int, previous_column: int
    ) -> None:
        if self._project is None or row < 0 or column < 0:
            return
        layer_index = len(self._project.layers) - 1 - row
        if not (0 <= layer_index < len(self._project.layers)):
            return
        if not (0 <= column < self.table.columnCount()):
            return
        self._update_selection_label(layer_index, column)
        self.cell_selected.emit(layer_index, column)

    def refresh(
        self,
        project: Project,
        selected_layer: int = 0,
        selected_frame: int = 0,
        display_frame_count: int | None = None,
        preview: bool = False,
    ) -> None:
        """Rebuild the table while preserving a valid model selection."""
        self._project = project
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setRowCount(len(project.layers))
        frame_count = display_frame_count or len(project.frames)
        self._display_frame_count = frame_count
        self._preview = preview
        self.table.setColumnCount(frame_count)
        self.table.setHorizontalHeaderLabels(
            [str(index) for index in range(1, frame_count + 1)]
        )
        self.table.setVerticalHeaderLabels(
            [
                f"{'◉' if layer.visible else '○'}  {layer.name}"
                for layer in reversed(project.layers)
            ]
        )
        for display_row, layer in enumerate(reversed(project.layers)):
            for frame_index in range(frame_count):
                frame = (
                    project.frames[frame_index]
                    if frame_index < len(project.frames)
                    else None
                )
                pixels = None if frame is None else frame.layer_pixels.get(layer.id)
                marker = "■" if pixels is not None and pixels[..., 3].any() else "·"
                item = QTableWidgetItem(marker)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(
                    f"{layer.name} · Frame {frame_index + 1}"
                )
                self.table.setItem(display_row, frame_index, item)
        self.table.blockSignals(False)
        self.set_current_cell(
            project,
            selected_layer,
            selected_frame,
            display_frame_count=frame_count,
        )
        self.fps_spin.blockSignals(True)
        self.fps_spin.setValue(project.fps)
        self.fps_spin.blockSignals(False)

    def set_current_cell(
        self,
        project: Project,
        layer_index: int,
        frame_index: int,
        display_frame_count: int | None = None,
    ) -> None:
        """Select the cell corresponding to model indices without emitting edits."""
        if not project.layers or not project.frames:
            return
        layer_index = max(0, min(layer_index, len(project.layers) - 1))
        frame_count = display_frame_count or len(project.frames)
        frame_index = max(0, min(frame_index, frame_count - 1))
        display_row = len(project.layers) - 1 - layer_index
        self.table.blockSignals(True)
        self.table.setCurrentCell(display_row, frame_index)
        self.table.blockSignals(False)
        self._highlight_frame_column(frame_index)
        current_item = self.table.currentItem()
        if current_item is not None:
            self.table.scrollToItem(
                current_item, QAbstractItemView.ScrollHint.PositionAtCenter
            )
        self._update_selection_label(layer_index, frame_index)
        self.update_playback_status(
            self._playing,
            frame_index,
            frame_count,
            project.fps,
            preview=self._preview,
        )

    def _update_selection_label(self, layer_index: int, frame_index: int) -> None:
        if self._project is None:
            return
        self.selection_label.setText(
            f"{self._project.layers[layer_index].name} · Frame {frame_index + 1}"
        )

    def _highlight_frame_column(self, frame_index: int) -> None:
        highlight = QBrush(QColor("#34495e"))
        clear = QBrush()
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item is not None:
                    item.setBackground(highlight if column == frame_index else clear)
