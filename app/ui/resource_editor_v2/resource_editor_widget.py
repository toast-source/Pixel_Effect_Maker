from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QSizePolicy, QStackedWidget, QSplitter, QTableWidget, QVBoxLayout, QWidget

from app.models.resource_composition import CompositionLayer, ResourceComposition
from app.services.resource_composition_render_service import invalidate_composition_cache
from app.ui.interface_settings_dialog import timeline_frame_width

from .asset_browser_panel import AssetBrowserPanel
from .asset_inspector_widget import AssetFrameStrip, AssetInspectorWidget, AssetPreviewCanvas, asset_durations, asset_frames
from .composition_canvas import CompositionCanvas
from .composition_inspector import CompositionInspector, LayerInspector, PropertySearchDialog
from .composition_timeline import CompositionTimeline
from .new_resource_dialog import NewResourceDialog
from .resource_editor_controller import ResourceEditorController
from .resource_editor_state import ResourceEditorMode
from app.ui.undo_commands import EditorValueCommand


class ResourceStartPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);layout.addStretch();self.label=QLabel();self.label.setAlignment(Qt.AlignmentFlag.AlignCenter);self.import_button=QPushButton();self.blank_button=QPushButton();layout.addWidget(self.label);layout.addWidget(self.import_button);layout.addWidget(self.blank_button);layout.addStretch()
    def setText(self,text):self.label.setText(text)


