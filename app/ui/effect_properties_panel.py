"""Editable Transform Emitter properties panel."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.effect_generator import (
    Distribution,
    Easing,
    TransformEmitter,
    TransformEmitterSettings,
)
from app.models.project import Project
from .focus_wheel_widgets import (
    FocusWheelComboBox,
    FocusWheelDoubleSpinBox,
    FocusWheelSpinBox,
)


class EffectPropertiesPanel(QScrollArea):
    generate_requested = Signal(str, object)
    reset_requested = Signal(str)
    draft_changed = Signal(str, object)
    refresh_preview_requested = Signal(str)
    revert_requested = Signal(str)
    auto_preview_changed = Signal(bool)
    gizmo_mode_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(360)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.generator_id: str | None = None
        self._loading = False
        self._localization = None
        self._preview_state = "applied"
        self.groups: dict[str, QGroupBox] = {}
        self.group_rows: dict[str, list[tuple[QLabel, QWidget]]] = {}
        self.field_labels: dict[str, QLabel] = {}
        body = QWidget()
        body.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.layout = QVBoxLayout(body)
        self.title_label = QLabel("Effect Properties")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.layout.addWidget(self.title_label)
        self.empty_label = QLabel("Select a Transform Emitter")
        self.layout.addWidget(self.empty_label)
        self.gizmo_row = QWidget()
        gizmo_layout = QHBoxLayout(self.gizmo_row); gizmo_layout.setContentsMargins(0, 0, 0, 0)
        self.gizmo_buttons = {}
        for mode, label in (("move", "Move"), ("rotate", "Rotate"), ("scale", "Scale"), ("distribution", "Distribution")):
            button = QPushButton(label); button.setCheckable(True); self.gizmo_buttons[mode] = button; gizmo_layout.addWidget(button)
            button.clicked.connect(lambda checked=False, mode=mode: self._select_gizmo(mode))
        self.gizmo_buttons["move"].setChecked(True)
        self.edit_end_check = QCheckBox("Edit End")
        self.edit_end_check.toggled.connect(lambda checked: self.gizmo_mode_changed.emit(self.current_gizmo_mode(), checked))
        self.layout.addWidget(self.gizmo_row); self.layout.addWidget(self.edit_end_check)

        self.source_combo = FocusWheelComboBox()
        self._add_group("Source", (("Source Asset", self.source_combo),))

        self.output_frames = self._integer(1, 512)
        self.instance_count = self._integer(1, 256)
        self.start_frame = self._integer(0, 511)
        self.emission_interval = self._integer(0, 512)
        self.lifetime = self._integer(1, 512)
        self._add_group(
            "Timing",
            (
                ("Output Frames", self.output_frames),
                ("Instance Count", self.instance_count),
                ("Start Frame", self.start_frame),
                ("Emission Interval", self.emission_interval),
                ("Lifetime", self.lifetime),
            ),
        )

        self.distribution_combo = FocusWheelComboBox()
        for item in Distribution:
            self.distribution_combo.addItem(item.value, item.value)
        self.origin_x = self._number(-4096, 4096)
        self.origin_y = self._number(-4096, 4096)
        self.line_end_x = self._number(-4096, 4096)
        self.line_end_y = self._number(-4096, 4096)
        self.radius = self._number(0, 4096)
        self.angle_start = self._number(-3600, 3600)
        self.angle_end = self._number(-3600, 3600)
        distribution_rows = (
            ("Type", self.distribution_combo),
            ("Origin X", self.origin_x),
            ("Origin Y", self.origin_y),
            ("Line End X", self.line_end_x),
            ("Line End Y", self.line_end_y),
            ("Radius", self.radius),
            ("Start Angle", self.angle_start),
            ("End Angle", self.angle_end),
        )
        self.distribution_group, self.distribution_labels = self._add_group(
            "Distribution", distribution_rows, return_labels=True
        )

        self.offset_x_start = self._number(-4096, 4096)
        self.offset_y_start = self._number(-4096, 4096)
        self.offset_x_end = self._number(-4096, 4096)
        self.offset_y_end = self._number(-4096, 4096)
        self._add_group(
            "Motion",
            (
                ("Position X", self._pair(self.offset_x_start, self.offset_x_end)),
                ("Position Y", self._pair(self.offset_y_start, self.offset_y_end)),
            ),
        )

        self.rotation_start = self._number(-3600, 3600)
        self.rotation_end = self._number(-3600, 3600)
        self.scale_x_start = self._number(-16, 16, 1.0)
        self.scale_x_end = self._number(-16, 16, 1.0)
        self.scale_y_start = self._number(-16, 16, 1.0)
        self.scale_y_end = self._number(-16, 16, 1.0)
        self._add_group(
            "Transform",
            (
                ("Rotation", self._pair(self.rotation_start, self.rotation_end)),
                ("Scale X", self._pair(self.scale_x_start, self.scale_x_end)),
                ("Scale Y", self._pair(self.scale_y_start, self.scale_y_end)),
            ),
        )

        self.horizontal_tilt_start = self._number(-1, 1)
        self.horizontal_tilt_end = self._number(-1, 1)
        self.vertical_tilt_start = self._number(-1, 1)
        self.vertical_tilt_end = self._number(-1, 1)
        self.perspective_start = self._number(-1, 1)
        self.perspective_end = self._number(-1, 1)
        self._add_group(
            "Pseudo 3D",
            (
                ("Horizontal Tilt", self._pair(self.horizontal_tilt_start, self.horizontal_tilt_end)),
                ("Vertical Tilt", self._pair(self.vertical_tilt_start, self.vertical_tilt_end)),
                ("Perspective", self._pair(self.perspective_start, self.perspective_end)),
            ),
        )

        self.opacity_start = self._number(0, 1, 1.0)
        self.opacity_end = self._number(0, 1, 1.0)
        self._add_group("Opacity", (("Opacity", self._pair(self.opacity_start, self.opacity_end)),))
        self.easing_combo = FocusWheelComboBox()
        for item in Easing:
            self.easing_combo.addItem(item.value, item.value)
        self._add_group("Easing", (("Curve", self.easing_combo),))

        self.settings_status = QLabel("")
        self.display_mode_label = QLabel("Applied Frames")
        self.display_mode_label.setStyleSheet("font-weight: bold; color: #74c0fc;")
        self.auto_preview_check = QCheckBox("Auto Preview")
        self.auto_preview_check.setChecked(True)
        self.refresh_preview_button = QPushButton("Refresh Preview")
        self.generate_button = QPushButton("Apply to Frames")
        self.revert_button = QPushButton("Revert Changes")
        self.reset_button = QPushButton("Reset to Defaults")
        self.layout.addWidget(self.display_mode_label)
        self.layout.addWidget(self.settings_status)
        self.layout.addWidget(self.auto_preview_check)
        self.layout.addWidget(self.refresh_preview_button)
        self.layout.addWidget(self.generate_button)
        self.layout.addWidget(self.revert_button)
        self.layout.addWidget(self.reset_button)
        self.layout.addStretch(1)
        self.setWidget(body)
        self._controls = (
            body.findChildren(QSpinBox)
            + body.findChildren(QDoubleSpinBox)
            + body.findChildren(QComboBox)
        )
        for control in self._controls:
            if isinstance(control, QComboBox):
                control.currentIndexChanged.connect(self._mark_changed)
            else:
                control.valueChanged.connect(self._mark_changed)
        self.distribution_combo.currentTextChanged.connect(
            self._update_distribution_visibility
        )
        self.generate_button.clicked.connect(self._emit_generate)
        self.refresh_preview_button.clicked.connect(self._emit_refresh)
        self.revert_button.clicked.connect(self._emit_revert)
        self.reset_button.clicked.connect(self._emit_reset)
        self.auto_preview_check.toggled.connect(self.auto_preview_changed)
        self._configure_units_and_help()
        self.set_generator(None, None)

    def current_gizmo_mode(self) -> str:
        return next((mode for mode, button in self.gizmo_buttons.items() if button.isChecked()), "move")

    def _select_gizmo(self, mode: str) -> None:
        for key, button in self.gizmo_buttons.items(): button.setChecked(key == mode)
        self.gizmo_mode_changed.emit(mode, self.edit_end_check.isChecked())

    @staticmethod
    def _integer(minimum: int, maximum: int) -> QSpinBox:
        widget = FocusWheelSpinBox()
        widget.setRange(minimum, maximum)
        return widget

    @staticmethod
    def _number(minimum: float, maximum: float, value: float = 0.0) -> QDoubleSpinBox:
        widget = FocusWheelDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(3)
        widget.setValue(value)
        return widget

    @staticmethod
    def _pair(start: QWidget, end: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        start.setMinimumWidth(72)
        end.setMinimumWidth(72)
        layout.addWidget(start, 1)
        arrow = QLabel("→")
        arrow.setToolTip("Start → End over the instance lifetime")
        layout.addWidget(arrow)
        layout.addWidget(end, 1)
        return row

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """A background click disarms the previously focused wheel editor."""
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def _add_group(self, title, rows, return_labels=False):
        group = QGroupBox(title)
        self.groups[title] = group
        group.setCheckable(True)
        group.setChecked(title not in {"Pseudo 3D", "Easing"})
        form = QFormLayout(group)
        labels = {}
        stored_rows = []
        for name, widget in rows:
            label = QLabel(name)
            labels[name] = label
            self.field_labels[name] = label
            form.addRow(label, widget)
            stored_rows.append((label, widget))
        self.group_rows[title] = stored_rows
        group.toggled.connect(
            lambda checked, title=title: self._toggle_group(title, checked)
        )
        self._toggle_group(title, group.isChecked())
        self.layout.addWidget(group)
        if return_labels:
            return group, labels
        return group

    def _toggle_group(self, title: str, checked: bool) -> None:
        for label, widget in self.group_rows.get(title, []):
            label.setVisible(checked)
            widget.setVisible(checked)
        if checked and title == "Distribution" and hasattr(self, "distribution_labels"):
            self._update_distribution_visibility(
                str(self.distribution_combo.currentData())
            )

    def set_generator(
        self, generator: TransformEmitter | None, project: Project | None
    ) -> None:
        self._loading = True
        self.generator_id = None if generator is None else generator.id
        self.source_combo.clear()
        if project is not None:
            for asset in project.source_assets:
                self.source_combo.addItem(asset.name, asset.id)
        enabled = generator is not None
        self.widget().setEnabled(enabled)
        self.empty_label.setVisible(not enabled)
        if generator is not None:
            settings = generator.settings
            index = self.source_combo.findData(settings.source_asset_id)
            self.source_combo.setCurrentIndex(max(0, index))
            for name in (
                "output_frames", "instance_count", "start_frame",
                "emission_interval", "lifetime", "origin_x", "origin_y",
                "line_end_x", "line_end_y", "radius", "angle_start", "angle_end",
                "offset_x_start", "offset_y_start", "offset_x_end", "offset_y_end",
                "rotation_start", "rotation_end", "scale_x_start", "scale_x_end",
                "scale_y_start", "scale_y_end", "horizontal_tilt_start",
                "horizontal_tilt_end", "vertical_tilt_start", "vertical_tilt_end",
                "perspective_start", "perspective_end", "opacity_start", "opacity_end",
            ):
                getattr(self, name).setValue(getattr(settings, name))
            self.distribution_combo.setCurrentIndex(
                self.distribution_combo.findData(settings.distribution)
            )
            self.easing_combo.setCurrentIndex(
                self.easing_combo.findData(settings.easing)
            )
            self.settings_status.setText("Generated" if generator.generated_layer_id else "Not generated")
        else:
            self.settings_status.setText("")
        self._loading = False
        self._update_distribution_visibility(self.distribution_combo.currentText())

    def current_settings(self) -> TransformEmitterSettings:
        return TransformEmitterSettings(
            source_asset_id=str(self.source_combo.currentData() or ""),
            output_frames=self.output_frames.value(),
            instance_count=self.instance_count.value(),
            emission_interval=self.emission_interval.value(),
            lifetime=self.lifetime.value(),
            start_frame=self.start_frame.value(),
            distribution=str(self.distribution_combo.currentData()),
            origin_x=self.origin_x.value(), origin_y=self.origin_y.value(),
            line_end_x=self.line_end_x.value(), line_end_y=self.line_end_y.value(),
            radius=self.radius.value(), angle_start=self.angle_start.value(),
            angle_end=self.angle_end.value(),
            offset_x_start=self.offset_x_start.value(), offset_y_start=self.offset_y_start.value(),
            offset_x_end=self.offset_x_end.value(), offset_y_end=self.offset_y_end.value(),
            rotation_start=self.rotation_start.value(), rotation_end=self.rotation_end.value(),
            scale_x_start=self.scale_x_start.value(), scale_x_end=self.scale_x_end.value(),
            scale_y_start=self.scale_y_start.value(), scale_y_end=self.scale_y_end.value(),
            horizontal_tilt_start=self.horizontal_tilt_start.value(),
            horizontal_tilt_end=self.horizontal_tilt_end.value(),
            vertical_tilt_start=self.vertical_tilt_start.value(),
            vertical_tilt_end=self.vertical_tilt_end.value(),
            perspective_start=self.perspective_start.value(),
            perspective_end=self.perspective_end.value(),
            opacity_start=self.opacity_start.value(), opacity_end=self.opacity_end.value(),
            easing=str(self.easing_combo.currentData()),
        )

    def _mark_changed(self, *args) -> None:
        if not self._loading and self.generator_id is not None:
            self.settings_status.setText("Settings changed")
            self.display_mode_label.setText("Live Preview — Unapplied")
            self.draft_changed.emit(self.generator_id, self.current_settings())

    def _emit_generate(self) -> None:
        if self.generator_id:
            self.generate_requested.emit(self.generator_id, self.current_settings())

    def _emit_reset(self) -> None:
        if self.generator_id:
            self.reset_requested.emit(self.generator_id)

    def _emit_refresh(self) -> None:
        if self.generator_id:
            self.refresh_preview_requested.emit(self.generator_id)

    def _emit_revert(self) -> None:
        if self.generator_id:
            self.revert_requested.emit(self.generator_id)

    def set_settings(self, settings: TransformEmitterSettings) -> None:
        """Load a draft without changing the committed generator model."""
        self._loading = True
        index = self.source_combo.findData(settings.source_asset_id)
        self.source_combo.setCurrentIndex(max(0, index))
        for name in (
            "output_frames", "instance_count", "start_frame",
            "emission_interval", "lifetime", "origin_x", "origin_y",
            "line_end_x", "line_end_y", "radius", "angle_start", "angle_end",
            "offset_x_start", "offset_y_start", "offset_x_end", "offset_y_end",
            "rotation_start", "rotation_end", "scale_x_start", "scale_x_end",
            "scale_y_start", "scale_y_end", "horizontal_tilt_start",
            "horizontal_tilt_end", "vertical_tilt_start", "vertical_tilt_end",
            "perspective_start", "perspective_end", "opacity_start", "opacity_end",
        ):
            getattr(self, name).setValue(getattr(settings, name))
        self.distribution_combo.setCurrentIndex(
            self.distribution_combo.findData(settings.distribution)
        )
        self.easing_combo.setCurrentIndex(
            self.easing_combo.findData(settings.easing)
        )
        self._loading = False
        self._update_distribution_visibility(settings.distribution)

    def set_preview_state(self, state: str) -> None:
        self._preview_state = state
        key = {
            "applied": "state.applied",
            "settings_changed": "state.settings_changed",
            "updating": "state.updating",
            "ready": "state.ready",
            "failed": "state.failed",
        }.get(state)
        self.settings_status.setText(
            self._localization.text(key) if self._localization and key else state
        )
        self.display_mode_label.setText(
            self._localization.text(
                "effects.applied_frames" if state == "applied" else "effects.live_preview"
            )
            if self._localization
            else "Applied Frames" if state == "applied" else "Live Preview — Unapplied"
        )

    def _configure_units_and_help(self) -> None:
        for widget in (self.output_frames, self.start_frame, self.emission_interval, self.lifetime):
            widget.setSuffix(" frames")
        self.instance_count.setSuffix(" instances")
        for widget in (
            self.origin_x, self.origin_y, self.line_end_x, self.line_end_y,
            self.radius, self.offset_x_start, self.offset_y_start,
            self.offset_x_end, self.offset_y_end,
        ):
            widget.setSuffix(" px")
        for widget in (self.angle_start, self.angle_end, self.rotation_start, self.rotation_end):
            widget.setSuffix("°")
        for widget in (
            self.scale_x_start, self.scale_x_end, self.scale_y_start, self.scale_y_end,
            self.horizontal_tilt_start, self.horizontal_tilt_end,
            self.vertical_tilt_start, self.vertical_tilt_end,
            self.perspective_start, self.perspective_end,
            self.opacity_start, self.opacity_end,
        ):
            widget.setSuffix(" ×" if widget in (
                self.scale_x_start, self.scale_x_end, self.scale_y_start, self.scale_y_end
            ) else " (0–1)")
        help_text = {
            self.emission_interval: "How many frames to wait before emitting the next instance.",
            self.lifetime: "How many frames each instance remains visible.",
            self.horizontal_tilt_start: "Tilts the source as if it rotates left or right in depth.",
            self.perspective_start: "Makes one side appear nearer or farther than the other.",
            self.generate_button: "Render the draft and write it into the project frames.",
            self.refresh_preview_button: "Render the current draft without changing the project.",
            self.revert_button: "Return to the last applied settings without changing project pixels.",
            self.reset_button: "Change the draft to the generator defaults; Apply is still required.",
            self.auto_preview_check: "Refresh the non-destructive preview after a short delay.",
        }
        for widget in self._controls:
            widget.setToolTip("Adjust this generator setting. Preview changes are not saved until applied.")
        for widget, tooltip in help_text.items():
            widget.setToolTip(tooltip)
            widget.setStatusTip(tooltip)

    def retranslate_ui(self, localization) -> None:
        self._localization = localization
        t = localization.text
        self.title_label.setText(t("effects.properties.title"))
        self.empty_label.setText(t("effects.select_emitter"))
        self.auto_preview_check.setText(t("effects.auto_preview"))
        self.refresh_preview_button.setText(t("effects.refresh_preview"))
        self.generate_button.setText(t("effects.apply_to_frames"))
        self.revert_button.setText(t("effects.revert"))
        self.reset_button.setText(t("effects.reset_defaults"))
        for mode, key in (("move", "gizmo.move"), ("rotate", "gizmo.rotate"), ("scale", "gizmo.scale"), ("distribution", "gizmo.distribution")):
            self.gizmo_buttons[mode].setText(t(key))
            self.gizmo_buttons[mode].setToolTip(t("gizmo.tooltip." + mode))
        self.edit_end_check.setText(t("gizmo.edit_end"))
        section_keys = {
            "Source": "section.source", "Timing": "section.timing",
            "Distribution": "section.distribution", "Motion": "section.motion",
            "Transform": "section.transform", "Pseudo 3D": "section.pseudo3d",
            "Opacity": "section.opacity", "Easing": "section.easing",
        }
        field_keys = {
            "Source Asset": "field.source_asset", "Output Frames": "field.output_frames",
            "Instance Count": "field.instance_count", "Start Frame": "field.start_frame",
            "Emission Interval": "field.emission_interval", "Lifetime": "field.lifetime",
            "Type": "field.type", "Origin X": "field.origin_x", "Origin Y": "field.origin_y",
            "Line End X": "field.line_end_x", "Line End Y": "field.line_end_y",
            "Radius": "field.radius", "Start Angle": "field.start_angle",
            "End Angle": "field.end_angle", "Position X": "field.position_x",
            "Position Y": "field.position_y", "Rotation": "field.rotation",
            "Scale X": "field.scale_x", "Scale Y": "field.scale_y",
            "Horizontal Tilt": "field.horizontal_tilt", "Vertical Tilt": "field.vertical_tilt",
            "Perspective": "field.perspective", "Opacity": "field.opacity", "Curve": "field.curve",
        }
        for name, group in self.groups.items():
            group.setTitle(t(section_keys.get(name, name)))
        for name, label in self.field_labels.items():
            label.setText(t(field_keys.get(name, name)))
        distribution_keys = {
            "Point": "distribution.point", "Line": "distribution.line", "Circle": "distribution.circle"
        }
        for index in range(self.distribution_combo.count()):
            value = str(self.distribution_combo.itemData(index))
            self.distribution_combo.setItemText(
                index,
                t(distribution_keys.get(value, value)),
            )
        easing_keys = {"Linear": "easing.linear", "Ease In": "easing.ease_in", "Ease Out": "easing.ease_out"}
        for index in range(self.easing_combo.count()):
            value = str(self.easing_combo.itemData(index))
            self.easing_combo.setItemText(
                index,
                t(easing_keys.get(value, value)),
            )
        self.set_preview_state(self._preview_state)

    def _update_distribution_visibility(self, distribution: str) -> None:
        if distribution not in {item.value for item in Distribution}:
            distribution = str(self.distribution_combo.currentData())
        line = distribution == Distribution.LINE.value
        circle = distribution == Distribution.CIRCLE.value
        for name in ("Line End X", "Line End Y"):
            self.distribution_labels[name].setVisible(line)
        self.line_end_x.setVisible(line)
        self.line_end_y.setVisible(line)
        for name in ("Radius", "Start Angle", "End Angle"):
            self.distribution_labels[name].setVisible(circle)
        self.radius.setVisible(circle)
        self.angle_start.setVisible(circle)
        self.angle_end.setVisible(circle)
