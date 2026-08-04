"""Application-wide interface preferences."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QVBoxLayout


MIN_TIMELINE_FRAME_WIDTH = 20
DEFAULT_TIMELINE_FRAME_WIDTH = 36
MAX_TIMELINE_FRAME_WIDTH = 96


def timeline_frame_width(settings):
    try: value = int(settings.value("ui/timeline_frame_width", DEFAULT_TIMELINE_FRAME_WIDTH))
    except (TypeError, ValueError): value = DEFAULT_TIMELINE_FRAME_WIDTH
    value = max(MIN_TIMELINE_FRAME_WIDTH, min(MAX_TIMELINE_FRAME_WIDTH, value))
    settings.setValue("ui/timeline_frame_width", value)
    return value


class InterfaceSettingsDialog(QDialog):
    frame_width_changed = Signal(int)

    def __init__(self, settings, localization, parent=None):
        super().__init__(parent); self.settings=settings; self.localization=localization
        root=QVBoxLayout(self); self.form=QFormLayout(); row=QHBoxLayout()
        self.slider=QSlider(Qt.Orientation.Horizontal); self.spin=QSpinBox(); self.reset=QPushButton()
        for widget in (self.slider,self.spin): widget.setRange(MIN_TIMELINE_FRAME_WIDTH,MAX_TIMELINE_FRAME_WIDTH)
        value=timeline_frame_width(settings); self.slider.setValue(value); self.spin.setValue(value); self.spin.setSuffix(" px")
        row.addWidget(self.slider,1); row.addWidget(self.spin); self.form.addRow(QLabel(),row); root.addLayout(self.form); root.addWidget(self.reset)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); root.addWidget(self.buttons)
        self.slider.valueChanged.connect(self.spin.setValue); self.spin.valueChanged.connect(self.slider.setValue); self.spin.valueChanged.connect(self._apply)
        self.reset.clicked.connect(lambda:self.spin.setValue(DEFAULT_TIMELINE_FRAME_WIDTH)); self.buttons.rejected.connect(self.reject)
        self.retranslate()

    def _apply(self,value):
        self.settings.setValue("ui/timeline_frame_width",int(value)); self.frame_width_changed.emit(int(value))

    def retranslate(self):
        t=self.localization.text; self.setWindowTitle(t("interface.title")); self.form.labelForField(self.form.itemAt(0,QFormLayout.ItemRole.FieldRole).layout()).setText(t("interface.timeline_frame_width")); self.reset.setText(t("interface.restore_default")); self.spin.setToolTip(t("tooltip.timeline_frame_width")); self.slider.setToolTip(t("tooltip.timeline_frame_width"))
