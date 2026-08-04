from __future__ import annotations

import os

import numpy as np
from PIL import Image
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from app.services.resource_composition_render_service import render_composition_frame
from app.models.project import Project
from app.models.resource_composition import CompositionLayer,ResourceComposition
from app.models.source_asset import SourceAsset
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow
from app.ui.resource_editor_v2.new_resource_dialog import NewResourceDialog
from app.ui.resource_editor_v2.composition_canvas import CompositionCanvas,alpha_bounds
from app.ui.resource_editor_v2.resource_editor_state import ResourceEditorMode


APPLICATION = QApplication.instance() or QApplication([])


def service(tmp_path, language="en"):
    settings=QSettings(str(tmp_path/"settings.ini"),QSettings.Format.IniFormat);settings.setValue("ui/language",language);return ShortcutSettingsService(settings)


def png(tmp_path):
    path=tmp_path/"spinner.png";pixels=np.zeros((3,5,4),dtype=np.uint8);pixels[0,0]=[255,0,0,255];pixels[1,1:5]=[0,180,255,255];Image.fromarray(pixels,"RGBA").save(path);return path


def click_asset(editor):
    item=next(editor.browser.asset_list.item(row) for row in range(editor.browser.asset_list.count()) if editor.browser.asset_list.item(row).data(Qt.ItemDataRole.UserRole))
    QTest.mouseClick(editor.browser.asset_list.viewport(),Qt.MouseButton.LeftButton,pos=editor.browser.asset_list.visualItemRect(item).center())


def click_create_resource(editor, captured=None):
    def accept_dialog():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,NewResourceDialog)
        if captured is not None:captured.update(name=dialog.name.text(),width=dialog.width.value(),height=dialog.height.value(),fps=dialog.fps.value(),duration=dialog.duration.value(),frames=dialog.frames.value(),create=dialog.create.text(),cancel=dialog.cancel.text())
        QTest.mouseClick(dialog.create,Qt.MouseButton.LeftButton)
    QTimer.singleShot(0,accept_dialog);QTest.mouseClick(editor.asset_inspector.create_button,Qt.MouseButton.LeftButton)


def test_click_flow_asset_to_rotating_particle_preview(tmp_path,monkeypatch):
    path=png(tmp_path);monkeypatch.setattr(QFileDialog,"getOpenFileNames",lambda *args,**kwargs:([str(path)],""));window=MainWindow(service(tmp_path));window.set_workspace("resource");window.show();APPLICATION.processEvents();editor=window.resource_editor;QTest.mouseClick(editor.browser.import_button,Qt.MouseButton.LeftButton);APPLICATION.processEvents()
    click_asset(editor);APPLICATION.processEvents()
    assert editor.controller.state.mode==ResourceEditorMode.ASSET_INSPECT
    assert editor.asset_inspector.isVisibleTo(window) and not editor.composition_timeline.isVisibleTo(window)
    assert not editor.layer_inspector.isVisibleTo(window) and not editor.composition_inspector.use.isVisibleTo(window)
    captured={};click_create_resource(editor,captured);APPLICATION.processEvents()
    assert captured=={"name":"spinner","width":5,"height":3,"fps":12,"duration":1.0,"frames":12,"create":"Create","cancel":"Cancel"}
    assert editor.controller.state.mode==ResourceEditorMode.LAYER_EDIT and len(window.project.resource_compositions)==1
    composition=window.project.resource_compositions[0];layer=composition.layers[0];assert layer.source_id==window.project.source_assets[0].id
    assert editor.composition_timeline.isVisibleTo(window) and editor.layer_inspector.isVisibleTo(window)
    QTest.mouseClick(editor.layer_inspector.full_rotation,Qt.MouseButton.LeftButton);assert [key.value for key in layer.tracks["rotation"].keyframes]==[0.0,360.0]
    first=render_composition_frame(window.project,composition,0);middle=render_composition_frame(window.project,composition,3);assert not np.array_equal(first,middle)
    editor.setFocus();QTest.keyClick(editor,Qt.Key.Key_Return);assert editor._playing and editor.timer.interval()==83;editor.stop()
    assert editor.layer_inspector.use.isVisibleTo(window);QTest.mouseClick(editor.layer_inspector.use,Qt.MouseButton.LeftButton);assert window.workspace_stack.currentIndex()==0
    emitter=window.project.particle_emitters[-1];assert emitter.settings.resource_type=="resource_composition" and emitter.settings.resource_id==composition.id
    for _ in range(50):
        QTest.qWait(20);APPLICATION.processEvents()
        if emitter.id in window.particle_preview_manager.sessions:break
    session=window.particle_preview_manager.sessions.get(emitter.id);assert session is not None and len(session.frames)==emitter.settings.output_frame_count;assert any(not np.array_equal(session.frames[0],frame) for frame in session.frames[1:])
    window.dirty=False;window.close()


