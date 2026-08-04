from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QFormLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from app.models.property_registry import search_properties
from app.ui.focus_wheel_widgets import FocusWheelDoubleSpinBox, FocusWheelSpinBox


class PropertySearchDialog(QDialog):
    def __init__(self, tracks, localization, parent=None):
        super().__init__(parent); self.localization=localization; self.selected_id=None; layout=QVBoxLayout(self); self.search=QLineEdit(); self.list=QListWidget(); self.add=QPushButton(); self.cancel=QPushButton(); buttons=QHBoxLayout(); buttons.addStretch(); buttons.addWidget(self.cancel); buttons.addWidget(self.add); layout.addWidget(self.search); layout.addWidget(self.list); layout.addLayout(buttons); self.tracks=tracks
        self.search.textChanged.connect(self.refresh); self.list.itemDoubleClicked.connect(lambda item:self.accept_selected()); self.add.clicked.connect(self.accept_selected); self.cancel.clicked.connect(self.reject); self.retranslate(); self.refresh()

    def refresh(self,*args):
        self.list.clear(); language=self.localization.language
        for definition,added in search_properties(self.search.text(),"composition_layer",self.tracks):
            name=definition.name_ko if language=="ko" else definition.name_en; description=definition.description_ko if language=="ko" else definition.description_en; item=QListWidgetItem(f"{name}{' ✓' if added else ''}\n{description}"); item.setData(Qt.ItemDataRole.UserRole,definition.id)
            if added: item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEnabled)
            self.list.addItem(item)

    def accept_selected(self):
        item=self.list.currentItem()
        if item and item.flags()&Qt.ItemFlag.ItemIsEnabled: self.selected_id=str(item.data(Qt.ItemDataRole.UserRole)); self.accept()

    def retranslate(self):
        t=self.localization.text; self.setWindowTitle(t("composition.add_property")); self.search.setPlaceholderText(t("composition.search")); self.add.setText(t("composition.add")); self.cancel.setText(t("v2.cancel"))


class CompositionInspector(QWidget):
    changed=Signal(object,object); use_requested=Signal()

    def __init__(self,parent=None):
        super().__init__(parent); layout=QVBoxLayout(self); self.title=QLabel(); self.name=QLineEdit(); self.info=QLabel(); self.pivot_x=FocusWheelDoubleSpinBox(); self.pivot_y=FocusWheelDoubleSpinBox(); [widget.setRange(-4096,4096) for widget in (self.pivot_x,self.pivot_y)]; self.form=QFormLayout(); self.form.addRow(" ",self.name); self.form.addRow(" ",self.pivot_x); self.form.addRow(" ",self.pivot_y); self.center=QPushButton(); self.use=QPushButton(); self.use.setObjectName("useResourceInEffectButton"); self.use.setDefault(True)
        layout.addWidget(self.title); layout.addWidget(self.info); layout.addLayout(self.form); layout.addWidget(self.center); layout.addWidget(self.use); layout.addStretch(); self.composition=None; self._loading=False; self.localization=None
        self.name.editingFinished.connect(self._apply); self.pivot_x.valueChanged.connect(self._apply); self.pivot_y.valueChanged.connect(self._apply); self.center.clicked.connect(self._center); self.use.clicked.connect(self.use_requested)

    def set_composition(self,composition):
        self.composition=composition; self._loading=True
        if composition:
            self.name.setText(composition.name); playback=self.localization.text("v2.loop" if composition.loop else "v2.hold") if self.localization else ""; template=self.localization.text("v2.comp_info") if self.localization else "{width} × {height} · {fps} FPS · {frames}"; self.info.setText(template.format(width=composition.width,height=composition.height,fps=composition.fps,frames=composition.frame_count,playback=playback)); self.pivot_x.setValue(composition.pivot_x); self.pivot_y.setValue(composition.pivot_y)
        self._loading=False

    def _apply(self,*args):
        if self._loading or not self.composition:return
        before={"name":self.composition.name,"pivot_x":self.composition.pivot_x,"pivot_y":self.composition.pivot_y};after={"name":self.name.text().strip() or self.composition.name,"pivot_x":self.pivot_x.value(),"pivot_y":self.pivot_y.value()}
        for key,value in after.items():setattr(self.composition,key,value)
        if before!=after:self.changed.emit(before,after)

    def _center(self):
        if self.composition: self.pivot_x.setValue(self.composition.width/2); self.pivot_y.setValue(self.composition.height/2)

    def retranslate(self,localization):
        self.localization=localization;t=localization.text; self.title.setText(t("v2.composition_inspector")); self.form.labelForField(self.name).setText(t("composition.name")); self.form.labelForField(self.pivot_x).setText(t("v2.output_pivot_x")); self.form.labelForField(self.pivot_y).setText(t("v2.output_pivot_y")); self.center.setText(t("v2.center_output_pivot")); self.use.setText(t("v2.use_in_effect")); self.use.setToolTip(t("v2.use_in_effect_tip"));self.set_composition(self.composition)


