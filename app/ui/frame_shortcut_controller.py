"""Focus-safe Previous/Next Frame shortcut handling."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QKeyCombination, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QAbstractSlider,
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


class FrameShortcutController(QObject):
    def __init__(
        self,
        window: QMainWindow,
        previous_callback: Callable[[], None],
        next_callback: Callable[[], None],
        allowed_timeline,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.callbacks = {
            "previous_frame": previous_callback,
            "next_frame": next_callback,
        }
        self.allowed_timelines = tuple(allowed_timeline) if isinstance(allowed_timeline,(list,tuple)) else (allowed_timeline,)
        self.allowed_timeline = self.allowed_timelines[0]
        self._shortcuts: list[QShortcut] = []

    def set_sequences(self, values: dict[str, list[str]]) -> None:
        for shortcut in self._shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._shortcuts.clear()
        for command_id, callback in self.callbacks.items():
            for sequence_text in values.get(command_id, []):
                if sequence_text == "<":
                    sequence = QKeySequence(
                        QKeyCombination(
                            Qt.KeyboardModifier.ShiftModifier, Qt.Key.Key_Comma
                        )
                    )
                elif sequence_text == ">":
                    sequence = QKeySequence(
                        QKeyCombination(
                            Qt.KeyboardModifier.ShiftModifier, Qt.Key.Key_Period
                        )
                    )
                else:
                    sequence = QKeySequence(sequence_text)
                shortcut = QShortcut(sequence, self.window)
                shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
                shortcut.activated.connect(
                    lambda callback=callback: self._activate_if_allowed(callback)
                )
                self._shortcuts.append(shortcut)

    def active_shortcut_count(self) -> int:
        return sum(item.isEnabled() for item in self._shortcuts)

    def _activate_if_allowed(self, callback: Callable[[], None]) -> None:
        if not self._blocked():
            callback()

    def _blocked(self) -> bool:
        application = QApplication.instance()
        if application is None or application.activeModalWidget() is not None:
            return True
        if application.activePopupWidget() is not None:
            return True
        focus = application.focusWidget()
        if focus is None:
            return False
        if isinstance(focus.window(), QDialog):
            return True
        current: QWidget | None = focus
        while current is not None:
            if current in self.allowed_timelines:
                return False
            if isinstance(
                current,
                (
                    QLineEdit,
                    QTextEdit,
                    QPlainTextEdit,
                    QAbstractSpinBox,
                    QKeySequenceEdit,
                    QAbstractSlider,
                ),
            ):
                return True
            if isinstance(current, QComboBox) and current.isEditable():
                return True
            if isinstance(current, QAbstractItemView):
                return True
            if isinstance(current, QAbstractScrollArea) and current not in self.allowed_timelines:
                return True
            current = current.parentWidget()
        return False
