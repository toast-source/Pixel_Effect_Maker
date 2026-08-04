"""Focus-aware keyboard shortcut controller for animation playback."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QKeySequenceEdit,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)


class PlaybackShortcutController(QObject):
    """Own the sole keyboard path to the playback toggle command."""

    def __init__(
        self, window: QMainWindow, toggle_callback: Callable[[], None]
    ) -> None:
        super().__init__(window)
        self.window = window
        self.toggle_callback = toggle_callback
        self.sequence_text = ""
        self._shortcuts: list[QShortcut] = []

    def set_sequence(self, sequence_text: str) -> None:
        self.set_sequences([sequence_text] if sequence_text else [])

    def set_sequences(self, sequence_texts: list[str]) -> None:
        """Replace all playback key bindings without accumulating connections."""
        for shortcut in self._shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._shortcuts.clear()
        self.sequence_text = sequence_texts[0] if sequence_texts else ""
        if not sequence_texts:
            return

        sequences: list[QKeySequence] = []
        for sequence_text in sequence_texts:
            if sequence_text == "Enter":
                sequences.extend(
                    (
                        QKeySequence(Qt.Key.Key_Return),
                        QKeySequence(Qt.Key.Key_Enter),
                    )
                )
            else:
                sequences.append(QKeySequence(sequence_text))
        for sequence in sequences:
            shortcut = QShortcut(sequence, self.window)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(self._activate_if_allowed)
            self._shortcuts.append(shortcut)

    def active_shortcut_count(self) -> int:
        """Return the number of enabled bindings, primarily for diagnostics."""
        return sum(shortcut.isEnabled() for shortcut in self._shortcuts)

    def _activate_if_allowed(self) -> None:
        if self._is_blocked_context():
            return
        self.toggle_callback()

    def _is_blocked_context(self) -> bool:
        application = QApplication.instance()
        if application is None:
            return True
        if application.activeModalWidget() is not None:
            return True
        if application.activePopupWidget() is not None:
            return True
        focus = application.focusWidget()
        if focus is None:
            return False
        if isinstance(focus.window(), QDialog):
            return True
        return self._is_input_widget(focus)

    @staticmethod
    def _is_input_widget(widget: QWidget) -> bool:
        current: QWidget | None = widget
        while current is not None:
            if isinstance(
                current,
                (
                    QLineEdit,
                    QTextEdit,
                    QPlainTextEdit,
                    QAbstractSpinBox,
                    QKeySequenceEdit,
                    QAbstractButton,
                ),
            ):
                return True
            if isinstance(current, QComboBox) and current.isEditable():
                return True
            if isinstance(current, QAbstractItemView):
                try:
                    if current.state() == QAbstractItemView.State.EditingState:
                        return True
                except RuntimeError:
                    return True
            current = current.parentWidget()
        return False
