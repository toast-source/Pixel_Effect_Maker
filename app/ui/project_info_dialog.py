"""Read-only current-project information dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.version import get_display_name


class ProjectInfoDialog(QDialog):
    """Present a snapshot of current project and application metadata."""

    def __init__(
        self,
        project: Project,
        project_path: Path | None,
        dirty: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Project Info")
        self.setModal(True)
        self.values = {
            "Project Name": project.name,
            "File": str(project_path) if project_path else "Not Saved",
            "Canvas": f"{project.width} × {project.height}",
            "Frames": str(len(project.frames)),
            "Layers": str(len(project.layers)),
            "FPS": str(project.fps),
            "Loop": "Enabled" if project.loop else "Disabled",
            "Format Version": str(project.format_version),
            "Application": get_display_name(),
            "Modified": "Yes" if dirty else "No",
        }
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.value_labels: dict[str, QLabel] = {}
        for label, value in self.values.items():
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.value_labels[label] = value_label
            form.addRow(label, value_label)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
