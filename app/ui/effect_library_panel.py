"""Source Asset and generator library panel."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.models.source_asset import SourceAsset


class EffectLibraryPanel(QWidget):
    import_requested = Signal()
    add_emitter_requested = Signal()
    asset_selected = Signal(str)
    generator_selected = Signal(str)
    delete_asset_requested = Signal(str)
    delete_generator_requested = Signal(str)
    create_clip_requested = Signal(str)
    clip_selected = Signal(str)
    particle_selected = Signal(str)
    add_particle_requested = Signal(str)
    resource_open_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(210)
        layout = QVBoxLayout(self)
        self.title_label = QLabel("Effect Library")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.title_label)

        self.source_group = QGroupBox("Source Assets")
        source_layout = QVBoxLayout(self.source_group)
        self.import_button = QPushButton("Import Source Asset…")
        self.asset_list = QListWidget()
        self.asset_list.setObjectName("sourceAssetList")
        self.source_preview = QLabel("No source selected")
        self.source_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_preview.setMinimumHeight(112)
        self.source_preview.setStyleSheet("background: #252a31; color: #adb5bd;")
        self.source_info = QLabel("")
        self.delete_asset_button = QPushButton("Delete Source")
        source_layout.addWidget(self.import_button)
        source_layout.addWidget(self.asset_list)
        source_layout.addWidget(self.source_preview)
        source_layout.addWidget(self.source_info)
        source_layout.addWidget(self.delete_asset_button)
        layout.addWidget(self.source_group, 1)

        self.generator_group = QGroupBox("Legacy Clip Generators")
        generator_layout = QVBoxLayout(self.generator_group)
        self.add_emitter_button = QPushButton("Add Transform Emitter")
        self.generator_list = QListWidget()
        self.generator_list.setObjectName("generatorList")
        self.delete_generator_button = QPushButton("Delete Generator")
        generator_layout.addWidget(self.add_emitter_button)
        generator_layout.addWidget(self.generator_list)
        generator_layout.addWidget(self.delete_generator_button)
        layout.addWidget(self.generator_group, 1)

        self.clip_group = QGroupBox("Animation Clips")
        clip_layout = QVBoxLayout(self.clip_group)
        self.create_clip_button = QPushButton("Create Animation Clip")
        self.clip_list = QListWidget(); self.clip_list.setObjectName("animationClipList")
        clip_layout.addWidget(self.create_clip_button); clip_layout.addWidget(self.clip_list)
        layout.addWidget(self.clip_group, 1)

        self.particle_group = QGroupBox("Particle Emitters")
        particle_layout = QVBoxLayout(self.particle_group)
        self.add_particle_button = QPushButton("Add Particle Emitter")
        self.particle_list = QListWidget(); self.particle_list.setObjectName("particleEmitterList")
        particle_layout.addWidget(self.add_particle_button); particle_layout.addWidget(self.particle_list)
        layout.addWidget(self.particle_group, 1)

        self.import_button.clicked.connect(self.import_requested)
        self.add_emitter_button.clicked.connect(self.add_emitter_requested)
        self.asset_list.currentItemChanged.connect(self._asset_changed)
        self.generator_list.currentItemChanged.connect(self._generator_changed)
        self.delete_asset_button.clicked.connect(self._request_delete_asset)
        self.delete_generator_button.clicked.connect(self._request_delete_generator)
        self.create_clip_button.clicked.connect(self._request_create_clip)
        self.add_particle_button.clicked.connect(self._request_add_particle)
        self.clip_list.currentItemChanged.connect(lambda item, previous: self._typed_changed(item, "clip"))
        self.particle_list.currentItemChanged.connect(lambda item, previous: self._typed_changed(item, "particle"))
        self.asset_list.itemDoubleClicked.connect(lambda item:self.resource_open_requested.emit("source_asset",str(item.data(Qt.ItemDataRole.UserRole))))
        self.clip_list.itemDoubleClicked.connect(lambda item:self.resource_open_requested.emit("animation_clip",str(item.data(Qt.ItemDataRole.UserRole))))
        self._configure_help()

    def _configure_help(self) -> None:
        help_text = {
            self.import_button: "Import a PNG as a non-destructive project Source Asset.",
            self.asset_list: "Select an embedded source image and inspect its thumbnail.",
            self.add_emitter_button: "Create a Transform Emitter using the selected Source Asset.",
            self.generator_list: "Select a generator to edit its draft settings and preview.",
            self.delete_asset_button: "Delete an unused Source Asset after confirmation.",
            self.delete_generator_button: "Delete the generator and its dedicated Generated Layer.",
        }
        for widget, text in help_text.items():
            widget.setToolTip(text)
            widget.setStatusTip(text)

    def retranslate_ui(self, localization) -> None:
        t = localization.text
        self.title_label.setText(t("effects.library.title"))
        self.source_group.setTitle(t("effects.sources"))
        self.generator_group.setTitle(t("effects.legacy_clip_generators"))
        self.clip_group.setTitle(t("effects.animation_clips"))
        self.particle_group.setTitle(t("effects.particle_emitters"))
        self.create_clip_button.setText(t("effects.create_clip"))
        self.add_particle_button.setText(t("effects.add_particle"))
        self.import_button.setText(t("effects.import"))
        self.add_emitter_button.setText(t("effects.add_emitter"))
        self.delete_asset_button.setText(t("effects.delete_source"))
        self.delete_generator_button.setText(t("effects.delete_generator"))
        if self.current_asset_id() is None:
            self.source_preview.setText(t("effects.no_source"))

    @staticmethod
    def _item(identifier: str, name: str) -> QListWidgetItem:
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, identifier)
        return item

    def refresh(self, project: Project) -> None:
        selected_asset = self.current_asset_id()
        selected_generator = self.current_generator_id()
        selected_clip = self.current_clip_id(); selected_particle = self.current_particle_id()
        self.asset_list.blockSignals(True)
        self.generator_list.blockSignals(True)
        self.asset_list.clear()
        self.generator_list.clear()
        self.clip_list.blockSignals(True); self.particle_list.blockSignals(True)
        self.clip_list.clear(); self.particle_list.clear()
        for asset in project.source_assets:
            self.asset_list.addItem(self._item(asset.id, asset.name))
        for generator in project.generators:
            self.generator_list.addItem(self._item(generator.id, generator.name))
        for clip in project.animation_clips: self.clip_list.addItem(self._item(clip.id, clip.name))
        for emitter in project.particle_emitters: self.particle_list.addItem(self._item(emitter.id, emitter.name))
        self._restore_selection(self.asset_list, selected_asset)
        self._restore_selection(self.generator_list, selected_generator)
        self._restore_selection(self.clip_list, selected_clip); self._restore_selection(self.particle_list, selected_particle)
        self.asset_list.blockSignals(False)
        self.generator_list.blockSignals(False)
        self.clip_list.blockSignals(False); self.particle_list.blockSignals(False)
        self.add_emitter_button.setEnabled(bool(project.source_assets))
        self.add_emitter_button.setVisible(False)
        self.generator_group.setVisible(bool(project.generators))
        self.delete_asset_button.setEnabled(self.current_asset_id() is not None)
        self.delete_generator_button.setEnabled(
            self.current_generator_id() is not None
        )
        self.create_clip_button.setEnabled(self.current_generator_id() is not None)
        self.add_particle_button.setEnabled(bool(project.animation_clips))
        asset = next(
            (item for item in project.source_assets if item.id == self.current_asset_id()),
            None,
        )
        self.show_asset(asset)

    @staticmethod
    def _restore_selection(widget: QListWidget, identifier: str | None) -> None:
        if identifier is None:
            return
        for row in range(widget.count()):
            if widget.item(row).data(Qt.ItemDataRole.UserRole) == identifier:
                widget.setCurrentRow(row)
                return

    def select_asset(self, identifier: str) -> None:
        self._restore_selection(self.asset_list, identifier)

    def select_generator(self, identifier: str) -> None:
        self._restore_selection(self.generator_list, identifier)

    def current_asset_id(self) -> str | None:
        item = self.asset_list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def current_generator_id(self) -> str | None:
        item = self.generator_list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def current_clip_id(self) -> str | None:
        item = self.clip_list.currentItem(); return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def current_particle_id(self) -> str | None:
        item = self.particle_list.currentItem(); return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def _typed_changed(self, current, kind: str) -> None:
        if current is None: return
        identifier = str(current.data(Qt.ItemDataRole.UserRole))
        for widget in (self.asset_list, self.generator_list, self.clip_list, self.particle_list):
            if (kind == "clip" and widget is self.clip_list) or (kind == "particle" and widget is self.particle_list): continue
            widget.clearSelection()
        (self.clip_selected if kind == "clip" else self.particle_selected).emit(identifier)

    def _request_create_clip(self) -> None:
        identifier = self.current_generator_id()
        if identifier: self.create_clip_requested.emit(identifier)

    def _request_add_particle(self) -> None:
        identifier = self.current_clip_id()
        if identifier is None and self.clip_list.count(): identifier = str(self.clip_list.item(0).data(Qt.ItemDataRole.UserRole))
        if identifier: self.add_particle_requested.emit(identifier)

    def _asset_changed(self, current: QListWidgetItem | None, previous) -> None:
        self.delete_asset_button.setEnabled(current is not None)
        if current is not None:
            self.generator_list.clearSelection()
            self.asset_selected.emit(str(current.data(Qt.ItemDataRole.UserRole)))

    def _generator_changed(self, current: QListWidgetItem | None, previous) -> None:
        self.delete_generator_button.setEnabled(current is not None)
        if current is not None:
            self.asset_list.clearSelection()
            self.generator_selected.emit(str(current.data(Qt.ItemDataRole.UserRole)))

    def _request_delete_asset(self) -> None:
        identifier = self.current_asset_id()
        if identifier:
            self.delete_asset_requested.emit(identifier)

    def _request_delete_generator(self) -> None:
        identifier = self.current_generator_id()
        if identifier:
            self.delete_generator_requested.emit(identifier)

    def show_asset(self, asset: SourceAsset | None) -> None:
        if asset is None:
            self.source_preview.setPixmap(QPixmap())
            self.source_preview.setText("No source selected")
            self.source_info.setText("")
            return
        pixels = np.ascontiguousarray(asset.pixels)
        image = QImage(
            pixels.data,
            asset.width,
            asset.height,
            pixels.strides[0],
            QImage.Format.Format_RGBA8888,
        ).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            104,
            104,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.source_preview.setText("")
        self.source_preview.setPixmap(pixmap)
        self.source_info.setText(
            f"{asset.width} × {asset.height} · Pivot "
            f"({asset.pivot_x:g}, {asset.pivot_y:g})"
        )
