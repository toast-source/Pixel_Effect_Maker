"""Composition-first Resource Editor with retained Imported Asset inspection."""
from __future__ import annotations
from copy import deepcopy
import math
from pathlib import Path
import numpy as np
from PySide6.QtCore import QPointF,QRectF,Qt,QTimer,Signal
from PySide6.QtGui import QColor,QImage,QPainter,QPen,QPixmap
from PySide6.QtWidgets import (QAbstractItemView,QCheckBox,QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QMessageBox,QPushButton,QScrollArea,QSpinBox,QSplitter,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget)
from app.models.animation_clip import AnimationClipAsset
from app.models.project import Project
from app.models.property_registry import search_properties
from app.models.resource_composition import ResourceComposition,CompositionLayer,PROPERTY_DEFAULTS
from app.models.source_asset import SourceAsset
from app.services.resource_composition_render_service import render_composition_frame,invalidate_composition_cache
from .focus_wheel_widgets import FocusWheelDoubleSpinBox,FocusWheelSpinBox

SUPPORTED_RESOURCE_SUFFIXES={".png",".gif",".ase",".aseprite"}
def resource_frames(resource):return [resource.pixels] if isinstance(resource,SourceAsset) else resource.frames
def resource_durations(resource):
    if isinstance(resource,SourceAsset):return [100]
    fallback=max(1,round(1000/max(1,resource.fps)));values=resource.frame_durations_ms or [fallback]*len(resource.frames)
    return [max(1,int(v or fallback)) for v in values] if len(values)==len(resource.frames) else [fallback]*len(resource.frames)

class NewCompositionDialog(QDialog):
    def __init__(self,names,localization,parent=None):
        super().__init__(parent);self.localization=localization;root=QVBoxLayout(self);form=QFormLayout();self.name=QLineEdit(self._name(names));self.width=FocusWheelSpinBox();self.height=FocusWheelSpinBox();self.fps=FocusWheelSpinBox();self.frames=FocusWheelSpinBox();self.duration=FocusWheelDoubleSpinBox();self.loop=QCheckBox();self.width.setRange(1,1024);self.height.setRange(1,1024);self.fps.setRange(1,120);self.frames.setRange(1,512);self.duration.setRange(.01,60);self.duration.setDecimals(2);self.width.setValue(64);self.height.setValue(64);self.fps.setValue(12);self.frames.setValue(12);self.duration.setValue(1);self.loop.setChecked(True)
        t=localization.text;form.addRow(t("composition.name"),self.name);form.addRow(t("composition.width"),self.width);form.addRow(t("composition.height"),self.height);form.addRow(t("composition.fps"),self.fps);form.addRow(t("composition.duration"),self.duration);form.addRow(t("composition.frames"),self.frames);form.addRow(t("composition.loop"),self.loop);root.addLayout(form);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);root.addWidget(buttons);self.setWindowTitle(t("composition.new"));self._sync=False;self.duration.valueChanged.connect(self._duration_changed);self.frames.valueChanged.connect(self._frames_changed);self.fps.valueChanged.connect(self._duration_changed)
    @staticmethod
    def _name(names):
        number=1
        while f"Composition {number}" in names:number+=1
        return f"Composition {number}"
    def _duration_changed(self,*a):
        if self._sync:return
        self._sync=True;self.frames.setValue(max(1,round(self.duration.value()*self.fps.value())));self._sync=False
    def _frames_changed(self,*a):
        if self._sync:return
        self._sync=True;self.duration.setValue(self.frames.value()/self.fps.value());self._sync=False
    def composition(self):return ResourceComposition(self.name.text().strip() or "Composition",self.width.value(),self.height.value(),self.fps.value(),self.frames.value(),self.loop.isChecked())

class AddPropertyDialog(QDialog):
    def __init__(self,enabled,localization,parent=None):
        super().__init__(parent);self.enabled=set(enabled);self.localization=localization;self.selected_id=None;root=QVBoxLayout(self);self.search=QLineEdit();self.results=QListWidget();self.add=QPushButton();root.addWidget(self.search);root.addWidget(self.results);root.addWidget(self.add);self.search.textChanged.connect(self.refresh);self.results.itemDoubleClicked.connect(lambda i:self._accept());self.add.clicked.connect(self._accept);self.setWindowTitle(localization.text("composition.add_property"));self.search.setPlaceholderText(localization.text("composition.search"));self.add.setText(localization.text("composition.add"));self.refresh()
    def refresh(self,*a):
        self.results.clear();language=self.localization.language
        for definition,added in search_properties(self.search.text(),"composition_layer",self.enabled):
            name=definition.name_ko if language=="ko" else definition.name_en;description=definition.description_ko if language=="ko" else definition.description_en;category=self.localization.text("composition.category."+definition.category.casefold());item=QListWidgetItem(f"{name}{' ✓' if added else ''}\n{category} · {description}");item.setData(Qt.ItemDataRole.UserRole,definition.id);item.setFlags(item.flags() if not added else item.flags()&~Qt.ItemFlag.ItemIsEnabled);self.results.addItem(item)
    def _accept(self):
        item=self.results.currentItem()
        if item and item.flags()&Qt.ItemFlag.ItemIsEnabled:self.selected_id=str(item.data(Qt.ItemDataRole.UserRole));self.accept()

