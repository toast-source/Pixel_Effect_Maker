from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget


class AssetBrowserPanel(QWidget):
    asset_selected = Signal(str, str)
    composition_selected = Signal(str)
    import_requested = Signal()
    asset_delete_requested = Signal(str, str)
    composition_delete_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.assets_label = QLabel()
        self.asset_list = QListWidget()
        self.asset_list.setObjectName("resourceV2AssetList")
        self.import_button = QPushButton()
        self.delete_asset_button = QPushButton()
        self.resources_label = QLabel()
        self.resource_list = QListWidget()
        self.delete_resource_button = QPushButton()
        self.resource_list.setObjectName("resourceV2CompositionList")
        for widget in (self.assets_label, self.asset_list, self.import_button, self.delete_asset_button, self.resources_label, self.resource_list, self.delete_resource_button):
            layout.addWidget(widget)
        self.asset_list.currentItemChanged.connect(self._asset_changed)
        self.resource_list.currentItemChanged.connect(self._resource_changed)
        self.asset_list.itemClicked.connect(self._asset_clicked)
        self.resource_list.itemClicked.connect(self._resource_clicked)
        self.import_button.clicked.connect(self.import_requested)
        self.delete_asset_button.clicked.connect(self._delete_asset); self.delete_resource_button.clicked.connect(self._delete_resource)
        self.delete_asset_button.hide(); self.delete_resource_button.hide()

    def refresh(self, project, asset_selection=None, composition_id=None):
        self.asset_list.blockSignals(True)
        self.resource_list.blockSignals(True)
        self.asset_list.clear()
        self.resource_list.clear()
        for kind, items in (("source_asset", project.source_assets), ("animation_clip", project.animation_clips)):
            for asset in items:
                item = QListWidgetItem(asset.name)
                item.setData(Qt.ItemDataRole.UserRole, (kind, asset.id))
                self.asset_list.addItem(item)
                if asset_selection == (kind, asset.id):
                    self.asset_list.setCurrentItem(item)
        for composition in project.resource_compositions:
            item = QListWidgetItem(composition.name)
            item.setData(Qt.ItemDataRole.UserRole, composition.id)
            self.resource_list.addItem(item)
            if composition_id == composition.id:
                self.resource_list.setCurrentItem(item)
        self.asset_list.blockSignals(False)
        self.resource_list.blockSignals(False)
        self.delete_asset_button.setVisible(self.asset_list.currentItem() is not None and self.asset_list.currentItem().data(Qt.ItemDataRole.UserRole) is not None); self.delete_resource_button.setVisible(self.resource_list.currentItem() is not None)

    def _asset_changed(self, item, previous):
        if item is None:
            return
        with QSignalBlocker(self.resource_list):
            self.resource_list.setCurrentItem(None)
        self.delete_resource_button.hide()
        kind, identifier = item.data(Qt.ItemDataRole.UserRole)
        self.delete_asset_button.show()
        self.asset_selected.emit(kind, identifier)

    def _asset_clicked(self, item):
        if item is not None:
            kind, identifier = item.data(Qt.ItemDataRole.UserRole)
            self.asset_selected.emit(kind, identifier)

    def _resource_changed(self, item, previous):
        if item is None:
            return
        with QSignalBlocker(self.asset_list):
            self.asset_list.setCurrentItem(None)
        self.delete_asset_button.hide();self.delete_resource_button.show()
        self.composition_selected.emit(str(item.data(Qt.ItemDataRole.UserRole)))

    def _resource_clicked(self, item):
        if item is not None:
            self.composition_selected.emit(str(item.data(Qt.ItemDataRole.UserRole)))

    def _delete_asset(self):
        item=self.asset_list.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole):self.asset_delete_requested.emit(*item.data(Qt.ItemDataRole.UserRole))

    def _delete_resource(self):
        item=self.resource_list.currentItem()
        if item:self.composition_delete_requested.emit(str(item.data(Qt.ItemDataRole.UserRole)))

    def retranslate(self, localization):
        t = localization.text
        self.assets_label.setText(t("v2.assets"))
        self.resources_label.setText(t("v2.resources"))
        self.import_button.setText(t("resource.import"))
        self.delete_asset_button.setText(t("v2.delete_asset")); self.delete_resource_button.setText(t("v2.delete_resource"))
