"""Input widgets that only consume wheel changes while focused."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox


class _FocusWheelMixin:
    def wheelEvent(self, event) -> None:  # noqa: N802
        editor_focused = hasattr(self, "lineEdit") and self.lineEdit() is not None and self.lineEdit().hasFocus()
        if self.hasFocus() or editor_focused:
            super().wheelEvent(event)
        else:
            event.ignore()


class FocusWheelSpinBox(_FocusWheelMixin, QSpinBox):
    pass


class FocusWheelDoubleSpinBox(_FocusWheelMixin, QDoubleSpinBox):
    pass


class FocusWheelComboBox(_FocusWheelMixin, QComboBox):
    pass