def test_modes_hide_unrelated_controls_and_korean_dialog(tmp_path):
    window=MainWindow(service(tmp_path,"ko"));window.show();window.set_workspace("resource");editor=window.resource_editor;APPLICATION.processEvents()
    assert editor.controller.state.mode==ResourceEditorMode.EMPTY and not editor.composition_timeline.isVisibleTo(window)
    window.import_resources([png(tmp_path)]);click_asset(editor);captured={};click_create_resource(editor,captured)
    assert captured["create"]=="만들기" and captured["cancel"]=="취소" and captured["width"]==5 and captured["height"]==3
    editor.controller.select_layer(None);APPLICATION.processEvents();assert editor.controller.state.mode==ResourceEditorMode.COMPOSITION
    assert editor.composition_inspector.isVisibleTo(window) and not editor.layer_inspector.isVisibleTo(window) and editor.composition_timeline.isVisibleTo(window)
    window.dirty=False;window.close()


def test_real_rotate_move_scale_pivot_handles_and_escape(tmp_path):
    window=MainWindow(service(tmp_path));window.import_resources([png(tmp_path)]);window.set_workspace("resource");window.show();editor=window.resource_editor;click_asset(editor);click_create_resource(editor);APPLICATION.processEvents();canvas=editor.composition_canvas;layer=editor.selected_layer
    QTest.mouseClick(editor.layer_inspector.mode_buttons["rotate"],Qt.MouseButton.LeftButton);QTest.mouseClick(canvas,Qt.MouseButton.LeftButton,pos=QPoint(10,10));assert "rotation" not in layer.tracks and editor.selected_layer is None
    table=editor.composition_timeline.table;item=table.item(0,0);QTest.mouseClick(table.viewport(),Qt.MouseButton.LeftButton,pos=table.visualItemRect(item).center());APPLICATION.processEvents();assert editor.selected_layer is layer
    QTest.mouseClick(canvas,Qt.MouseButton.LeftButton,pos=QPoint(10,10));center=QPoint(canvas.width()//2,canvas.height()//2);QTest.mouseClick(canvas,Qt.MouseButton.LeftButton,pos=center);APPLICATION.processEvents();assert editor.selected_layer is layer
    assert canvas.mode=="rotate";rotate_handle=canvas.rotate_handle_position().toPoint();QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=rotate_handle);QTest.mouseMove(canvas,QPoint(center.x()+45,center.y()));QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=QPoint(center.x()+45,center.y()));assert "rotation" in layer.tracks and abs(layer.value("rotation",0))>20
    layer.tracks.pop("rotation");QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=rotate_handle);QTest.mouseMove(canvas,QPoint(center.x()+45,center.y()));QTest.keyClick(canvas,Qt.Key.Key_Escape);assert "rotation" not in layer.tracks
    QTest.mouseClick(editor.layer_inspector.mode_buttons["move"],Qt.MouseButton.LeftButton);QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=center);QTest.mouseMove(canvas,center+QPoint(16,0));QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=center+QPoint(16,0));assert layer.value("position",0)[0]>0
    QTest.mouseClick(editor.layer_inspector.mode_buttons["scale"],Qt.MouseButton.LeftButton);corner=QPoint(center.x()-20+16,center.y()-12);QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=corner);QTest.mouseMove(canvas,corner+QPoint(-12,-8));QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=corner+QPoint(-12,-8));assert layer.value("scale",0)[0]!=1
    old=(layer.pivot_x,layer.pivot_y);QTest.mouseClick(editor.layer_inspector.mode_buttons["pivot"],Qt.MouseButton.LeftButton);pivot=center+QPoint(16,0);QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=pivot);QTest.mouseMove(canvas,pivot+QPoint(8,0));QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=pivot+QPoint(8,0));assert layer.pivot_x!=old[0]
    window.dirty=False;window.close()


