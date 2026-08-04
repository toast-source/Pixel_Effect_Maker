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
    QHBoxLayout,
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
        self,
        shortcuts: dict[str, str | list[str]],
        parent: QWidget | None = None,
        localization=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.localization = localization
        self.help_label = QLabel(
            "Clear a shortcut to disable it. Duplicate shortcuts are not allowed."
        )
        layout.addWidget(self.help_label)
        form = QFormLayout()
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.primary_header = QLabel("Primary")
        self.alternate_header = QLabel("Alternate")
        header_layout.addWidget(self.primary_header)
        header_layout.addWidget(self.alternate_header)
        form.addRow("", header)
        self.editors: dict[str, QKeySequenceEdit] = {}
        self.alternate_editors: dict[str, QKeySequenceEdit] = {}
        self.command_labels: dict[str, QLabel] = {}
        for command in SHORTCUT_COMMANDS:
            values = shortcuts.get(command.key, [])
            if isinstance(values, str):
                values = [values]
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            primary = QKeySequenceEdit(QKeySequence(values[0] if values else ""))
            alternate = QKeySequenceEdit(
                QKeySequence(values[1] if len(values) > 1 else "")
            )
            primary.setClearButtonEnabled(True)
            alternate.setClearButtonEnabled(True)
            primary.setToolTip("Primary shortcut")
            alternate.setToolTip("Alternate shortcut")
            self.editors[command.key] = primary
            self.alternate_editors[command.key] = alternate
            row_layout.addWidget(primary)
            row_layout.addWidget(alternate)
            label = QLabel(command.label)
            self.command_labels[command.key] = label
            form.addRow(label, row)
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
        if localization is not None:
            localization.language_changed.connect(self.retranslate_ui)
            self.retranslate_ui()

    def retranslate_ui(self, *args) -> None:
        if self.localization is None:
            return
        t = self.localization.text
        self.setWindowTitle(t("shortcut.title"))
        for key, label in self.command_labels.items():
            label.setText(t(f"shortcut.{key}"))
        self.restore_button.setText(t("shortcut.restore"))
        self.apply_button.setText(t("shortcut.apply"))
        self.primary_header.setText(t("shortcut.primary"))
        self.alternate_header.setText(t("shortcut.alternate"))

    def current_shortcuts(self) -> dict[str, list[str]]:
        return {
            key: [
                sequence
                for sequence in (
                    editor.keySequence().toString(
                        QKeySequence.SequenceFormat.PortableText
                    ),
                    self.alternate_editors[key].keySequence().toString(
                        QKeySequence.SequenceFormat.PortableText
                    ),
                )
                if sequence
            ]
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
        for key, shortcuts in DEFAULT_SHORTCUTS.items():
            self.editors[key].setKeySequence(
                QKeySequence(shortcuts[0] if shortcuts else "")
            )
            self.alternate_editors[key].setKeySequence(
                QKeySequence(shortcuts[1] if len(shortcuts) > 1 else "")
            )
        self.error_label.clear()

    def accept(self) -> None:
        if self.apply_changes():
            super().accept()