class CompositionCanvas(QWidget):
    transform_changed=Signal(str,object,bool);cancelled=Signal(str,object)
    def __init__(self,parent=None):
        super().__init__(parent);self.composition=None;self.layer=None;self.pixels=None;self.frame=0;self.mode="rotate";self.zoom=8;self.pan=QPointF();self._panning=False;self._drag=False;self._start_point=QPointF();self._start_value=None;self.setMinimumSize(320,280);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def set_state(self,composition,layer,pixels,frame):self.composition=composition;self.layer=layer;self.pixels=pixels;self.frame=frame;self.zoom=max(1,min(self.zoom,32));self.update()
    def origin(self):
        if not self.composition:return QPointF()
        return QPointF((self.width()-self.composition.width*self.zoom)/2+self.pan.x(),(self.height()-self.composition.height*self.zoom)/2+self.pan.y())
    def to_comp(self,p):o=self.origin();return QPointF((p.x()-o.x())/self.zoom,(p.y()-o.y())/self.zoom)
    def to_widget(self,x,y):o=self.origin();return QPointF(o.x()+x*self.zoom,o.y()+y*self.zoom)
    def wheelEvent(self,event):self.zoom=max(1,min(32,self.zoom+(1 if event.angleDelta().y()>0 else -1)));self.update();event.accept()
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor("#20242b"))
        if self.composition is None or self.pixels is None:p.setPen(QColor("#adb5bd"));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"New Resource Composition");return
        o=self.origin();rect=QRectF(o.x(),o.y(),self.composition.width*self.zoom,self.composition.height*self.zoom);p.setClipRect(rect);size=max(4,4*self.zoom)
        for y in range(int(rect.top()),int(rect.bottom())+1,size):
            for x in range(int(rect.left()),int(rect.right())+1,size):p.fillRect(x,y,size,size,QColor("#b8bdc4") if ((x-int(rect.left()))//size+(y-int(rect.top()))//size)%2 else QColor("#e1e4e8"))
        pixels=np.ascontiguousarray(self.pixels);image=QImage(pixels.data,self.composition.width,self.composition.height,pixels.strides[0],QImage.Format.Format_RGBA8888).copy();p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,False);p.drawPixmap(rect,QPixmap.fromImage(image),QRectF(0,0,self.composition.width,self.composition.height));p.setClipping(False);p.setPen(QPen(QColor("#6ea8fe"),1));p.drawRect(rect)
        if self.layer:
            pos=self.layer.value("position",self.frame);center=self.to_widget(self.composition.width/2+pos[0],self.composition.height/2+pos[1]);p.setPen(QPen(QColor("#51cf66"),2));p.drawEllipse(center,6,6)
            pivot=self.to_widget(self.composition.width/2+pos[0]+self.layer.pivot_x-self.layer.pivot_x,self.composition.height/2+pos[1]);p.setPen(QPen(QColor("#ff6b6b"),2));p.drawLine(QPointF(pivot.x()-9,pivot.y()),QPointF(pivot.x()+9,pivot.y()));p.drawLine(QPointF(pivot.x(),pivot.y()-9),QPointF(pivot.x(),pivot.y()+9))
            if self.mode=="rotate":
                angle=float(self.layer.value("rotation",self.frame));end=center+QPointF(math.cos(math.radians(angle))*50,math.sin(math.radians(angle))*50);p.setPen(QPen(QColor("#ffd43b"),2));p.drawLine(center,end);p.drawEllipse(end,5,5)
    def _value(self):
        if self.mode=="pivot":return [self.layer.pivot_x,self.layer.pivot_y]
        return deepcopy(self.layer.value(self.mode,self.frame))
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.MiddleButton:self._panning=True;self._start_point=event.position()-self.pan;event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self.layer:self._drag=True;self._start_point=self.to_comp(event.position());self._start_value=self._value();event.accept();return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._panning:self.pan=event.position()-self._start_point;self.update();event.accept();return
        if not self._drag:return super().mouseMoveEvent(event)
        point=self.to_comp(event.position());delta=point-self._start_point
        if self.mode=="move":value=[self._start_value[0]+delta.x(),self._start_value[1]+delta.y()];prop="position"
        elif self.mode=="pivot":value=[self._start_value[0]+delta.x(),self._start_value[1]+delta.y()];prop="pivot"
        elif self.mode=="rotate":
            pos=self.layer.value("position",self.frame);cx=self.composition.width/2+pos[0];cy=self.composition.height/2+pos[1];value=math.degrees(math.atan2(point.y()-cy,point.x()-cx));value=round(value/15)*15 if event.modifiers()&Qt.KeyboardModifier.ShiftModifier else value;prop="rotation"
        else:
            start=max(.001,math.hypot(self._start_point.x()-self.composition.width/2,self._start_point.y()-self.composition.height/2));ratio=max(.01,math.hypot(point.x()-self.composition.width/2,point.y()-self.composition.height/2)/start);value=[max(.01,self._start_value[0]*ratio),max(.01,self._start_value[1]*ratio)];prop="scale"
        self.transform_changed.emit(prop,value,False);event.accept()
    def mouseReleaseEvent(self,event):
        if self._panning and event.button()==Qt.MouseButton.MiddleButton:self._panning=False;event.accept();return
        if self._drag:self._drag=False;self.transform_changed.emit("pivot" if self.mode=="pivot" else {"move":"position"}.get(self.mode,self.mode),self._value(),True);event.accept();return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and self._drag:self._drag=False;self.cancelled.emit("pivot" if self.mode=="pivot" else {"move":"position"}.get(self.mode,self.mode),self._start_value);event.accept();return
        super().keyPressEvent(event)

class ResourceEditorWidget(QWidget):
    import_requested=Signal(object);pivot_changed=Signal(str,str,float,float);create_emitter_requested=Signal(str,str);reimport_requested=Signal(str,str);delete_requested=Signal(str,str);resource_selected=Signal(str,str);composition_changed=Signal(str)
    def __init__(self,settings,parent=None):
        super().__init__(parent);self.settings=settings;self.project=None;self.resource=None;self.resource_type=None;self.composition=None;self.selected_layer=None;self.selected_property_id=None;self.frame_index=0;self._playing=False;self._loading=False;self._localization=None;self._row_map=[];self._gizmo_before={}
        root=QVBoxLayout(self);self.splitter=QSplitter(Qt.Orientation.Horizontal);left=QWidget();ll=QVBoxLayout(left);self.assets_title=QLabel("Assets");self.empty_label=QLabel();self.list=QListWidget();self.list.setObjectName("resourceLibraryList");self.import_button=QPushButton("Import Resources…");self.comps_title=QLabel("Compositions");self.comp_list=QListWidget();self.new_comp=QPushButton("New Resource Composition…");self.add_layer=QPushButton("Add Asset to Composition");self.delete_comp=QPushButton("Delete Composition");[ll.addWidget(w) for w in (self.assets_title,self.empty_label,self.list,self.import_button,self.comps_title,self.comp_list,self.new_comp,self.add_layer,self.delete_comp)]
        center=QWidget();cl=QVBoxLayout(center);modes=QHBoxLayout();self.gizmo_buttons={};
        for mode in ("move","rotate","scale","pivot"):
            button=QPushButton(mode.title());button.setCheckable(True);button.clicked.connect(lambda checked=False,m=mode:self.set_gizmo(m));self.gizmo_buttons[mode]=button;modes.addWidget(button)
        self.gizmo_buttons["rotate"].setChecked(True);cl.addLayout(modes);self.canvas=CompositionCanvas();self.status=QLabel();cl.addWidget(self.canvas,1);cl.addWidget(self.status)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setMinimumWidth(340);details=QWidget();dl=QVBoxLayout(details);self.details_title=QLabel("Layer Properties");self.info=QLabel();self.name_edit=QLineEdit();self.start=FocusWheelSpinBox();self.end=FocusWheelSpinBox();self.pivot_x=FocusWheelDoubleSpinBox();self.pivot_y=FocusWheelDoubleSpinBox();[w.setRange(-4096,4096) for w in (self.pivot_x,self.pivot_y)];self.start.setRange(0,511);self.end.setRange(0,511);self.layer_form=QFormLayout();self.layer_form.addRow("Name",self.name_edit);self.layer_form.addRow("Start",self.start);self.layer_form.addRow("End",self.end);self.layer_form.addRow("Pivot X",self.pivot_x);self.layer_form.addRow("Pivot Y",self.pivot_y);dl.addWidget(self.details_title);dl.addWidget(self.info);dl.addLayout(self.layer_form);self.add_property=QPushButton("+ Add Property");self.full_rotation=QPushButton("Add Full Rotation");dl.addWidget(self.add_property);dl.addWidget(self.full_rotation);self.property_body=QWidget();self.property_layout=QVBoxLayout(self.property_body);dl.addWidget(self.property_body);self.create_emitter=QPushButton("Create Particle Emitter from Resource");dl.addWidget(self.create_emitter);dl.addStretch();scroll.setWidget(details)
        [self.splitter.addWidget(w) for w in (left,center,scroll)];self.splitter.setSizes(self._sizes());self.splitter.splitterMoved.connect(lambda *a:self.settings.setValue("ui/resource_composition_splitter",self.splitter.sizes()));root.addWidget(self.splitter,1)
        controls=QHBoxLayout();self.previous=QPushButton("◀");self.play=QPushButton("▶");self.next=QPushButton("▶|");self.delete_keyframe=QPushButton("Delete Keyframe");self.timeline=QTableWidget();self.timeline.setMaximumHeight(230);self.timeline.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);[controls.addWidget(w) for w in (self.previous,self.play,self.next,self.delete_keyframe)];controls.addWidget(self.timeline,1);root.addLayout(controls)
        self.timer=QTimer(self);self.timer.setSingleShot(False);self.timer.timeout.connect(self._advance);self.import_button.clicked.connect(lambda:self.import_requested.emit(None));self.list.currentItemChanged.connect(self._asset_selected);self.comp_list.currentItemChanged.connect(self._comp_selected);self.new_comp.clicked.connect(self.new_composition_dialog);self.add_layer.clicked.connect(self.add_selected_asset);self.delete_comp.clicked.connect(self.remove_composition);self.previous.clicked.connect(self.previous_frame);self.next.clicked.connect(self.next_frame);self.play.clicked.connect(self.toggle_play);self.timeline.cellClicked.connect(self._timeline_clicked);self.timeline.verticalHeader().sectionClicked.connect(self._toggle_layer);self.add_property.clicked.connect(self.show_add_property);self.full_rotation.clicked.connect(self.add_full_rotation);self.delete_keyframe.clicked.connect(self.delete_current_keyframe);self.canvas.transform_changed.connect(self._gizmo_change);self.canvas.cancelled.connect(self._gizmo_cancel);self.name_edit.editingFinished.connect(self._rename);self.start.valueChanged.connect(self._layer_meta);self.end.valueChanged.connect(self._layer_meta);self.pivot_x.valueChanged.connect(self._layer_meta);self.pivot_y.valueChanged.connect(self._layer_meta);self.create_emitter.clicked.connect(lambda:self.composition and self.create_emitter_requested.emit("resource_composition",self.composition.id));self.setAcceptDrops(True);self._set_composition_enabled(False)
    def _sizes(self):
        value=self.settings.value("ui/resource_composition_splitter",[])
        try:s=[int(v) for v in value]
        except (TypeError,ValueError):s=[]
        return s if len(s)==3 and min(s)>=100 and s[2]>=300 else [250,680,360]
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and any(u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in SUPPORTED_RESOURCE_SUFFIXES for u in event.mimeData().urls()):event.acceptProposedAction()
    def dropEvent(self,event):self.import_requested.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]);event.acceptProposedAction()
    def refresh(self,project,select=None):
        self.project=project;asset_current=select or (self.list.currentItem().data(Qt.ItemDataRole.UserRole) if self.list.currentItem() else None);comp_current=self.composition.id if self.composition else None;self.list.blockSignals(True);self.comp_list.blockSignals(True);self.list.clear();self.comp_list.clear()
        for kind,items in (("source_asset",project.source_assets),("animation_clip",project.animation_clips)):
            heading=QListWidgetItem(self._localization.text("resource.static" if kind=="source_asset" else "resource.animated") if self._localization else ("Static Resources" if kind=="source_asset" else "Animated Resources"));heading.setFlags(Qt.ItemFlag.NoItemFlags);self.list.addItem(heading)
            for r in items:
                item=QListWidgetItem(f"{'●' if len(resource_frames(r))==1 else '▶'} {r.name}\n{r.source_format.upper()} · {r.width}×{r.height}");item.setData(Qt.ItemDataRole.UserRole,(kind,r.id));self.list.addItem(item)
                if asset_current==(kind,r.id):self.list.setCurrentItem(item)
        for composition in project.resource_compositions:
            item=QListWidgetItem(f"◆ {composition.name}\n{composition.width}×{composition.height} · {composition.frame_count}f · {composition.fps} FPS");item.setData(Qt.ItemDataRole.UserRole,composition.id);self.comp_list.addItem(item)
            if comp_current==composition.id:self.comp_list.setCurrentItem(item)
        self.list.blockSignals(False);self.comp_list.blockSignals(False);self.empty_label.setVisible(not(project.source_assets or project.animation_clips));
        if select:
            kind,identifier=select;items=project.source_assets if kind=="source_asset" else project.animation_clips;self.resource=next((r for r in items if r.id==identifier),None);self.resource_type=kind
            if self.resource:self._inspect_asset()
        if self.composition:
            self.composition=next((c for c in project.resource_compositions if c.id==self.composition.id),None)
            if self.composition:self._render()
    def select_resource(self,kind,identifier):
        self.refresh(self.project,(kind,identifier));self.resource_type=kind;self.resource=next((r for r in (self.project.source_assets if kind=="source_asset" else self.project.animation_clips) if r.id==identifier),None)
        if self.resource:self._inspect_asset()
    def _asset_selected(self,item,previous):
        data=item.data(Qt.ItemDataRole.UserRole) if item else None
        if not data or self.project is None:return
        kind,identifier=data;items=self.project.source_assets if kind=="source_asset" else self.project.animation_clips;self.resource=next((r for r in items if r.id==identifier),None);self.resource_type=kind;self._inspect_asset();self.resource_selected.emit(kind,identifier)

    def _inspect_asset(self):
        """Keep the former Resource Preview workflow available inside Assets."""
        self.stop();self.composition=None;self.selected_layer=None;self.frame_index=0;self._set_composition_enabled(False)
        for widget in (self.previous,self.play,self.next,self.pivot_x,self.pivot_y,self.create_emitter):widget.setEnabled(self.resource is not None)
        if self.resource is None:return
        self._loading=True;self.pivot_x.setValue(self.resource.pivot_x);self.pivot_y.setValue(self.resource.pivot_y);self._loading=False
        self.info.setText(f"{self.resource.name} · {self.resource.width}×{self.resource.height} · {len(resource_frames(self.resource))} frames")
        self._asset_timeline();self._render_asset()

    def _asset_timeline(self):
        frames=resource_frames(self.resource) if self.resource else []
        self.timeline.blockSignals(True);self.timeline.clear();self.timeline.setRowCount(1 if frames else 0);self.timeline.setColumnCount(len(frames))
        if frames:
            self.timeline.setVerticalHeaderLabels([self.resource.name]);self.timeline.setHorizontalHeaderLabels([str(i+1) for i in range(len(frames))])
            for index in range(len(frames)):self.timeline.setItem(0,index,QTableWidgetItem("■"))
            self.timeline.setCurrentCell(0,self.frame_index)
        self.timeline.blockSignals(False)

    def _render_asset(self):
        if self.resource is None:return
        frames=resource_frames(self.resource);pixels=frames[self.frame_index]
        preview=ResourceComposition(self.resource.name,self.resource.width,self.resource.height,max(1,getattr(self.resource,"fps",10)),len(frames),getattr(self.resource,"loop",False))
        self.canvas.set_state(preview,None,pixels,self.frame_index);self.status.setText(f"Frame {self.frame_index+1} / {len(frames)}")

    def _center(self):
        if self.resource is None:return
        self.pivot_x.setValue(self.resource.width/2);self.pivot_y.setValue(self.resource.height/2)
    def _comp_selected(self,item,previous):
        identifier=item.data(Qt.ItemDataRole.UserRole) if item else None
        if not identifier or self.project is None:return
        self.composition=next((c for c in self.project.resource_compositions if c.id==identifier),None);self.frame_index=0;self.selected_layer=self.composition.layers[0] if self.composition.layers else None;self._set_composition_enabled(True);self._load_layer();self._render();self._timeline()
    def create_composition(self,name="Composition",width=64,height=64,fps=12,frame_count=12,loop=True):
        names={c.name for c in self.project.resource_compositions};base=name;number=2
        while name in names:name=f"{base} ({number})";number+=1
        composition=ResourceComposition(name,width,height,fps,frame_count,loop);self.project.resource_compositions.append(composition);self.composition=composition;self.selected_layer=None;self.composition_changed.emit(composition.id);self.refresh(self.project);self._select_comp_item(composition.id);return composition
    def new_composition_dialog(self):
        dialog=NewCompositionDialog({c.name for c in self.project.resource_compositions},self._localization,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            c=dialog.composition();self.create_composition(c.name,c.width,c.height,c.fps,c.frame_count,c.loop)
    def _select_comp_item(self,identifier):
        for i in range(self.comp_list.count()):
            if self.comp_list.item(i).data(Qt.ItemDataRole.UserRole)==identifier:self.comp_list.setCurrentRow(i);return
    def add_selected_asset(self):
        if not self.composition or not self.resource:return None
        layer=CompositionLayer(self.resource.name,self.resource_type,self.resource.id,0,self.composition.frame_count-1,pivot_x=self.resource.pivot_x,pivot_y=self.resource.pivot_y);self.composition.layers.append(layer);self.selected_layer=layer;self._changed();self._load_layer();self._render();self._timeline();return layer
    def remove_composition(self):
        if not self.composition:return
        t=self._localization.text
        if any(e.settings.resource_type=="resource_composition" and e.settings.resource_id==self.composition.id for e in self.project.particle_emitters):QMessageBox.warning(self,t("composition.compositions"),t("composition.in_use"));return
        if QMessageBox.question(self,t("composition.compositions"),t("composition.delete_confirm"))!=QMessageBox.StandardButton.Yes:return
        self.project.resource_compositions.remove(self.composition);self.composition=None;self.selected_layer=None;self.canvas.set_state(None,None,None,0);self._set_composition_enabled(False);self.composition_changed.emit("");self.refresh(self.project)
    def _set_composition_enabled(self,value):
        for w in (self.add_layer,self.delete_comp,self.add_property,self.full_rotation,self.create_emitter,self.previous,self.play,self.next,self.delete_keyframe,self.name_edit,self.start,self.end,self.pivot_x,self.pivot_y):w.setEnabled(value)
    def _load_layer(self):
        self._loading=True
        if self.composition:self.info.setText(f"{self.composition.name} · {self.composition.width}×{self.composition.height} · {self.composition.frame_count} frames · {self.composition.fps} FPS");self.name_edit.setText(self.composition.name)
        if self.selected_layer:self.start.setValue(self.selected_layer.start_frame);self.end.setValue(self.selected_layer.end_frame);self.pivot_x.setValue(self.selected_layer.pivot_x);self.pivot_y.setValue(self.selected_layer.pivot_y)
        self._loading=False;self._properties()
    def _rename(self):
        if not self.composition or not self.name_edit.text().strip():return
        requested=self.name_edit.text().strip();names={c.name for c in self.project.resource_compositions if c is not self.composition};name=requested;number=2
        while name in names:name=f"{requested} ({number})";number+=1
        self.composition.name=name;self.name_edit.setText(name);self._changed();self.refresh(self.project)
    def _layer_meta(self,*a):
        if self._loading:return
        if self.selected_layer is None:
            if self.resource is not None:
                self.resource.pivot_x=self.pivot_x.value();self.resource.pivot_y=self.pivot_y.value();self.pivot_changed.emit(self.resource_type,self.resource.id,self.resource.pivot_x,self.resource.pivot_y)
            return
        self.selected_layer.start_frame=min(self.start.value(),self.composition.frame_count-1);self.selected_layer.end_frame=max(self.selected_layer.start_frame,min(self.end.value(),self.composition.frame_count-1));self.selected_layer.pivot_x=self.pivot_x.value();self.selected_layer.pivot_y=self.pivot_y.value();self._changed();self._render();self._timeline()
    def show_add_property(self):
        if not self.selected_layer:return
        dialog=AddPropertyDialog(self.selected_layer.tracks,self._localization,self)
        if dialog.exec()==QDialog.DialogCode.Accepted and dialog.selected_id:self.add_property_to_layer(dialog.selected_id)
    def add_property_to_layer(self,property_id):self.selected_layer.add_property(property_id);self._changed();self._properties();self._timeline();return self.selected_layer.tracks[property_id]
    def remove_property(self,property_id):
        if QMessageBox.question(self,self._localization.text("composition.properties"),self._localization.text("composition.remove_property_confirm"))!=QMessageBox.StandardButton.Yes:return
        self.selected_layer.remove_property(property_id);self._changed();self._properties();self._timeline()
    def _properties(self):
        while self.property_layout.count():
            item=self.property_layout.takeAt(0);widget=item.widget()
            if widget:widget.deleteLater()
        if not self.selected_layer:return
        for property_id,track in self.selected_layer.tracks.items():
            definitions=search_properties(property_id,"composition_layer");definition=definitions[0][0] if definitions else None;title_text=(definition.name_ko if self._localization and self._localization.language=="ko" else definition.name_en) if definition else property_id.title()
            row=QWidget();layout=QVBoxLayout(row);layout.setContentsMargins(0,2,0,2);title=QLabel(title_text);layout.addWidget(title);value=track.evaluate(self.frame_index);editors=[]
            values=value if isinstance(value,(list,tuple)) else [value]
            fields=QHBoxLayout()
            for index,item in enumerate(values):
                editor=FocusWheelDoubleSpinBox();editor.setRange(-4096,4096);editor.setDecimals(3);editor.setValue(float(item)*100 if property_id in {"scale","opacity"} else float(item));fields.addWidget(editor);editors.append(editor)
            easing=QComboBox();[easing.addItem(name,name) for name in ("Linear","Ease In","Ease Out","Ease In/Out")];existing=next((k for k in track.keyframes if k.frame==self.frame_index),None);easing.setCurrentText(existing.easing if existing else "Linear")
            key=QPushButton("◆");remove=QPushButton("×");fields.addWidget(easing);fields.addWidget(key);fields.addWidget(remove);layout.addLayout(fields);key.clicked.connect(lambda checked=False,p=property_id,e=editors,c=easing:self.set_keyframe(p,self._editor_value(p,e),c.currentData()));remove.clicked.connect(lambda checked=False,p=property_id:self.remove_property(p))
            for editor in editors:editor.valueChanged.connect(lambda value,p=property_id,e=editors:self._property_value(p,self._editor_value(p,e)))
            self.property_layout.addWidget(row)
        self.property_layout.addStretch()
    @staticmethod
    def _editor_value(property_id,editors):
        values=[e.value()/(100 if property_id in {"scale","opacity"} else 1) for e in editors];return values if property_id in {"position","scale"} else values[0]
    def _property_value(self,property_id,value):
        if self._loading:return
        track=self.selected_layer.tracks[property_id];existing=next((k for k in track.keyframes if k.frame==self.frame_index),None)
        if existing:existing.value=value
        else:track.default_value=value
        self._changed();self._render();self._timeline()
    def set_keyframe(self,property_id,value,easing="Linear"):
        track=self.selected_layer.add_property(property_id);track.set_keyframe(self.frame_index,value,easing);self._changed();self._properties();self._timeline()
    def delete_current_keyframe(self):
        if not self.selected_layer:return
        tracks=[self.selected_layer.tracks[self.selected_property_id]] if self.selected_property_id in self.selected_layer.tracks else self.selected_layer.tracks.values()
        for track in tracks:track.delete_keyframe(self.frame_index)
        self._changed();self._properties();self._timeline()
    def add_full_rotation(self,clockwise=True,turns=1):
        if not self.selected_layer:return
        track=self.selected_layer.add_property("rotation");track.set_keyframe(0,0,"Linear");track.set_keyframe(self.composition.frame_count-1,(360 if clockwise else -360)*turns,"Linear");self._changed();self._properties();self._timeline();self._render()
    def set_gizmo(self,mode):
        for key,button in self.gizmo_buttons.items():button.setChecked(key==mode)
        self.canvas.mode=mode
    def _gizmo_change(self,property_id,value,final):
        if not self.selected_layer:return
        if property_id not in self._gizmo_before:self._gizmo_before[property_id]=deepcopy(self.selected_layer.tracks.get(property_id)) if property_id!="pivot" else [self.selected_layer.pivot_x,self.selected_layer.pivot_y]
        if property_id=="pivot":self.selected_layer.pivot_x,self.selected_layer.pivot_y=value;self._loading=True;self.pivot_x.setValue(value[0]);self.pivot_y.setValue(value[1]);self._loading=False
        else:self.selected_layer.add_property(property_id).set_keyframe(self.frame_index,value)
        self.composition.touch();invalidate_composition_cache(self.composition.id);self._render();self._properties();self._timeline()
        if final:self._gizmo_before.pop(property_id,None);self.composition_changed.emit(self.composition.id)
    def _gizmo_cancel(self,property_id,value):
        before=self._gizmo_before.pop(property_id,None)
        if property_id=="pivot":self.selected_layer.pivot_x,self.selected_layer.pivot_y=before or value
        elif before is None:self.selected_layer.tracks.pop(property_id,None)
        else:self.selected_layer.tracks[property_id]=before
        self.composition.touch();self._render();self._properties();self._timeline()
    def _changed(self):self.composition.touch();invalidate_composition_cache(self.composition.id);self.composition_changed.emit(self.composition.id)
    def _render(self):
        if not self.composition:return
        pixels=render_composition_frame(self.project,self.composition,self.frame_index);self.canvas.set_state(self.composition,self.selected_layer,pixels,self.frame_index);self.status.setText(self._localization.text("composition.frame_status").format(current=self.frame_index+1,total=self.composition.frame_count,fps=self.composition.fps))
    def _timeline(self):
        if not self.composition:return
        self._row_map=[]
        for layer in self.composition.layers:
            self._row_map.append((layer,None))
            for property_id in layer.tracks:self._row_map.append((layer,property_id))
        self.timeline.blockSignals(True);self.timeline.setRowCount(len(self._row_map));self.timeline.setColumnCount(self.composition.frame_count);self.timeline.setHorizontalHeaderLabels([str(i+1) for i in range(self.composition.frame_count)]);headers=[]
        for row,(layer,property_id) in enumerate(self._row_map):
            headers.append(("  "+property_id.title()) if property_id else f"{'◉' if layer.visible else '○'} {layer.name}")
            for frame in range(self.composition.frame_count):
                text="◆" if property_id and any(k.frame==frame for k in layer.tracks[property_id].keyframes) else "■" if not property_id and layer.start_frame<=frame<=layer.end_frame else "·";item=QTableWidgetItem(text);item.setTextAlignment(Qt.AlignmentFlag.AlignCenter);self.timeline.setItem(row,frame,item)
        self.timeline.setVerticalHeaderLabels(headers);self.timeline.blockSignals(False)
        if self._row_map:self.timeline.setCurrentCell(next((i for i,v in enumerate(self._row_map) if v[0] is self.selected_layer),0),self.frame_index)
    def _timeline_clicked(self,row,column):
        self.set_frame(column)
        if self.composition is None:return
        if 0<=row<len(self._row_map):self.selected_layer,self.selected_property_id=self._row_map[row];self._load_layer();self._render()
    def _toggle_layer(self,row):
        if 0<=row<len(self._row_map) and self._row_map[row][1] is None:self._row_map[row][0].visible=not self._row_map[row][0].visible;self._changed();self._render();self._timeline()
    def set_frame(self,index):
        self.stop()
        if self.composition:self.frame_index=max(0,min(index,self.composition.frame_count-1));self._render();self._properties();self._timeline()
        elif self.resource:self.frame_index=max(0,min(index,len(resource_frames(self.resource))-1));self._render_asset();self._asset_timeline()
    def previous_frame(self):self.set_frame(self.frame_index-1)
    def next_frame(self):self.set_frame(self.frame_index+1)
    def toggle_play(self):
        if self._playing:self.stop();return
        if self.composition:
            if self.composition.frame_count<2:return
            interval=max(1,round(1000/self.composition.fps))
        else:
            if self.resource is None or len(resource_frames(self.resource))<2:return
            interval=resource_durations(self.resource)[self.frame_index]
        self._playing=True;self.play.setText("■");self.timer.start(interval)
    def stop(self):self._playing=False;self.timer.stop();self.play.setText("▶")
    def _advance(self):
        if not self._playing:return
        if self.composition is None:
            frames=resource_frames(self.resource);self.frame_index=(self.frame_index+1)%len(frames);self._render_asset();self._asset_timeline();self.timer.setInterval(resource_durations(self.resource)[self.frame_index]);return
        if self.frame_index>=self.composition.frame_count-1:
            if self.composition.loop:self.frame_index=0
            else:self.stop();return
        else:self.frame_index+=1
        self._render();self._properties();self._timeline()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.toggle_play();event.accept();return
        if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Comma):self.previous_frame();event.accept();return
        if event.key() in (Qt.Key.Key_Right,Qt.Key.Key_Period):self.next_frame();event.accept();return
        super().keyPressEvent(event)
    def remove_composition_property(self,property_id):self.remove_property(property_id)
    def retranslate_ui(self,l):
        self._localization=l;t=l.text;self.assets_title.setText(t("composition.assets"));self.comps_title.setText(t("composition.compositions"));self.import_button.setText(t("resource.import"));self.new_comp.setText(t("composition.new"));self.add_layer.setText(t("composition.add_asset"));self.delete_comp.setText(t("composition.delete"));self.details_title.setText(t("composition.properties"));self.add_property.setText(t("composition.add_property"));self.full_rotation.setText(t("composition.full_rotation"));self.create_emitter.setText(t("resource.create_emitter"));self.empty_label.setText(t("resource.empty"));
        for field,key in ((self.name_edit,"composition.name"),(self.start,"composition.start"),(self.end,"composition.end"),(self.pivot_x,"resource.pivot_x"),(self.pivot_y,"resource.pivot_y")):self.layer_form.labelForField(field).setText(t(key))
        self.delete_keyframe.setText(t("composition.delete_keyframe"));self.add_layer.setToolTip(t("composition.tooltip.add_asset"));self.add_property.setToolTip(t("composition.tooltip.add_property"));self.full_rotation.setToolTip(t("composition.tooltip.full_rotation"))
        for mode,key in (("move","gizmo.move"),("rotate","gizmo.rotate"),("scale","gizmo.scale"),("pivot","composition.pivot")):self.gizmo_buttons[mode].setText(t(key))
        if self.project:self.refresh(self.project)
