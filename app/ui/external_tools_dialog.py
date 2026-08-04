"""QSettings-backed Aseprite executable configuration."""
from pathlib import Path
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QFileDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QVBoxLayout,QWidget
from app.services.aseprite_locator_service import locate_aseprite,validate_aseprite
class ExternalToolsDialog(QDialog):
    def __init__(self,settings,localization,parent=None):
        super().__init__(parent);self.settings=settings;self.localization=localization;self._validated=None;root=QVBoxLayout(self);form=QFormLayout();row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);self.path=QLineEdit(str(settings.value("external_tools/aseprite_path","")));self.browse=QPushButton();layout.addWidget(self.path,1);layout.addWidget(self.browse);form.addRow("Aseprite",row);root.addLayout(form);actions=QHBoxLayout();self.detect=QPushButton();self.validate=QPushButton();self.clear=QPushButton();[actions.addWidget(w) for w in (self.detect,self.validate,self.clear)];root.addLayout(actions);self.status=QLabel();root.addWidget(self.status);self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel);root.addWidget(self.buttons);self.browse.clicked.connect(self._browse);self.detect.clicked.connect(self._detect);self.validate.clicked.connect(self._validate);self.clear.clicked.connect(lambda:self.path.clear());self.buttons.clicked.connect(self._button);self.path.textChanged.connect(lambda:self.status.setText(""));self.retranslate_ui()
    def retranslate_ui(self):
        t=self.localization.text;self.setWindowTitle(t("external.title"));self.browse.setText(t("external.browse"));self.detect.setText(t("external.detect"));self.validate.setText(t("external.validate"));self.clear.setText(t("external.clear"))
    def _browse(self):
        path,_=QFileDialog.getOpenFileName(self,self.localization.text("external.browse"),"","Aseprite (Aseprite.exe)")
        if path:self.path.setText(path)
    def _detect(self):
        found=locate_aseprite(self.settings)
        if found:self.path.setText(str(found));self._validate()
        else:self.status.setText(self.localization.text("external.not_found"))
    def _validate(self):
        valid,version=validate_aseprite(self.path.text());self._validated=self.path.text() if valid else None;self.status.setText((self.localization.text("external.valid")+f" · {version}") if valid else self.localization.text("external.invalid"));return valid
    def _button(self,button):
        role=self.buttons.buttonRole(button)
        if role==QDialogButtonBox.ButtonRole.RejectRole:self.reject();return
        if not self.path.text().strip():self.settings.remove("external_tools/aseprite_path");self._validated=""
        elif not self._validate():return
        else:self.settings.setValue("external_tools/aseprite_path",self._validated)
        if role==QDialogButtonBox.ButtonRole.AcceptRole:self.accept()
