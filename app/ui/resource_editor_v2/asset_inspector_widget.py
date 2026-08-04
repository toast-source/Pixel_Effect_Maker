from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton, QFormLayout, QVBoxLayout, QWidget

from app.models.source_asset import SourceAsset
from app.ui.focus_wheel_widgets import FocusWheelDoubleSpinBox


def asset_frames(asset):
    return [asset.pixels] if isinstance(asset, SourceAsset) else asset.frames


def asset_durations(asset):
    if isinstance(asset, SourceAsset):
        return [100]
    fallback = max(1, round(1000 / max(1, asset.fps)))
    values = asset.frame_durations_ms or [fallback] * len(asset.frames)
    return values if len(values) == len(asset.frames) else [fallback] * len(asset.frames)


class AssetPreviewCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.asset = None
        self.frame = 0
        self.setMinimumSize(320, 260)

    def set_asset(self, asset, frame=0):
        self.asset, self.frame = asset, frame
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#20242b"))
        if self.asset is None:
            return
        pixels = np.ascontiguousarray(asset_frames(self.asset)[self.frame])
        scale = max(1, min(32, int(min(self.width() / pixels.shape[1], self.height() / pixels.shape[0]))))
        rect = QRectF((self.width() - pixels.shape[1] * scale) / 2, (self.height() - pixels.shape[0] * scale) / 2, pixels.shape[1] * scale, pixels.shape[0] * scale)
        tile = max(4, scale * 2)
        for y in range(int(rect.top()), int(rect.bottom()) + 1, tile):
            for x in range(int(rect.left()), int(rect.right()) + 1, tile):
                painter.fillRect(x, y, tile, tile, QColor("#dfe3e8") if ((x - int(rect.left())) // tile + (y - int(rect.top())) // tile) % 2 else QColor("#aeb4bc"))
        image = QImage(pixels.data, pixels.shape[1], pixels.shape[0], pixels.strides[0], QImage.Format.Format_RGBA8888).copy()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(rect, QPixmap.fromImage(image), QRectF(0, 0, pixels.shape[1], pixels.shape[0]))


class AssetFrameStrip(QListWidget):
    frame_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setMaximumHeight(62)
        self.currentRowChanged.connect(lambda row: row >= 0 and self.frame_selected.emit(row))

    def set_asset(self, asset, frame=0):
        self.blockSignals(True)
        self.clear()
        if asset:
            for index in range(len(asset_frames(asset))):
                self.addItem(QListWidgetItem(str(index + 1)))
            self.setCurrentRow(frame)
        self.blockSignals(False)


class AssetInspectorWidget(QWidget):
    create_requested = Signal()
    reimport_requested = Signal()
    pivot_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.title = QLabel()
        self.info = QLabel()
        self.pivot_x = FocusWheelDoubleSpinBox(); self.pivot_y = FocusWheelDoubleSpinBox()
        for widget in (self.pivot_x, self.pivot_y): widget.setRange(-4096, 4096)
        self.form = QFormLayout(); self.form.addRow(" ", self.pivot_x); self.form.addRow(" ", self.pivot_y)
        self.center_button = QPushButton(); self.reimport_button = QPushButton(); self.create_button = QPushButton()
        self.create_button.setObjectName("createResourceFromAssetButton")
        self.create_button.setDefault(True)
        layout.addWidget(self.title); layout.addWidget(self.info); layout.addLayout(self.form)
        for widget in (self.center_button, self.reimport_button, self.create_button): layout.addWidget(widget)
        layout.addStretch()
        self.create_button.clicked.connect(self.create_requested); self.reimport_button.clicked.connect(self.reimport_requested)
        self.center_button.clicked.connect(self._center)
        self.pivot_x.valueChanged.connect(self._pivot); self.pivot_y.valueChanged.connect(self._pivot)
        self.asset = None; self._loading = False

    def set_asset(self, asset):
        self.asset = asset; self._loading = True
        if asset:
            self.info.setText(f"{asset.source_format.upper()} · {asset.width} × {asset.height} · {len(asset_frames(asset))}")
            self.pivot_x.setValue(asset.pivot_x); self.pivot_y.setValue(asset.pivot_y)
        self._loading = False

    def _pivot(self, *args):
        if not self._loading and self.asset: self.pivot_changed.emit(self.pivot_x.value(), self.pivot_y.value())

    def _center(self):
        if self.asset:
            self.pivot_x.setValue(self.asset.width / 2); self.pivot_y.setValue(self.asset.height / 2)

    def retranslate(self, localization):
        t = localization.text
        self.title.setText(t("v2.asset_inspector"))
        self.form.labelForField(self.pivot_x).setText(t("v2.asset_pivot_x")); self.form.labelForField(self.pivot_y).setText(t("v2.asset_pivot_y"))
        self.center_button.setText(t("v2.center_asset_pivot")); self.reimport_button.setText(t("resource.reimport")); self.create_button.setText(t("v2.create_from_asset"))
        self.create_button.setToolTip(t("v2.create_from_asset_tip"))
