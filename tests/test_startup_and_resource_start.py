from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.models.project import Project
from app.services.project_io import ProjectIOError
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow
from app.ui.resource_editor_v2.new_resource_dialog import NewResourceDialog
from app.ui.resource_editor_v2.resource_editor_state import ResourceEditorMode
from app.ui.startup_dialog import StartupDialog


APPLICATION = QApplication.instance() or QApplication([])


def service(tmp_path, language="en"):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", language)
    return ShortcutSettingsService(settings)


def test_startup_dialog_defaults_and_runtime_localization(tmp_path):
    window = MainWindow(service(tmp_path, "en"))
    dialog = StartupDialog(window, window.localization)
    assert dialog.settings().frame_count == 1
    assert dialog.windowTitle() == "Pixel Effect Maker — New Project"
    assert dialog.create_button.text() == "Create Project"
    assert dialog.open_button.text() == "Open Project…"
    window.localization.set_language("ko")
    assert dialog.windowTitle() == "Pixel Effect Maker — 새 프로젝트"
    assert dialog.create_button.text() == "새 프로젝트 시작"
    assert dialog.open_button.text() == "프로젝트 열기…"
    dialog.close()
    window.dirty = False
    window.close()


def test_startup_open_failure_keeps_dialog_open(tmp_path, monkeypatch):
    window = MainWindow(service(tmp_path))
    dialog = StartupDialog(window, window.localization)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("broken.peffect.json", ""))
    monkeypatch.setattr("app.ui.startup_dialog.load_project", lambda path: (_ for _ in ()).throw(ProjectIOError("broken")))
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: shown.append(args[2]))
    dialog.show()
    QTest.mouseClick(dialog.open_button, Qt.MouseButton.LeftButton)
    assert dialog.isVisible()
    assert dialog.opened_project is None
    assert shown == ["broken"]
    dialog.close()
    window.dirty = False
    window.close()


def test_startup_open_accepts_loaded_project(tmp_path, monkeypatch):
    path = tmp_path / "opened.peffect.json"
    project = Project.create_default("Opened")
    window = MainWindow(service(tmp_path))
    dialog = StartupDialog(window, window.localization)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(path), ""))
    monkeypatch.setattr("app.ui.startup_dialog.load_project", lambda value: project)
    dialog.show()
    QTest.mouseClick(dialog.open_button, Qt.MouseButton.LeftButton)
    assert dialog.opened_project is project
    assert dialog.opened_path == path
    assert dialog.result() == dialog.DialogCode.Accepted
    window.dirty = False
    window.close()


def test_resource_empty_start_buttons_import_or_create_blank(tmp_path, monkeypatch):
    window = MainWindow(service(tmp_path))
    window.set_workspace("resource")
    window.show()
    editor = window.resource_editor
    APPLICATION.processEvents()
    assert editor.controller.state.mode == ResourceEditorMode.EMPTY
    assert editor.empty.import_button.text() == "Import Asset"
    assert editor.empty.blank_button.text() == "Create Empty Resource"

    imports = []
    editor.import_requested.connect(imports.append)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args, **kwargs: ([], ""))
    QTest.mouseClick(editor.empty.import_button, Qt.MouseButton.LeftButton)
    assert imports == [None]

    def accept_blank_dialog():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, NewResourceDialog)
        dialog.name.setText("Blank Spark")
        dialog.width.setValue(48)
        dialog.height.setValue(32)
        dialog.fps.setValue(24)
        dialog.frames.setValue(18)
        QTest.mouseClick(dialog.create, Qt.MouseButton.LeftButton)

    QTimer.singleShot(0, accept_blank_dialog)
    QTest.mouseClick(editor.empty.blank_button, Qt.MouseButton.LeftButton)
    APPLICATION.processEvents()
    assert len(window.project.resource_compositions) == 1
    composition = window.project.resource_compositions[0]
    assert (composition.name, composition.width, composition.height) == ("Blank Spark", 48, 32)
    assert (composition.fps, composition.frame_count) == (24, 18)
    assert composition.layers == []
    assert editor.controller.state.mode == ResourceEditorMode.COMPOSITION
    window.dirty = False
    window.close()
