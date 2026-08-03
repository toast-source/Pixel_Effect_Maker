"""Application entry point."""

from __future__ import annotations

import sys

from app.version import APP_NAME, get_display_name


def main(argv: list[str] | None = None) -> int:
    """Handle lightweight CLI options, then create and run the Qt application."""
    arguments = sys.argv[1:] if argv is None else argv
    if "--version" in arguments:
        print(get_display_name())
        return 0

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow

    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setOrganizationName("SOUTHPAW GAMES")
    window = MainWindow()
    window.show()
    if "--check" in arguments:
        QTimer.singleShot(0, application.quit)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
