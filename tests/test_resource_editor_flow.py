from __future__ import annotations
import os
import numpy as np
from PIL import Image
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtCore import QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow
from app.ui.resource_editor_widget import resource_durations
APPLICATION=QApplication.instance() or QApplication([])
def service(tmp_path):
    settings=QSettings(str(tmp_path/"settings.ini"),QSettings.Format.IniFormat);settings.setValue("ui/language","en");return ShortcutSettingsService(settings)
def make_resources(tmp_path):
    png=tmp_path/"spark.PNG";Image.new("RGBA",(5,3),(255,0,0,128)).save(png)
    gif=tmp_path/"smoke.GIF";frames=[Image.new("RGBA",(4,4),(255,0,0,255)),Image.new("RGBA",(4,4),(0,255,0,128))];frames[0].save(gif,save_all=True,append_images=frames[1:],duration=[40,130],loop=0);return png,gif
def test_workspace_import_preview_timeline_pivot_and_particle(tmp_path):
    window=MainWindow(service(tmp_path));png,gif=make_resources(tmp_path);resources=window.import_resources([png,gif]);assert len(resources)==2
    window.show();APPLICATION.processEvents()
    assert window.workspace_stack.currentIndex()==1 and window.resource_editor.list.count()==2
    window.resource_editor.select_resource("animation_clip",resources[1].id);assert window.resource_editor.timeline.columnCount()==2;assert resource_durations(resources[1])==[40,130]
    old_frames=len(window.project.frames);window.resource_editor.set_frame(1);assert window.resource_editor.frame_index==1 and len(window.project.frames)==old_frames
    window.dirty=False;window.resource_editor.pivot_x.setValue(1);assert resources[1].pivot_x==1 and window.dirty
    window.resource_editor._center();assert resources[1].pivot_x==2 and resources[1].pivot_y==2
    emitter=window.create_particle_from_resource("animation_clip",resources[1].id);assert emitter.settings.resource_id==resources[1].id and window.workspace_stack.currentIndex()==0
def test_static_resource_picker_and_duration_playback(tmp_path):
    window=MainWindow(service(tmp_path));png,gif=make_resources(tmp_path);source,clip=window.import_resources([png,gif]);emitter=window.create_particle_from_resource("source_asset",source.id)
    assert emitter.settings.resource_type=="source_asset";window.select_particle_emitter(emitter.id);assert tuple(window.particle_properties.clip.currentData())==("source_asset",source.id)
    editor=window.resource_editor;editor.refresh(window.project,("animation_clip",clip.id));editor.toggle_play();assert editor.timer.interval()==40;editor._advance();assert editor.frame_index==1 and editor.timer.interval()==130
def test_resource_delete_reference_protection_and_reimport_identity(tmp_path,monkeypatch):
    monkeypatch.setattr(QMessageBox,"warning",lambda *a,**k:QMessageBox.StandardButton.Ok)
    window=MainWindow(service(tmp_path));png,_=make_resources(tmp_path);source=window.import_resources([png])[0];old_id=source.id;window.create_particle_from_resource("source_asset",source.id);assert window.delete_resource("source_asset",source.id) is False
    window.project.particle_emitters.clear();monkeypatch.setattr(QMessageBox,"question",lambda *a,**k:QMessageBox.StandardButton.Yes);assert window.reimport_resource("source_asset",source.id);assert window.project.source_assets[0].id==old_id;assert window.delete_resource("source_asset",source.id)
def test_resource_editor_shortcuts_are_separate(tmp_path):
    window=MainWindow(service(tmp_path));_,gif=make_resources(tmp_path);clip=window.import_resources([gif])[0];editor=window.resource_editor;editor.select_resource("animation_clip",clip.id);window.show();window.activateWindow();editor.setFocus();APPLICATION.processEvents();QTest.keyClick(editor,Qt.Key.Key_Right);assert editor.frame_index==1;QTest.keyClick(editor,Qt.Key.Key_Left);assert editor.frame_index==0;QTest.keyClick(editor,Qt.Key.Key_Return);assert editor._playing
def test_workspace_labels_translate_without_resource_name_change(tmp_path):
    window=MainWindow(service(tmp_path));png,_=make_resources(tmp_path);resource=window.import_resources([png])[0];name=resource.name;window.localization.set_language("ko");assert window.resource_workspace_button.text()=="리소스 에디터" and resource.name==name