class ResourceEditorWidget(QWidget):
    SUPPORTED_DROP_SUFFIXES = {".png", ".gif", ".ase", ".aseprite"}
    import_requested=Signal(object);pivot_changed=Signal(str,str,float,float);create_emitter_requested=Signal(str,str);reimport_requested=Signal(str,str);delete_requested=Signal(str,str);resource_selected=Signal(str,str);composition_changed=Signal(str)

    def __init__(self,settings,parent=None):
        super().__init__(parent);self.setAcceptDrops(True);self.settings=settings;self.localization=None;self.undo_stack=None;self._applying_command=False;self.controller=ResourceEditorController(self);self.project=None;self._playing=False;self._last_asset=None;self._gizmo_before={};root=QVBoxLayout(self);self.vertical_splitter=QSplitter(Qt.Orientation.Vertical);self.splitter=QSplitter(Qt.Orientation.Horizontal);self.splitter.setChildrenCollapsible(False);self.splitter.setStretchFactor(0,0);self.splitter.setStretchFactor(1,1);self.splitter.setStretchFactor(2,0)
        self.browser=AssetBrowserPanel();self.center_stack=QStackedWidget();self.empty=ResourceStartPanel();self.asset_canvas=AssetPreviewCanvas();self.asset_strip=AssetFrameStrip();asset_center=QWidget();asset_layout=QVBoxLayout(asset_center);asset_layout.addWidget(self.asset_canvas,1);asset_layout.addWidget(self.asset_strip);self.composition_canvas=CompositionCanvas();self.center_stack.addWidget(self.empty);self.center_stack.addWidget(asset_center);self.center_stack.addWidget(self.composition_canvas)
        self.browser.setMinimumWidth(180);self.browser.setMaximumWidth(320);self.browser.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Expanding);self.center_stack.setMinimumWidth(320);self.inspector_stack=QStackedWidget();self.empty_inspector=QWidget();self.asset_inspector=AssetInspectorWidget();self.composition_inspector=CompositionInspector();self.layer_inspector=LayerInspector();[self.inspector_stack.addWidget(widget) for widget in (self.empty_inspector,self.asset_inspector,self.composition_inspector,self.layer_inspector)];self.inspector_stack.setMinimumWidth(300);self.inspector_stack.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Expanding);[self.splitter.addWidget(widget) for widget in (self.browser,self.center_stack,self.inspector_stack)];self.vertical_splitter.setChildrenCollapsible(False);self.vertical_splitter.setStretchFactor(0,1);self.vertical_splitter.setStretchFactor(1,0);self.vertical_splitter.addWidget(self.splitter)
        self.composition_timeline=CompositionTimeline();self.composition_timeline.set_frame_cell_width(timeline_frame_width(settings));self.composition_timeline.setMinimumHeight(120);self.vertical_splitter.addWidget(self.composition_timeline);root.addWidget(self.vertical_splitter,1);self.timeline=QTableWidget(self);self.timeline.hide();self.splitter.splitterMoved.connect(self._save_horizontal_splitter);self.vertical_splitter.splitterMoved.connect(self._save_vertical_splitter);QTimer.singleShot(0,self._restore_splitters)
        self.timer=QTimer(self);self.timer.timeout.connect(self._advance)
        self.list=self.browser.asset_list;self.comp_list=self.browser.resource_list;self.pivot_x=self.asset_inspector.pivot_x;self.pivot_y=self.asset_inspector.pivot_y;self.canvas=self.composition_canvas
        self.browser.import_requested.connect(lambda:self.import_requested.emit(None));self.browser.asset_selected.connect(self._select_asset);self.browser.composition_selected.connect(lambda identifier:self.controller.select_composition(identifier));self.browser.asset_delete_requested.connect(self.delete_requested);self.browser.composition_delete_requested.connect(self._delete_composition);self.asset_strip.frame_selected.connect(self.set_frame);self.asset_inspector.create_requested.connect(self._create_dialog);self.asset_inspector.reimport_requested.connect(self._reimport);self.asset_inspector.pivot_changed.connect(self._asset_pivot)
        self.empty.import_button.clicked.connect(lambda:self.import_requested.emit(None));self.empty.blank_button.clicked.connect(self._create_blank_dialog)
        self.composition_inspector.changed.connect(self._composition_meta);self.composition_inspector.use_requested.connect(self._use_in_effect);self.layer_inspector.changed.connect(self._layer_meta);self.layer_inspector.mode_changed.connect(self.set_gizmo);self.layer_inspector.add_property_requested.connect(self._property_dialog);self.layer_inspector.full_rotation_requested.connect(self._full_rotation_click);self.layer_inspector.center_pivot_requested.connect(self._center_layer_pivot);self.layer_inspector.use_requested.connect(self._use_in_effect);self.layer_inspector.keyframe_requested.connect(self.set_keyframe);self.layer_inspector.property_value_requested.connect(self._property_value);self.layer_inspector.remove_property_requested.connect(self._remove_property)
        self.composition_timeline.frame_selected.connect(self.set_frame);self.composition_timeline.layer_selected.connect(self.controller.select_layer);self.composition_timeline.visibility_requested.connect(self._toggle_visibility);self.composition_timeline.play_requested.connect(self.toggle_play);self.composition_timeline.previous_requested.connect(self.previous_frame);self.composition_timeline.next_requested.connect(self.next_frame);self.composition_timeline.delete_keyframe_requested.connect(self._delete_keyframe)
        self.composition_timeline.scrub_started.connect(self.stop)
        self.composition_canvas.layer_selected.connect(self.controller.select_layer);self.composition_canvas.transform_changed.connect(self._gizmo_change);self.composition_canvas.transform_cancelled.connect(self._gizmo_cancel);self.composition_canvas.drag_started.connect(self.stop)
        self.controller.state_changed.connect(self._apply_state);self.controller.frame_changed.connect(lambda frame:self._apply_state(self.controller.state));self.controller.composition_changed.connect(self.composition_changed);self.controller.clear()
        for drop_target in (self.browser,self.browser.asset_list,self.browser.asset_list.viewport(),self.browser.resource_list,self.browser.resource_list.viewport(),self.empty,self.center_stack,self.asset_canvas,self.composition_canvas):
            drop_target.setAcceptDrops(True);drop_target.installEventFilter(self)

    @classmethod
    def _drop_paths(cls,event):
        mime=event.mimeData()
        if not mime or not mime.hasUrls():return []
        return [url.toLocalFile() for url in mime.urls() if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in cls.SUPPORTED_DROP_SUFFIXES]

    def _accept_drag(self,event):
        if self._drop_paths(event):event.setDropAction(Qt.DropAction.CopyAction);event.accept()
        else:event.ignore()

    def dragEnterEvent(self,event):self._accept_drag(event)
    def dragMoveEvent(self,event):self._accept_drag(event)
    def dropEvent(self,event):
        paths=self._drop_paths(event)
        if not paths:event.ignore();return
        self.import_requested.emit(paths);event.setDropAction(Qt.DropAction.CopyAction);event.accept()

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.Type.DragEnter,QEvent.Type.DragMove):self._accept_drag(event);return True
        if event.type()==QEvent.Type.Drop:self.dropEvent(event);return True
        return super().eventFilter(watched,event)

    @property
    def resource(self):return self.controller.asset
    @resource.setter
    def resource(self,value):
        if value is None:self.controller.state.asset_id=None
    @property
    def resource_type(self):return self.controller.state.asset_type
    @property
    def composition(self):return self.controller.composition
    @composition.setter
    def composition(self,value):self.controller.state.composition_id=None if value is None else value.id
    @property
    def selected_layer(self):return self.controller.layer
    @selected_layer.setter
    def selected_layer(self,value):self.controller.state.layer_id=None if value is None else value.id
    @property
    def frame_index(self):return self.controller.state.frame
    @frame_index.setter
    def frame_index(self,value):self.controller.state.frame=int(value)

    def refresh(self,project,select=None):
        self.project=project;self.controller.set_project(project)
        if select:self._last_asset=select;self.controller.select_asset(*select)
        asset_selection=(self.controller.state.asset_type,self.controller.state.asset_id) if self.controller.asset else None;self.browser.refresh(project,asset_selection,self.controller.state.composition_id);self._legacy_timeline();self._apply_state(self.controller.state)

    def select_resource(self,kind,identifier):self.controller.select_asset(kind,identifier);self.browser.refresh(self.project,(kind,identifier),None)

    def _select_asset(self,kind,identifier):
        self._last_asset=(kind,identifier);self.controller.select_asset(kind,identifier);self.resource_selected.emit(kind,identifier)

    def _apply_state(self,state):
        mode=state.mode;asset=self.controller.asset;composition=self.controller.composition;layer=self.controller.layer
        timeline_was_visible=self.composition_timeline.isVisible();timeline_visible=mode in {ResourceEditorMode.COMPOSITION,ResourceEditorMode.LAYER_EDIT};self.center_stack.setCurrentIndex(0 if mode==ResourceEditorMode.EMPTY else 1 if mode==ResourceEditorMode.ASSET_INSPECT else 2);self.inspector_stack.setCurrentIndex({ResourceEditorMode.EMPTY:0,ResourceEditorMode.ASSET_INSPECT:1,ResourceEditorMode.COMPOSITION:2,ResourceEditorMode.LAYER_EDIT:3}[mode]);self.composition_timeline.setVisible(timeline_visible)
        if timeline_visible and not timeline_was_visible:QTimer.singleShot(0,self._restore_vertical_splitter)
        if mode==ResourceEditorMode.EMPTY:self.empty.setText(self.localization.text("resource.start_text") if self.localization else "Import an asset or create an empty resource to begin")
        elif mode==ResourceEditorMode.ASSET_INSPECT:
            self.asset_canvas.set_asset(asset,state.frame);self.asset_strip.set_asset(asset,state.frame);self.asset_inspector.set_asset(asset)
        else:
            source=self._layer_source(layer);self.composition_canvas.set_context(self.project,composition,layer,state.frame);self.composition_inspector.set_composition(composition);self.layer_inspector.set_layer(layer,source,state.frame);self.layer_inspector.set_mode(state.gizmo_mode);self.composition_canvas.set_mode(state.gizmo_mode,self.localization.text({"move":"gizmo.move","rotate":"gizmo.rotate","scale":"gizmo.scale","pivot":"composition.pivot"}[state.gizmo_mode]) if self.localization else state.gizmo_mode);self.composition_timeline.refresh(composition,layer,state.frame)
        self._legacy_timeline()

    @staticmethod
    def _settings_sizes(value,count):
        try:return [int(item) for item in value] if isinstance(value,(list,tuple)) and len(value)==count else []
        except (TypeError,ValueError):return []

    def _restore_splitters(self):
        available=max(900,self.width());left=min(240,max(190,round(available*.18)));right=min(380,max(310,round(available*.27)));defaults=[left,max(320,available-left-right),right];saved=self._settings_sizes(self.settings.value("ui/resource_editor_v2_horizontal_splitter",[]),3)
        valid=bool(saved and saved[0]>=180 and saved[1]>=320 and saved[2]>=300 and sum(saved)<=available*1.25);self.splitter.setSizes(saved if valid else defaults);self._restore_vertical_splitter()

    def _restore_vertical_splitter(self):
        available=max(420,self.height());saved=self._settings_sizes(self.settings.value("ui/resource_editor_v2_vertical_splitter",[]),2);defaults=[max(260,available-190),190];valid=bool(saved and saved[0]>=240 and saved[1]>=120 and sum(saved)<=available*1.25);self.vertical_splitter.setSizes(saved if valid else defaults)

    def _save_horizontal_splitter(self,*args):self.settings.setValue("ui/resource_editor_v2_horizontal_splitter",self.splitter.sizes())
    def _save_vertical_splitter(self,*args):
        if self.composition_timeline.isVisible():self.settings.setValue("ui/resource_editor_v2_vertical_splitter",self.vertical_splitter.sizes())

    def _layer_source(self,layer):
        if layer is None:return None
        items=self.project.source_assets if layer.source_type=="source_asset" else self.project.animation_clips;return next((item for item in items if item.id==layer.source_id),None)

    def _legacy_timeline(self):
        count=len(asset_frames(self.resource)) if self.resource else 0;self.timeline.setColumnCount(count);self.timeline.setRowCount(1 if count else 0)

    def _create_dialog(self):
        if self.resource is None:return
        dialog=NewResourceDialog(self.resource,self.localization,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.controller.create_resource(*dialog.values());self.browser.refresh(self.project,None,self.composition.id)

    def _create_blank_dialog(self):
        if self.project is None:return
        dialog=NewResourceDialog(None,self.localization,self,defaults=(self.project.width,self.project.height,self.project.fps,self.project.loop))
        if dialog.exec()==QDialog.DialogCode.Accepted:
            composition=self.controller.create_blank_resource(*dialog.values());self.browser.refresh(self.project,None,composition.id)

    def _reimport(self):
        if self.resource:self.reimport_requested.emit(self.resource_type,self.resource.id)

    def _asset_pivot(self,x,y):
        if self.resource:self._push_value(self.resource.id,"asset_pivot",[self.resource.pivot_x,self.resource.pivot_y],[x,y],"Asset Pivot",512)

    def _composition_meta(self,before,after):
        names={item.name for item in self.project.resource_compositions if item is not self.composition};base=self.composition.name;number=2
        while self.composition.name in names:self.composition.name=f"{base} ({number})";number+=1
        after=dict(after);after["name"]=self.composition.name
        for key,value in before.items():setattr(self.composition,key,value)
        self._push_value(self.composition.id,"composition_meta",before,after,"Composition Properties",510);self.browser.refresh(self.project,None,self.composition.id)

    def _layer_meta(self,before,after):
        for key,value in before.items():setattr(self.selected_layer,key,value)
        self._push_value(self.selected_layer.id,"layer_meta",before,after,"Layer Properties",511)
    def _use_in_effect(self):
        if self.composition:self.create_emitter_requested.emit("resource_composition",self.composition.id)

    def _delete_composition(self,identifier):
        composition=next((item for item in self.project.resource_compositions if item.id==identifier),None)
        if composition is None:return
        if any(emitter.settings.resource_type=="resource_composition" and emitter.settings.resource_id==identifier for emitter in self.project.particle_emitters):QMessageBox.warning(self,self.localization.text("v2.resources"),self.localization.text("composition.in_use"));return
        if not self._confirm(self.localization.text("v2.resources"),self.localization.text("composition.delete_confirm"),"v2.delete"):return
        self.project.resource_compositions.remove(composition);invalidate_composition_cache(identifier);self.controller.clear();self.composition_changed.emit("");self.browser.refresh(self.project)

    def _property_dialog(self):
        if not self.selected_layer:return
        dialog=PropertySearchDialog(self.selected_layer.tracks,self.localization,self)
        if dialog.exec()==QDialog.DialogCode.Accepted and dialog.selected_id:self.add_property_to_layer(dialog.selected_id)

    def _full_rotation_click(self):
        track=self.selected_layer.tracks.get("rotation") if self.selected_layer else None
        if track and track.keyframes and not self._confirm(self.localization.text("v2.full_rotation"),self.localization.text("v2.replace_rotation_confirm"),"v2.replace"):return
        self.add_full_rotation()

    def _center_layer_pivot(self):
        source=self._layer_source(self.selected_layer)
        if source:self._push_value(self.selected_layer.id,"pivot",[self.selected_layer.pivot_x,self.selected_layer.pivot_y],[source.width/2,source.height/2],"Center Layer Pivot")

    def _toggle_visibility(self,layer_id):
        layer=next((item for item in self.composition.layers if item.id==layer_id),None)
        if layer:self._push_value(layer.id,"visible",layer.visible,not layer.visible,"Layer Visibility")

    def _delete_keyframe(self,property_id):
        if self.selected_layer is None:return
        properties=[property_id] if property_id in self.selected_layer.tracks else list(self.selected_layer.tracks)
        for prop in properties:
            before=deepcopy(self.selected_layer.tracks.get(prop));after=deepcopy(before);after.delete_keyframe(self.frame_index)
            self._push_value(self.selected_layer.id,"track:"+prop,before,after,"Delete Keyframe")

    def _remove_property(self,property_id):
        if self._confirm(self.localization.text("composition.properties"),self.localization.text("composition.remove_property_confirm"),"v2.delete"):self.selected_layer.remove_property(property_id);self.controller.changed()

    def _property_value(self,property_id,value):
        track=self.selected_layer.tracks[property_id];before=deepcopy(track);after=deepcopy(track);existing=next((item for item in after.keyframes if item.frame==self.frame_index),None)
        if existing:existing.value=value
        else:after.default_value=value
        self._push_value(self.selected_layer.id,"track:"+property_id,before,after,"Change "+property_id.title(),100+list(("position","rotation","scale","opacity")).index(property_id))

    def _confirm(self,title,message,accept_key):
        box=QMessageBox(QMessageBox.Icon.Question,title,message,parent=self);accept=box.addButton(self.localization.text(accept_key),QMessageBox.ButtonRole.AcceptRole);box.addButton(self.localization.text("v2.cancel"),QMessageBox.ButtonRole.RejectRole);box.exec();return box.clickedButton() is accept

    def set_gizmo(self,mode):
        self.controller.set_gizmo(mode);self.layer_inspector.set_mode(mode);self.composition_canvas.set_mode(mode,self.localization.text({"move":"gizmo.move","rotate":"gizmo.rotate","scale":"gizmo.scale","pivot":"composition.pivot"}[mode]) if self.localization else mode)

    def _gizmo_change(self,property_id,value,final):
        layer=self.selected_layer
        if layer is None:return
        if property_id not in self._gizmo_before:self._gizmo_before[property_id]=deepcopy([layer.pivot_x,layer.pivot_y] if property_id=="pivot" else layer.tracks.get(property_id))
        if property_id=="pivot":layer.pivot_x,layer.pivot_y=value
        else:layer.add_property(property_id).set_keyframe(self.frame_index,value)
        self.composition.touch();invalidate_composition_cache(self.composition.id);self._apply_state(self.controller.state)
        if final:
            before=self._gizmo_before.pop(property_id,None);after=deepcopy([layer.pivot_x,layer.pivot_y] if property_id=="pivot" else layer.tracks.get(property_id))
            if before!=after:self.apply_undo_value(layer.id,"pivot" if property_id=="pivot" else "track:"+property_id,before);self._push_value(layer.id,"pivot" if property_id=="pivot" else "track:"+property_id,before,after,"Gizmo "+property_id.title())
            self.composition_changed.emit(self.composition.id)

    def _gizmo_cancel(self,property_id,value):
        before=self._gizmo_before.pop(property_id,None);layer=self.selected_layer
        if property_id=="pivot":layer.pivot_x,layer.pivot_y=before or value
        elif before is None:layer.tracks.pop(property_id,None)
        else:layer.tracks[property_id]=before
        self.composition.touch();invalidate_composition_cache(self.composition.id);self._apply_state(self.controller.state)

    def set_frame(self,index):self.stop();self.controller.set_frame(index)
    def previous_frame(self):self.set_frame(self.frame_index-1)
    def next_frame(self):self.set_frame(self.frame_index+1)
    def toggle_play(self):
        if self._playing:self.stop();return
        count=self.composition.frame_count if self.composition else len(asset_frames(self.resource)) if self.resource else 0
        if count<2:return
        interval=max(1,round(1000/self.composition.fps)) if self.composition else asset_durations(self.resource)[self.frame_index];self._playing=True;self.composition_timeline.set_playing(True);self.timer.start(interval)
    def stop(self):self._playing=False;self.timer.stop();self.composition_timeline.set_playing(False)
    def _advance(self):
        if not self._playing:return
        if self.composition:
            if self.frame_index>=self.composition.frame_count-1:
                if not self.composition.loop:self.stop();return
                self.controller.set_frame(0)
            else:self.controller.set_frame(self.frame_index+1)
        else:
            frames=asset_frames(self.resource);self.controller.set_frame((self.frame_index+1)%len(frames));self.timer.setInterval(asset_durations(self.resource)[self.frame_index])

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.toggle_play();event.accept();return
        if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Comma):self.previous_frame();event.accept();return
        if event.key() in (Qt.Key.Key_Right,Qt.Key.Key_Period):self.next_frame();event.accept();return
        super().keyPressEvent(event)

    def retranslate_ui(self,localization):
        self.localization=localization;self.browser.retranslate(localization);self.asset_inspector.retranslate(localization);self.composition_inspector.retranslate(localization);self.layer_inspector.retranslate(localization);self.composition_timeline.retranslate(localization);self.empty.setText(localization.text("resource.start_text"));self.empty.import_button.setText(localization.text("resource.start_import"));self.empty.blank_button.setText(localization.text("resource.start_blank"));self.set_gizmo(self.composition_canvas.mode)
    def set_undo_stack(self,stack):self.undo_stack=stack
    def set_timeline_frame_width(self,width):self.composition_timeline.set_frame_cell_width(width)
    def _push_value(self,target_id,field,before,after,text,merge_id=-1):
        if before==after:return
        if self.undo_stack is None:self.apply_undo_value(target_id,field,after)
        else:self.undo_stack.push(EditorValueCommand(self,target_id,field,before,after,text,merge_id))
    def apply_undo_value(self,target_id,field,value):
        if self.project is None:return
        self._applying_command=True
        try:self._apply_undo_value(target_id,field,value)
        finally:self._applying_command=False
    def _apply_undo_value(self,target_id,field,value):
        if field=="asset_pivot":
            asset=next((item for item in self.project.source_assets+self.project.animation_clips if item.id==target_id),None)
            if asset:asset.pivot_x,asset.pivot_y=value;self._apply_state(self.controller.state);self.pivot_changed.emit(self.resource_type,target_id,*value)
            return
        if field=="composition_meta":
            composition=next((item for item in self.project.resource_compositions if item.id==target_id),None)
            if composition:
                for key,part in value.items():setattr(composition,key,part)
                composition.touch();invalidate_composition_cache(composition.id);self.controller.changed();self.browser.refresh(self.project,None,composition.id)
            return
        layer=next((layer for composition in self.project.resource_compositions for layer in composition.layers if layer.id==target_id),None)
        if layer is None:return
        if field.startswith("track:"):
            prop=field.split(":",1)[1]
            if value is None:layer.tracks.pop(prop,None)
            else:layer.tracks[prop]=value
        elif field=="pivot":layer.pivot_x,layer.pivot_y=value
        elif field=="layer_meta":
            for key,part in value.items():setattr(layer,key,part)
        else:setattr(layer,field,value)
        composition=next((item for item in self.project.resource_compositions if layer in item.layers),None)
        if composition:composition.touch();invalidate_composition_cache(composition.id);self.controller.changed()
    def _center(self):self.asset_inspector._center()
    def create_composition(self,name="Composition",width=64,height=64,fps=12,frame_count=12,loop=True):
        existing={item.name for item in self.project.resource_compositions};base=name;number=2
        while name in existing:name=f"{base} ({number})";number+=1
        composition=ResourceComposition(name,width,height,fps,frame_count,loop);self.project.resource_compositions.append(composition);self.controller.select_composition(composition.id);self.composition_changed.emit(composition.id);self.browser.refresh(self.project,None,composition.id);return composition
    def add_selected_asset(self):
        if not self.composition or not self._last_asset:return None
        kind,identifier=self._last_asset;items=self.project.source_assets if kind=="source_asset" else self.project.animation_clips;asset=next((item for item in items if item.id==identifier),None)
        if asset is None:return None
        layer=CompositionLayer(asset.name,kind,asset.id,0,self.composition.frame_count-1,pivot_x=asset.pivot_x,pivot_y=asset.pivot_y);self.composition.layers.append(layer);self.controller.select_layer(layer.id);self.controller.changed();return layer
    def add_property_to_layer(self,property_id):track=self.selected_layer.add_property(property_id);self.controller.changed();return track
    def set_keyframe(self,property_id,value,easing="Linear"):
        before=deepcopy(self.selected_layer.tracks.get(property_id));after=deepcopy(before) if before else self.selected_layer.add_property(property_id);after=deepcopy(after);after.set_keyframe(self.frame_index,value,easing)
        if before is None:self.selected_layer.tracks.pop(property_id,None)
        self._push_value(self.selected_layer.id,"track:"+property_id,before,after,"Add Keyframe")
    def add_full_rotation(self,clockwise=True,turns=1):
        before=deepcopy(self.selected_layer.tracks.get("rotation"));track=deepcopy(before) if before else self.selected_layer.add_property("rotation");track=deepcopy(track);track.keyframes.clear();track.set_keyframe(0,0,"Linear");track.set_keyframe(self.composition.frame_count-1,(360 if clockwise else -360)*turns,"Linear")
        if before is None:self.selected_layer.tracks.pop("rotation",None)
        self._push_value(self.selected_layer.id,"track:rotation",before,track,"Full Rotation")
