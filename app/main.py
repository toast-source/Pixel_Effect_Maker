"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from app.version import APP_NAME, get_display_name


def main(argv: list[str] | None = None) -> int:
    """Handle lightweight CLI options, then create and run the Qt application."""
    arguments = sys.argv[1:] if argv is None else argv
    if "--version" in arguments:
        print(get_display_name())
        return 0

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QDialog

    from app.ui.main_window import MainWindow
    from app.ui.startup_dialog import StartupDialog
    from app.services.project_io import load_project

    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setOrganizationName("SOUTHPAW GAMES")
    if "--check" in arguments:
        window = MainWindow()
        window.show()
        QTimer.singleShot(0, application.quit)
        return application.exec()
    project_paths = [value for value in arguments if not value.startswith("-")]
    if project_paths:
        project = load_project(project_paths[0])
        window = MainWindow(initial_project=project)
        window.project_path = Path(project_paths[0])
    else:
        window = MainWindow()
        startup = StartupDialog(None, window.localization)
        if startup.exec() != QDialog.DialogCode.Accepted:
            return 0
        if startup.opened_project is not None:
            window.project = startup.opened_project
            window.project_path = startup.opened_path
            window._refresh_all()
        else:
            window.apply_new_project_settings(startup.settings())
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
