"""Editable project settings dialog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.services.canvas_resize_service import CanvasAnchor, CanvasResizeMode
from app.version import get_display_name


@dataclass(frozen=True, slots=True)
class ProjectSettingsValues:
    """Validated editable project settings."""

    name: str
    fps: int
    loop: bool
    width: int
    height: int
    resize_mode: CanvasResizeMode
    anchor: CanvasAnchor


class ProjectSettingsDialog(QDialog):
    """Edit general and canvas settings while showing compact metadata."""

    def __init__(
        self,
        project: Project,
        project_path: Path | None,
        apply_callback: Callable[[ProjectSettingsValues], bool],
        parent: QWidget | None = None,
        localization=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.setModal(True)
        self._apply_callback = apply_callback
        self.localization = localization

        layout = QVBoxLayout(self)
        self.general_group = QGroupBox("General")
        general_form = QFormLayout(self.general_group)
        self.name_edit = QLineEdit(project.name)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(project.fps)
        self.loop_check = QCheckBox("Loop animation")
        self.loop_check.setChecked(project.loop)
        self.name_label = QLabel("Project Name")
        self.fps_label = QLabel("FPS")
        general_form.addRow(self.name_label, self.name_edit)
        general_form.addRow(self.fps_label, self.fps_spin)
        general_form.addRow("", self.loop_check)
        layout.addWidget(self.general_group)

        self.canvas_group = QGroupBox("Canvas")
        canvas_layout = QVBoxLayout(self.canvas_group)
        canvas_form = QFormLayout()
        self.current_size_label = QLabel(f"{project.width} × {project.height}")
        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        for spin, value in (
            (self.width_spin, project.width),
            (self.height_spin, project.height),
        ):
            spin.setRange(1, 1024)
            spin.setValue(value)
            spin.setSuffix(" px")
        self.current_size_field_label = QLabel("Current Size")
        self.width_label = QLabel("New Width")
        self.height_label = QLabel("New Height")
        canvas_form.addRow(self.current_size_field_label, self.current_size_label)
        canvas_form.addRow(self.width_label, self.width_spin)
        canvas_form.addRow(self.height_label, self.height_spin)
        canvas_layout.addLayout(canvas_form)

        self.canvas_only_radio = QRadioButton(CanvasResizeMode.CANVAS_ONLY.value)
        self.scale_radio = QRadioButton(CanvasResizeMode.SCALE.value)
        self.canvas_only_radio.setChecked(True)
        canvas_layout.addWidget(self.canvas_only_radio)
        canvas_layout.addWidget(
            QLabel("Keep existing pixels at their current size and only change the canvas area.")
        )
        canvas_layout.addWidget(self.scale_radio)
        canvas_layout.addWidget(
            QLabel("Resize the canvas and scale all frame and layer pixels to the new size.")
        )

        self.anchor_group = QGroupBox("Anchor")
        anchor_grid = QGridLayout(self.anchor_group)
        self.anchor_buttons = QButtonGroup(self)
        anchors = (
            (CanvasAnchor.TOP_LEFT, "↖", 0, 0),
            (CanvasAnchor.TOP_CENTER, "↑", 0, 1),
            (CanvasAnchor.TOP_RIGHT, "↗", 0, 2),
            (CanvasAnchor.CENTER_LEFT, "←", 1, 0),
            (CanvasAnchor.CENTER, "●", 1, 1),
            (CanvasAnchor.CENTER_RIGHT, "→", 1, 2),
            (CanvasAnchor.BOTTOM_LEFT, "↙", 2, 0),
            (CanvasAnchor.BOTTOM_CENTER, "↓", 2, 1),
            (CanvasAnchor.BOTTOM_RIGHT, "↘", 2, 2),
        )
        self.anchor_by_button: dict[QPushButton, CanvasAnchor] = {}
        for anchor, text, row, column in anchors:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setToolTip(anchor.value)
            self.anchor_buttons.addButton(button)
            self.anchor_by_button[button] = anchor
            anchor_grid.addWidget(button, row, column)
            if anchor is CanvasAnchor.CENTER:
                button.setChecked(True)
        canvas_layout.addWidget(self.anchor_group)
        layout.addWidget(self.canvas_group)

        self.info_label = QLabel(
            f"File: {project_path if project_path else 'Not Saved'}\n"
            f"Frames: {len(project.frames)}    Layers: {len(project.layers)}    "
            f"Format: {project.format_version}\nApplication: {get_display_name()}"
        )
        self.info_label.setStyleSheet("color: #777;")
        layout.addWidget(self.info_label)

        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: #d9534f;")
        layout.addWidget(self.validation_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply_button = buttons.addButton(
            "Apply", QDialogButtonBox.ButtonRole.ApplyRole
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self.apply_changes)
        layout.addWidget(buttons)

        self.name_edit.textChanged.connect(self._validate)
        self.scale_radio.toggled.connect(self.anchor_group.setDisabled)
        self._validate()
        if localization is not None:
            localization.language_changed.connect(self.retranslate_ui)
            self.retranslate_ui()

    def retranslate_ui(self, *args) -> None:
        if self.localization is None:
            return
        t = self.localization.text
        self.setWindowTitle(t("dialog.project_settings"))
        self.general_group.setTitle(t("dialog.general"))
        self.canvas_group.setTitle(t("dialog.canvas"))
        self.anchor_group.setTitle(t("dialog.anchor"))
        self.name_label.setText(t("dialog.project_name"))
        self.fps_label.setText("FPS")
        self.current_size_field_label.setText(t("dialog.current_size"))
        self.width_label.setText(t("dialog.new_width"))
        self.height_label.setText(t("dialog.new_height"))
        self.loop_check.setText(t("dialog.loop"))
        self.canvas_only_radio.setText(t("dialog.canvas_only"))
        self.scale_radio.setText(t("dialog.scale_canvas"))
        self.apply_button.setText(t("shortcut.apply"))
        self._validate()

    def _validate(self) -> None:
        valid = bool(self.name_edit.text().strip())
        message = self.localization.text("dialog.enter_name") if self.localization else "Enter a project name."
        self.validation_label.setText("" if valid else message)
        self.apply_button.setEnabled(valid)

    def settings(self) -> ProjectSettingsValues:
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("project name must not be empty")
        checked = self.anchor_buttons.checkedButton()
        anchor = self.anchor_by_button.get(checked, CanvasAnchor.CENTER)
        mode = (
            CanvasResizeMode.SCALE
            if self.scale_radio.isChecked()
            else CanvasResizeMode.CANVAS_ONLY
        )
        return ProjectSettingsValues(
            name=name,
            fps=self.fps_spin.value(),
            loop=self.loop_check.isChecked(),
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            resize_mode=mode,
            anchor=anchor,
        )

    def apply_changes(self) -> bool:
        try:
            values = self.settings()
        except ValueError as exc:
            self.validation_label.setText(str(exc))
            return False
        if not self._apply_callback(values):
            return False
        self.current_size_label.setText(f"{values.width} × {values.height}")
        return True

    def accept(self) -> None:
        if self.apply_changes():
            super().accept()
