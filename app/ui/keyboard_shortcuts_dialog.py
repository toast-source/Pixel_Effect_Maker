"""Keyboard shortcut preferences dialog."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QKeySequenceEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.shortcuts import (
    DEFAULT_SHORTCUTS,
    SHORTCUT_COMMANDS,
    ShortcutConfigurationError,
    validate_shortcuts,
)


class KeyboardShortcutsDialog(QDialog):
    """Edit configurable shortcuts and reject duplicate assignments."""

    shortcuts_applied = Signal(object)

    def __init__(
        self, shortcuts: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Clear a shortcut to disable it. Duplicate shortcuts are not allowed.")
        )
        form = QFormLayout()
        self.editors: dict[str, QKeySequenceEdit] = {}
        for command in SHORTCUT_COMMANDS:
            editor = QKeySequenceEdit(QKeySequence(shortcuts.get(command.key, "")))
            editor.setClearButtonEnabled(True)
            self.editors[command.key] = editor
            form.addRow(command.label, editor)
        layout.addLayout(form)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #d9534f;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.restore_button = buttons.addButton(
            "Restore Defaults", QDialogButtonBox.ButtonRole.ResetRole
        )
        self.apply_button = buttons.addButton(
            "Apply", QDialogButtonBox.ButtonRole.ApplyRole
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.restore_button.clicked.connect(self.restore_defaults)
        self.apply_button.clicked.connect(self.apply_changes)
        layout.addWidget(buttons)

    def current_shortcuts(self) -> dict[str, str]:
        return {
            key: editor.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            )
            for key, editor in self.editors.items()
        }

    def apply_changes(self) -> bool:
        try:
            shortcuts = validate_shortcuts(self.current_shortcuts())
        except ShortcutConfigurationError as exc:
            self.error_label.setText(str(exc))
            return False
        self.error_label.clear()
        self.shortcuts_applied.emit(shortcuts)
        return True

    def restore_defaults(self) -> None:
        for key, shortcut in DEFAULT_SHORTCUTS.items():
            self.editors[key].setKeySequence(QKeySequence(shortcut))
        self.error_label.clear()

    def accept(self) -> None:
        if self.apply_changes():
            super().accept()
