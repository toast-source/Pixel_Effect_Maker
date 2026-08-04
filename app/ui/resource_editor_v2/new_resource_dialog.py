from pathlib import Path

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from app.models.source_asset import SourceAsset
from app.ui.focus_wheel_widgets import FocusWheelDoubleSpinBox, FocusWheelSpinBox

from .asset_inspector_widget import asset_durations


class NewResourceDialog(QDialog):
    def __init__(self, asset, localization, parent=None, defaults=None):
        super().__init__(parent)
        self.localization = localization
        root = QVBoxLayout(self); self.form = QFormLayout()
        self.name = QLineEdit(Path(asset.name).stem if asset is not None else "Resource 1"); self.name.setObjectName("newResourceName")
        self.width = FocusWheelSpinBox(); self.height = FocusWheelSpinBox(); self.fps = FocusWheelSpinBox(); self.frames = FocusWheelSpinBox(); self.duration = FocusWheelDoubleSpinBox(); self.loop = QCheckBox()
        self.length_unit=QComboBox();self.length_stack=QStackedWidget();self.length_stack.addWidget(self.frames);self.length_stack.addWidget(self.duration);self.length_info=QLabel();self.length_row=QWidget();length_layout=QVBoxLayout(self.length_row);length_layout.setContentsMargins(0,0,0,0);length_input=QHBoxLayout();length_input.addWidget(self.length_stack,1);length_input.addWidget(self.length_unit);length_layout.addLayout(length_input);length_layout.addWidget(self.length_info)
        for widget in (self.width, self.height): widget.setRange(1, 1024)
        self.fps.setRange(1, 120); self.frames.setRange(1, 512); self.duration.setRange(1/120, 60); self.duration.setDecimals(4);self.duration.setKeyboardTracking(False)
        self.width.setValue(asset.width if asset is not None else defaults[0]); self.height.setValue(asset.height if asset is not None else defaults[1])
        if asset is None:
            fps, seconds, loop = defaults[2], 1.0, defaults[3]
        elif isinstance(asset, SourceAsset):
            fps, seconds, loop = 12, 1.0, True
        else:
            seconds = max(.001, sum(asset_durations(asset)) / 1000)
            fps = max(1, min(120, round(len(asset.frames) / seconds)))
            loop = bool(asset.loop)
        self._duration_seconds = float(seconds)
        self.fps.setValue(fps); self.frames.setValue(max(1, round(fps * seconds))); self.duration.setValue(self.frames.value()/fps); self.loop.setChecked(loop)
        for widget in (self.name, self.width, self.height, self.fps, self.length_row, self.loop): self.form.addRow(" ", widget)
        root.addLayout(self.form)
        buttons = QHBoxLayout(); buttons.addStretch(); self.cancel = QPushButton(); self.create = QPushButton(); self.create.setObjectName("confirmCreateResourceButton"); self.create.setDefault(True); buttons.addWidget(self.cancel); buttons.addWidget(self.create); root.addLayout(buttons)
        self.cancel.clicked.connect(self.reject); self.create.clicked.connect(self.accept)
        self._syncing = False
        self.duration.valueChanged.connect(self._duration_changed)
        self.duration.editingFinished.connect(self._duration_finished)
        self.frames.valueChanged.connect(self._frames_changed)
        self.fps.valueChanged.connect(self._fps_changed)
        self.length_unit.currentIndexChanged.connect(self._unit_changed)
        self._configure_duration()
        self.retranslate()

    def _configure_duration(self):
        step = 1.0 / self.fps.value()
        self.duration.setMinimum(step)
        self.duration.setSingleStep(step)

    def _set_timing(self, frames):
        frames = max(1, min(self.frames.maximum(), int(frames)))
        self._duration_seconds = frames / self.fps.value()
        self._syncing = True
        try:
            with QSignalBlocker(self.frames): self.frames.setValue(frames)
            with QSignalBlocker(self.duration): self.duration.setValue(self._duration_seconds)
        finally:
            self._syncing = False
        self._update_length_info()

    def _duration_finished(self):
        if not self._syncing:
            self._set_timing(round(self.duration.value() * self.fps.value()))

    def _duration_changed(self,value):
        if not self._syncing:self._set_timing(round(float(value)*self.fps.value()))

    def _frames_changed(self, frames):
        if not self._syncing: self._set_timing(frames)

    def _fps_changed(self, fps):
        if self._syncing: return
        self._configure_duration()
        if self.length_unit.currentData()=="seconds":self._set_timing(round(self._duration_seconds * fps))
        else:self._set_timing(self.frames.value())

    def _unit_changed(self):
        seconds_mode=self.length_unit.currentData()=="seconds"
        if seconds_mode:
            self._duration_seconds=self.frames.value()/self.fps.value()
            with QSignalBlocker(self.duration):self.duration.setValue(self._duration_seconds)
        else:
            self._set_timing(round(self.duration.value()*self.fps.value()))
        self.length_stack.setCurrentWidget(self.duration if seconds_mode else self.frames)
        self._update_length_info()

    def _update_length_info(self):
        if not hasattr(self,"length_info") or not self.localization:return
        if self.length_unit.currentData()=="seconds":
            self.length_info.setText(self.localization.text("v2.length_seconds_info").format(fps=self.fps.value(),frames=self.frames.value()))
        else:
            self.length_info.setText(self.localization.text("v2.length_frame_info").format(fps=self.fps.value(),seconds=self.frames.value()/self.fps.value()))

    def values(self):
        return self.name.text().strip(), self.width.value(), self.height.value(), self.fps.value(), self.frames.value(), self.loop.isChecked()

    def retranslate(self):
        t = self.localization.text; self.setWindowTitle(t("v2.create_resource_title"))
        current=self.length_unit.currentData();self.length_unit.blockSignals(True);self.length_unit.clear();self.length_unit.addItem(t("v2.frames"),"frames");self.length_unit.addItem(t("v2.seconds"),"seconds");self.length_unit.setCurrentIndex(1 if current=="seconds" else 0);self.length_unit.blockSignals(False)
        for widget, key in ((self.name,"composition.name"),(self.width,"composition.width"),(self.height,"composition.height"),(self.fps,"composition.fps"),(self.length_row,"v2.length"),(self.loop,"composition.loop")):
            self.form.labelForField(widget).setText(t(key))
        self.create.setText(t("v2.create")); self.cancel.setText(t("v2.cancel"));self._unit_changed()