class LayerInspector(QScrollArea):
    changed=Signal(object,object); mode_changed=Signal(str); add_property_requested=Signal(); full_rotation_requested=Signal(); center_pivot_requested=Signal(); use_requested=Signal(); keyframe_requested=Signal(str,object,str); property_value_requested=Signal(str,object); remove_property_requested=Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent); self.setWidgetResizable(True); self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); body=QWidget(); body.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.MinimumExpanding); self.layout=QVBoxLayout(body); self.title=QLabel(); self.name=QLineEdit(); self.source=QLabel(); self.source.setWordWrap(True); self.source.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred); self.start=FocusWheelSpinBox(); self.end=FocusWheelSpinBox(); self.visible=QCheckBox(); self.pivot_x=FocusWheelDoubleSpinBox(); self.pivot_y=FocusWheelDoubleSpinBox(); [widget.setRange(-4096,4096) for widget in (self.pivot_x,self.pivot_y)]; self.start.setRange(0,511);self.end.setRange(0,511); self.form=QFormLayout(); self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for widget in (self.name,self.source,self.start,self.end,self.visible,self.pivot_x,self.pivot_y): self.form.addRow(" ",widget)
        self.layout.addWidget(self.title); self.layout.addLayout(self.form); self.center=QPushButton(); self.layout.addWidget(self.center); modes=QGridLayout(); self.mode_buttons={}
        for index,mode in enumerate(("move","rotate","scale","pivot")):
            button=QPushButton();button.setCheckable(True);button.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);button.clicked.connect(lambda checked=False,value=mode:self.mode_changed.emit(value));self.mode_buttons[mode]=button;modes.addWidget(button,index//2,index%2)
        self.mode_buttons["move"].setChecked(True);self.layout.addLayout(modes);self.add_property=QPushButton();self.full_rotation=QPushButton();self.full_rotation.setObjectName("fullRotationButton");self.use=QPushButton();self.use.setObjectName("useResourceInEffectFromLayerButton");self.use.setDefault(True);self.use.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);self.use.setMinimumHeight(36);self.layout.addWidget(self.add_property);self.layout.addWidget(self.full_rotation);self.property_body=QWidget();self.property_body.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.MinimumExpanding);self.property_layout=QVBoxLayout(self.property_body);self.property_layout.setContentsMargins(0,4,0,4);self.layout.addWidget(self.property_body);self.layout.addWidget(self.use);self.layout.addStretch();self.setWidget(body);self.layer=None;self.frame=0;self._loading=False;self.localization=None;self.property_cards={}
        self.name.editingFinished.connect(self._apply);self.start.valueChanged.connect(self._apply);self.end.valueChanged.connect(self._apply);self.visible.toggled.connect(self._apply);self.pivot_x.valueChanged.connect(self._apply);self.pivot_y.valueChanged.connect(self._apply);self.center.clicked.connect(self.center_pivot_requested);self.add_property.clicked.connect(self.add_property_requested);self.full_rotation.clicked.connect(self.full_rotation_requested);self.use.clicked.connect(self.use_requested)

    def set_layer(self,layer,source,frame):
        self.layer,self.frame=layer,frame;self._loading=True
        if layer:
            self.name.setText(layer.name);self.source.setText(source.name if source else "");self.start.setValue(layer.start_frame);self.end.setValue(layer.end_frame);self.visible.setChecked(layer.visible);self.pivot_x.setValue(layer.pivot_x);self.pivot_y.setValue(layer.pivot_y)
        self._loading=False;self._properties()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.widget():self.widget().setMaximumWidth(max(0,self.viewport().width()))

    def set_mode(self,mode):
        for key,button in self.mode_buttons.items():button.setChecked(key==mode)

    def _apply(self,*args):
        if self._loading or not self.layer:return
        before={key:getattr(self.layer,key) for key in ("name","start_frame","end_frame","visible","pivot_x","pivot_y")};after={"name":self.name.text().strip() or self.layer.name,"start_frame":self.start.value(),"end_frame":max(self.start.value(),self.end.value()),"visible":self.visible.isChecked(),"pivot_x":self.pivot_x.value(),"pivot_y":self.pivot_y.value()}
        for key,value in after.items():setattr(self.layer,key,value)
        if before!=after:self.changed.emit(before,after)

    def _properties(self):
        self.property_cards={}
        while self.property_layout.count():
            item=self.property_layout.takeAt(0);widget=item.widget()
            if widget:widget.deleteLater()
        if not self.layer:return
        for property_id,track in self.layer.tracks.items():
            card=QFrame();card.setObjectName("propertyCard_"+property_id);card.setFrameShape(QFrame.Shape.StyledPanel);card.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred);card_layout=QVBoxLayout(card);card_layout.setContentsMargins(8,6,8,8);header=QHBoxLayout();title=QLabel(self.localization.text("property."+property_id) if self.localization else property_id.title());title.setWordWrap(True);remove=QPushButton("×");remove.setFixedSize(28,28);remove.setToolTip(self.localization.text("property.remove") if self.localization else "Remove");header.addWidget(title,1);header.addWidget(remove);card_layout.addLayout(header);value=track.evaluate(self.frame);editors=[];value_form=QFormLayout();value_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow);value_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            values=value if isinstance(value,(list,tuple)) else [value]
            labels=("property.x","property.y") if property_id in {"position","scale"} else ("property.value",)
            for label_key,part in zip(labels,values):
                editor=FocusWheelDoubleSpinBox();editor.setRange(-4096,4096);editor.setDecimals(3);editor.setMinimumWidth(0);editor.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);editor.setSuffix(" %" if property_id in {"scale","opacity"} else "°" if property_id=="rotation" else " px");editor.setValue(float(part)*(100 if property_id in {"scale","opacity"} else 1));value_form.addRow(self.localization.text(label_key) if self.localization else label_key,editor);editors.append(editor)
            card_layout.addLayout(value_form)
            easing=QComboBox()
            for name in ("Linear","Ease In","Ease Out","Ease In/Out"):easing.addItem(self.localization.text("easing."+name.lower().replace(" ","_").replace("/","_")) if self.localization else name,name)
            existing=next((item for item in track.keyframes if item.frame==self.frame),None);easing.setCurrentIndex(max(0,easing.findData(existing.easing if existing else "Linear")))
            easing.setMinimumWidth(0);easing.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);key=QPushButton("◆");key.setFixedSize(34,28);key.setToolTip(self.localization.text("composition.add_keyframe") if self.localization else "Add Keyframe");footer=QHBoxLayout();footer.addWidget(QLabel(self.localization.text("property.easing") if self.localization else "Easing"));footer.addWidget(easing,1);footer.addWidget(key);card_layout.addLayout(footer);key.clicked.connect(lambda checked=False,p=property_id,e=editors,c=easing:self.keyframe_requested.emit(p,self._value(p,e),c.currentData()));remove.clicked.connect(lambda checked=False,p=property_id:self.remove_property_requested.emit(p));[editor.valueChanged.connect(lambda value,p=property_id,e=editors:self.property_value_requested.emit(p,self._value(p,e))) for editor in editors];self.property_layout.addWidget(card);self.property_cards[property_id]={"card":card,"editors":editors,"easing":easing,"keyframe":key,"remove":remove}

    @staticmethod
    def _value(property_id,editors):
        values=[editor.value()/(100 if property_id in {"scale","opacity"} else 1) for editor in editors];return values if property_id in {"position","scale"} else values[0]

    def retranslate(self,localization):
        self.localization=localization;t=localization.text;self.title.setText(t("v2.layer_inspector"))
        for widget,key in ((self.name,"v2.layer_name"),(self.source,"v2.source_asset"),(self.start,"composition.start"),(self.end,"composition.end"),(self.visible,"v2.visible"),(self.pivot_x,"v2.layer_pivot_x"),(self.pivot_y,"v2.layer_pivot_y")):self.form.labelForField(widget).setText(t(key))
        self.center.setText(t("v2.center_layer_pivot"));self.add_property.setText(t("composition.add_property"));self.full_rotation.setText(t("v2.full_rotation"));self.use.setText(t("v2.use_in_effect"));self.use.setToolTip(t("v2.use_in_effect_tip"))
        for mode,key in (("move","gizmo.move"),("rotate","gizmo.rotate"),("scale","gizmo.scale"),("pivot","composition.pivot")):self.mode_buttons[mode].setText(t(key));self.mode_buttons[mode].setToolTip(t("gizmo.tooltip."+mode) if mode!="pivot" else t("v2.center_layer_pivot"))
        self._properties()
