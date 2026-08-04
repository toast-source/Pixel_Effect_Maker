"""Project choice shown before the main editor on normal application startup."""

from pathlib import Path

from PySide6.QtWidgets import QDialogButtonBox, QFileDialog, QMessageBox

from app.services.project_io import ProjectIOError, load_project
from app.ui.new_project_dialog import NewProjectDialog


class StartupDialog(NewProjectDialog):
    def __init__(self, parent=None, localization=None):
        super().__init__(parent, localization)
        self.opened_project = None
        self.opened_path: Path | None = None
        self.open_button = self.button_box.addButton(
            "Open Project…", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.open_button.clicked.connect(self._open_project)
        self.retranslate_ui()

    def retranslate_ui(self, *args):
        super().retranslate_ui(*args)
        if not hasattr(self, "open_button"):
            return
        t = self.localization.text if self.localization else lambda key: key
        self.setWindowTitle(t("startup.title"))
        self.create_button.setText(t("startup.create"))
        self.open_button.setText(t("startup.open"))

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.localization.text("startup.open") if self.localization else "Open Project…",
            "projects", "Pixel Effect Project (*.peffect.json)"
        )
        if not path:
            return
        try:
            self.opened_project = load_project(path)
        except ProjectIOError as exc:
            QMessageBox.critical(self, self.localization.text("error.open") if self.localization else "Open Project", str(exc))
            return
        self.opened_path = Path(path)
        self.accept()
