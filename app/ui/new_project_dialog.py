"""Single-dialog new-project settings and validation."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class NewProjectSettings:
    """Validated values needed to construct a new project."""

    name: str
    width: int
    height: int
    fps: int
    loop: bool
    frame_count: int = 1


class NewProjectDialog(QDialog):
    """Collect all supported new-project settings in one modal dialog."""

    PRESETS = (16, 32, 48, 64, 96, 128, 256)
    MIN_CANVAS_SIZE = 1
    MAX_CANVAS_SIZE = 1024
    MIN_FPS = 1
    MAX_FPS = 120

    def __init__(self, parent: QWidget | None = None, localization=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        self._changing_preset = False
        self.localization = localization or getattr(parent, "localization", None)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit("Untitled")
        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        self.fps_spin = QSpinBox()
        self.frame_count_spin = QSpinBox()
        self.loop_check = QCheckBox("Loop animation")
        self.loop_check.setChecked(True)
        self.preset_combo = QComboBox()

        for spin in (self.width_spin, self.height_spin):
            spin.setRange(self.MIN_CANVAS_SIZE, self.MAX_CANVAS_SIZE)
            spin.setValue(64)
            spin.setSuffix(" px")
        self.fps_spin.setRange(self.MIN_FPS, self.MAX_FPS)
        self.fps_spin.setValue(12)
        self.fps_spin.setSuffix(" FPS")
        self.frame_count_spin.setRange(1, 999); self.frame_count_spin.setValue(1)
        for size in self.PRESETS:
            self.preset_combo.addItem(f"{size} × {size}", size)
        self.preset_combo.addItem("Custom", None)
        self.preset_combo.setCurrentText("64 × 64")

        self.form_labels = [
            QLabel("Project name"), QLabel("Canvas preset"), QLabel("Canvas width"),
            QLabel("Canvas height"), QLabel("Playback speed"), QLabel("Initial frames"),
        ]
        form.addRow(self.form_labels[0], self.name_edit)
        form.addRow(self.form_labels[1], self.preset_combo)
        form.addRow(self.form_labels[2], self.width_spin)
        form.addRow(self.form_labels[3], self.height_spin)
        form.addRow(self.form_labels[4], self.fps_spin)
        form.addRow(self.form_labels[5], self.frame_count_spin)
        form.addRow("", self.loop_check)
        layout.addLayout(form)

        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: #d9534f;")
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        self.create_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.create_button.setText("Create")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        self.width_spin.valueChanged.connect(self._mark_custom_size)
        self.height_spin.valueChanged.connect(self._mark_custom_size)
        self.name_edit.textChanged.connect(self._validate)
        self._validate()
        if self.localization is not None:
            self.localization.language_changed.connect(self.retranslate_ui)
            self.retranslate_ui()

    def retranslate_ui(self, *args) -> None:
        if self.localization is None:
            return
        t = self.localization.text
        self.setWindowTitle(t("dialog.new_project"))
        labels = tuple(t(key) for key in (
            "dialog.project_name", "dialog.canvas_preset", "dialog.canvas_width",
            "dialog.canvas_height", "dialog.playback_speed", "startup.initial_frames"
        ))
        for label, text in zip(self.form_labels, labels, strict=True):
            label.setText(text)
        self.loop_check.setText(t("dialog.loop"))
        self.create_button.setText(t("dialog.create"))
        custom_index = self.preset_combo.count() - 1
        self.preset_combo.setItemText(custom_index, t("dialog.custom"))
        self._validate()

    def _apply_preset(self) -> None:
        size = self.preset_combo.currentData()
        if size is None:
            return
        self._changing_preset = True
        self.width_spin.setValue(int(size))
        self.height_spin.setValue(int(size))
        self._changing_preset = False

    def _mark_custom_size(self) -> None:
        if self._changing_preset:
            return
        size = self.preset_combo.currentData()
        if size != self.width_spin.value() or size != self.height_spin.value():
            self.preset_combo.setCurrentIndex(self.preset_combo.count() - 1)

    def _validate(self) -> None:
        valid = bool(self.name_edit.text().strip())
        message = self.localization.text("dialog.enter_name") if self.localization else "Enter a project name."
        self.validation_label.setText("" if valid else message)
        self.create_button.setEnabled(valid)

    def settings(self) -> NewProjectSettings:
        """Return normalized settings from the constrained input widgets."""
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("project name must not be empty")
        return NewProjectSettings(
            name=name,
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            fps=self.fps_spin.value(),
            loop=self.loop_check.isChecked(),
            frame_count=self.frame_count_spin.value(),
        )
