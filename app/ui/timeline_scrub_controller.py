"""Shared mouse-drag frame scrubbing for timeline item views."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt


class TimelineScrubController(QObject):
    def __init__(self, table, select: Callable[[int, int], None], start: Callable[[], None], parent=None):
        super().__init__(parent or table)
        self.table = table
        self.viewport = table.viewport()
        self.select = select
        self.start = start
        self.scrubbing = False
        self.last_column = -1
        self.viewport.installEventFilter(self)

    def _cell(self, position):
        if self.table.columnCount() <= 0 or self.table.rowCount() <= 0:
            return None
        column = self.table.columnAt(round(position.x()))
        if column < 0:
            column = 0 if position.x() < 0 else self.table.columnCount() - 1
        row = self.table.rowAt(round(position.y()))
        if row < 0:
            row = max(0, self.table.currentRow())
        return row, max(0, min(column, self.table.columnCount() - 1))

    def _select(self, position):
        cell = self._cell(position)
        if cell is None:
            return
        row, column = cell
        if column == self.last_column:
            return
        self.last_column = column
        self.select(row, column)

    def eventFilter(self, watched, event):
        if watched is not self.viewport:
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self._cell(event.position()) is None:
                return False
            self.scrubbing = True
            self.last_column = -1
            self.start()
            self._select(event.position())
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseMove and self.scrubbing:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._select(event.position())
                event.accept()
                return True
            self.scrubbing = False
        if event.type() == QEvent.Type.MouseButtonRelease and self.scrubbing:
            self._select(event.position())
            self.scrubbing = False
            event.accept()
            return True
        return super().eventFilter(watched, event)