def test_asset_list_contains_only_real_assets_after_refresh_language_and_delete(tmp_path):
    window=MainWindow(service(tmp_path));editor=window.resource_editor;assert editor.browser.asset_list.count()==0
    first=png(tmp_path);second=tmp_path/"animated.gif";frames=[Image.new("RGBA",(2,2),(255,0,0,255)),Image.new("RGBA",(2,2),(0,0,255,255))];frames[0].save(second,save_all=True,append_images=frames[1:],duration=[50,150],loop=0)
    window.import_resources([first]);assert editor.browser.asset_list.count()==1
    window.import_resources([second]);assert editor.browser.asset_list.count()==2
    for _ in range(3):editor.refresh(window.project)
    for row in range(editor.browser.asset_list.count()):
        item=editor.browser.asset_list.item(row);assert item.text().strip();assert item.data(Qt.ItemDataRole.UserRole) is not None;assert item.flags()!=Qt.ItemFlag.NoItemFlags
    window.localization.set_language("ko");assert editor.browser.asset_list.count()==2
    window.localization.set_language("en");assert editor.browser.asset_list.count()==2
    window.project.source_assets.clear();editor.refresh(window.project);assert editor.browser.asset_list.count()==1
    window.dirty=False;window.close()


@pytest.mark.parametrize("language",["ko","en"])
@pytest.mark.parametrize("size",[(1024,720),(1280,800),(1600,900)])
def test_layer_inspector_cards_fit_viewport_without_horizontal_scroll(tmp_path,language,size):
    window=MainWindow(service(tmp_path,language));window.resize(*size);window.import_resources([png(tmp_path)]);window.set_workspace("resource");window.show();editor=window.resource_editor;click_asset(editor);APPLICATION.processEvents();assert not editor.composition_timeline.isVisibleTo(window) and editor.vertical_splitter.sizes()[1]==0;click_create_resource(editor);layer=editor.selected_layer
    for property_id in ("position","rotation","scale","opacity"):layer.add_property(property_id)
    editor.controller.changed();APPLICATION.processEvents();inspector=editor.layer_inspector;viewport=inspector.viewport()
    assert inspector.horizontalScrollBar().maximum()==0;assert inspector.widget().width()<=viewport.width()
    assert len(inspector.property_cards)==4
    for controls in inspector.property_cards.values():
        for widget in (controls["card"],*controls["editors"],controls["easing"],controls["keyframe"],controls["remove"]):
            point=widget.mapTo(viewport,QPoint(0,0));assert point.x()>=0;assert point.x()+widget.width()<=viewport.width()+1
    use_point=inspector.use.mapTo(viewport,QPoint(0,0));assert use_point.x()>=0 and use_point.x()+inspector.use.width()<=viewport.width()+1
    panes=editor.splitter.sizes();assert panes[0]>=180 and panes[1]>=320 and panes[2]>=300
    vertical=editor.vertical_splitter.sizes();assert vertical[1]>=120 and vertical[1]<sum(vertical)/2
    window.dirty=False;window.close()


def test_alpha_bounds_drive_selection_polygon_without_changing_pivot_or_pixels():
    pixels=np.zeros((20,20,4),dtype=np.uint8);pixels[8:10,9:12]=[255,100,20,255];before=pixels.copy();asset=SourceAsset("padded",pixels);project=Project.create_default(width=20,height=20);project.source_assets.append(asset);composition=ResourceComposition("A",20,20,12,12,True);layer=CompositionLayer("padded","source_asset",asset.id,0,11,pivot_x=asset.pivot_x,pivot_y=asset.pivot_y);composition.layers.append(layer);project.resource_compositions.append(composition);canvas=CompositionCanvas();canvas.set_context(project,composition,layer,0)
    assert alpha_bounds(pixels)==(9,8,12,10);polygon=canvas.selection_polygon_comp(layer);assert max(point.x() for point in polygon)-min(point.x() for point in polygon)==3;assert max(point.y() for point in polygon)-min(point.y() for point in polygon)==2
    original_pivot=(layer.pivot_x,layer.pivot_y);layer.add_property("scale").set_keyframe(0,[2,2]);layer.add_property("rotation").set_keyframe(0,90);rotated=canvas.selection_polygon_comp(layer);assert round(max(point.x() for point in rotated)-min(point.x() for point in rotated))==4;assert round(max(point.y() for point in rotated)-min(point.y() for point in rotated))==6;assert (layer.pivot_x,layer.pivot_y)==original_pivot and np.array_equal(asset.pixels,before)
    transparent=SourceAsset("empty",np.zeros((4,6,4),dtype=np.uint8));project.source_assets.append(transparent);empty_layer=CompositionLayer("empty","source_asset",transparent.id,0,11,pivot_x=3,pivot_y=2);composition.layers=[empty_layer];fallback=canvas.selection_polygon_comp(empty_layer);assert max(point.x() for point in fallback)-min(point.x() for point in fallback)==6
