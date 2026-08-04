"""Scrollable properties for the first executable Particle Emitter flow."""
from __future__ import annotations
from random import SystemRandom
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget
from app.models.particle_emitter import ParticleEmitter, ParticleEmitterSettings
from .focus_wheel_widgets import FocusWheelComboBox, FocusWheelDoubleSpinBox, FocusWheelSpinBox

class ParticlePropertiesPanel(QScrollArea):
    draft_changed = Signal(str, object); refresh_requested = Signal(str); bake_requested = Signal(str, object)
    revert_requested = Signal(str); export_requested = Signal(str); gizmo_mode_changed = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self.setWidgetResizable(True); self.setMinimumWidth(360); self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.emitter_id = None; self._loading = False; self._localization = None
        body=QWidget(); self.layout=QVBoxLayout(body); self.title=QLabel("Particle Emitter Properties"); self.layout.addWidget(self.title);self._group_records=[]
        self.clip=FocusWheelComboBox(); self.output_frame_count=self._i(1,512); self.start_frame=self._i(0,511)
        self.emission_mode=self._combo(("burst","over_time")); self.count_min=self._i(0,4096); self.count_max=self._i(0,4096); self.emission_duration=self._i(1,512)
        self.spawn_shape=self._combo(("point","line","circle","box")); self.origin_x=self._n(-4096,4096); self.origin_y=self._n(-4096,4096); self.line_end_x=self._n(-4096,4096); self.line_end_y=self._n(-4096,4096); self.radius=self._n(0,4096); self.box_width=self._n(0,4096); self.box_height=self._n(0,4096); self.start_angle=self._n(-3600,3600); self.end_angle=self._n(-3600,3600)
        self.direction_mode=self._combo(("fixed","radial_outward")); self.direction_degrees=self._n(-3600,3600); self.direction_spread_degrees=self._n(0,360)
        self.speed_min=self._n(0,1024); self.speed_max=self._n(0,1024); self.lifetime_min=self._i(1,512); self.lifetime_max=self._i(1,512); self.scale_min=self._n(.01,16); self.scale_max=self._n(.01,16); self.rotation_min=self._n(-3600,3600); self.rotation_max=self._n(-3600,3600); self.angular_velocity_min=self._n(-3600,3600); self.angular_velocity_max=self._n(-3600,3600); self.start_delay_min=self._i(0,512); self.start_delay_max=self._i(0,512); self.clip_speed_min=self._n(.01,16); self.clip_speed_max=self._n(.01,16); self.random_start_frame=QCheckBox("Random Start Frame"); self.opacity_start=self._n(0,1); self.opacity_end=self._n(0,1); self.seed=self._i(-2147483647,2147483647)
        self.clip_group=self._group("Particle Resource", (("Resource",self.clip),("Output Frames",self.output_frame_count),("Start Frame",self.start_frame)))
        self._group("Emission", (("Mode",self.emission_mode),("Count Min",self.count_min),("Count Max",self.count_max),("Duration",self.emission_duration)))
        self._group("Spawn Shape", (("Shape",self.spawn_shape),("Origin X",self.origin_x),("Origin Y",self.origin_y),("Line End X",self.line_end_x),("Line End Y",self.line_end_y),("Radius",self.radius),("Box Width",self.box_width),("Box Height",self.box_height),("Start Angle",self.start_angle),("End Angle",self.end_angle)))
        self._group("Direction", (("Mode",self.direction_mode),("Direction",self.direction_degrees),("Spread",self.direction_spread_degrees),("Speed Min",self.speed_min),("Speed Max",self.speed_max)))
        self._group("Random Range", (("Lifetime Min",self.lifetime_min),("Lifetime Max",self.lifetime_max),("Scale Min",self.scale_min),("Scale Max",self.scale_max),("Rotation Min",self.rotation_min),("Rotation Max",self.rotation_max),("Angular Velocity Min",self.angular_velocity_min),("Angular Velocity Max",self.angular_velocity_max),("Start Delay Min",self.start_delay_min),("Start Delay Max",self.start_delay_max),("Clip Speed Min",self.clip_speed_min),("Clip Speed Max",self.clip_speed_max),("Random Start Frame",self.random_start_frame),("Opacity Start",self.opacity_start),("Opacity End",self.opacity_end),("Seed",self.seed)))
        self.randomize=QPushButton("Randomize Seed"); self.refresh=QPushButton("Refresh Preview"); self.bake=QPushButton("Bake to Frames"); self.export=QPushButton("Export Preview Sequence…"); self.revert=QPushButton("Revert Changes")
        for w in (self.randomize,self.refresh,self.bake,self.export,self.revert): self.layout.addWidget(w)
        self.layout.addStretch(); self.setWidget(body)
        self.controls=body.findChildren(QSpinBox)+body.findChildren(QDoubleSpinBox)+body.findChildren(QComboBox)
        for w in self.controls:
            signal=w.currentIndexChanged if isinstance(w,FocusWheelComboBox) else w.valueChanged; signal.connect(self._changed)
        self.random_start_frame.toggled.connect(self._changed); self.randomize.clicked.connect(self._randomize); self.refresh.clicked.connect(lambda: self.emitter_id and self.refresh_requested.emit(self.emitter_id)); self.bake.clicked.connect(lambda: self.emitter_id and self.bake_requested.emit(self.emitter_id,self.settings())); self.export.clicked.connect(lambda: self.emitter_id and self.export_requested.emit(self.emitter_id)); self.revert.clicked.connect(lambda: self.emitter_id and self.revert_requested.emit(self.emitter_id))
    def _i(self,a,b): w=FocusWheelSpinBox(); w.setRange(a,b); return w
    def _n(self,a,b): w=FocusWheelDoubleSpinBox(); w.setRange(a,b); w.setDecimals(3); return w
    def _combo(self, values): w=FocusWheelComboBox(); [w.addItem(v,v) for v in values]; return w
    def _group(self,title,rows):
        g=QGroupBox(title);f=QFormLayout(g);records=[]
        for name,w in rows:f.addRow(name,w);records.append((name,w))
        self._group_records.append((title,g,f,records));self.layout.addWidget(g);return g
    def set_emitter(self, emitter: ParticleEmitter|None, project):
        self._loading=True; self.emitter_id=None if emitter is None else emitter.id; self.clip.clear()
        t=self._localization.text if self._localization else lambda key:{"particle.resource_compositions":"Resource Compositions","resource.static":"Static Resources","resource.animated":"Animated Resources"}.get(key,key)
        self.clip.addItem(t("particle.resource_compositions"),None);self.clip.model().item(self.clip.count()-1).setEnabled(False);composition_heading=self.clip.count()-1
        [self.clip.addItem(c.name,("resource_composition",c.id)) for c in project.resource_compositions]
        self.clip.addItem(t("resource.static"),None);self.clip.model().item(self.clip.count()-1).setEnabled(False);static_heading=self.clip.count()-1
        [self.clip.addItem(c.name,("source_asset",c.id)) for c in project.source_assets]
        self.clip.addItem(t("resource.animated"),None);self.clip.model().item(self.clip.count()-1).setEnabled(False);animated_heading=self.clip.count()-1
        [self.clip.addItem(c.name,("animation_clip",c.id)) for c in project.animation_clips]
        self._heading_indexes=(composition_heading,static_heading,animated_heading)
        self.widget().setEnabled(emitter is not None)
        if emitter: self.set_settings(emitter.settings)
        self._loading=False
    def set_settings(self,s):
        self._loading=True
        mapping={"clip":"clip_asset_id","count_min":"particle_count_min","count_max":"particle_count_max"}
        for name in ("clip","output_frame_count","start_frame","emission_mode","count_min","count_max","emission_duration","spawn_shape","origin_x","origin_y","line_end_x","line_end_y","radius","box_width","box_height","start_angle","end_angle","direction_mode","direction_degrees","direction_spread_degrees","speed_min","speed_max","lifetime_min","lifetime_max","scale_min","scale_max","rotation_min","rotation_max","angular_velocity_min","angular_velocity_max","start_delay_min","start_delay_max","clip_speed_min","clip_speed_max","opacity_start","opacity_end","seed"):
            w=getattr(self,name); value=(s.resource_type,s.resource_id) if name=="clip" else getattr(s,mapping.get(name,name))
            if isinstance(w,FocusWheelComboBox):
                index=w.findData(value)
                if name=="clip" and index<0:
                    index=next((i for i in range(w.count()) if w.itemData(i) is not None and tuple(w.itemData(i))==value),-1)
                w.setCurrentIndex(max(0,index))
            else:w.setValue(value)
        self.random_start_frame.setChecked(s.random_start_frame); self._loading=False
    def settings(self):
        def v(name): w=getattr(self,name); return w.currentData() if isinstance(w,FocusWheelComboBox) else w.value()
        resource=v("clip") or ("animation_clip","")
        return ParticleEmitterSettings(clip_asset_id=str(resource[1]),resource_type=str(resource[0]),output_frame_count=v("output_frame_count"),start_frame=v("start_frame"),emission_mode=str(v("emission_mode")),particle_count_min=v("count_min"),particle_count_max=v("count_max"),emission_duration=v("emission_duration"),spawn_shape=str(v("spawn_shape")),origin_x=v("origin_x"),origin_y=v("origin_y"),line_end_x=v("line_end_x"),line_end_y=v("line_end_y"),radius=v("radius"),box_width=v("box_width"),box_height=v("box_height"),start_angle=v("start_angle"),end_angle=v("end_angle"),direction_mode=str(v("direction_mode")),direction_degrees=v("direction_degrees"),direction_spread_degrees=v("direction_spread_degrees"),speed_min=v("speed_min"),speed_max=v("speed_max"),lifetime_min=v("lifetime_min"),lifetime_max=v("lifetime_max"),scale_min=v("scale_min"),scale_max=v("scale_max"),rotation_min=v("rotation_min"),rotation_max=v("rotation_max"),angular_velocity_min=v("angular_velocity_min"),angular_velocity_max=v("angular_velocity_max"),start_delay_min=v("start_delay_min"),start_delay_max=v("start_delay_max"),clip_speed_min=v("clip_speed_min"),clip_speed_max=v("clip_speed_max"),random_start_frame=self.random_start_frame.isChecked(),opacity_start=v("opacity_start"),opacity_end=v("opacity_end"),seed=v("seed"))
    def _changed(self,*args):
        if not self._loading and self.emitter_id: self.draft_changed.emit(self.emitter_id,self.settings())
    def _randomize(self): self.seed.setValue(SystemRandom().randint(-2147483647,2147483647))
    def retranslate_ui(self,l):
        self._localization=l; t=l.text; self.title.setText(t("particle.title")); self.randomize.setText(t("particle.randomize_seed")); self.refresh.setText(t("effects.refresh_preview")); self.bake.setText(t("effects.bake")); self.export.setText(t("effects.export_preview")); self.revert.setText(t("effects.revert"))
        group_keys={"Particle Resource":"particle.resource","Emission":"particle.emission","Spawn Shape":"particle.spawn_shape","Direction":"particle.direction","Random Range":"particle.random_range"}
        field_keys={"Resource":"particle.resource_label","Output Frames":"particle.output_frames","Start Frame":"particle.start_frame","Mode":"particle.mode","Count Min":"particle.count_min","Count Max":"particle.count_max","Duration":"particle.duration","Shape":"particle.shape","Origin X":"particle.origin_x","Origin Y":"particle.origin_y","Line End X":"particle.line_end_x","Line End Y":"particle.line_end_y","Radius":"particle.radius","Box Width":"particle.box_width","Box Height":"particle.box_height","Start Angle":"particle.start_angle","End Angle":"particle.end_angle","Direction":"particle.direction_value","Spread":"particle.spread","Speed Min":"particle.speed_min","Speed Max":"particle.speed_max","Lifetime Min":"particle.lifetime_min","Lifetime Max":"particle.lifetime_max","Scale Min":"particle.scale_min","Scale Max":"particle.scale_max","Rotation Min":"particle.rotation_min","Rotation Max":"particle.rotation_max","Angular Velocity Min":"particle.angular_velocity_min","Angular Velocity Max":"particle.angular_velocity_max","Start Delay Min":"particle.start_delay_min","Start Delay Max":"particle.start_delay_max","Clip Speed Min":"particle.clip_speed_min","Clip Speed Max":"particle.clip_speed_max","Random Start Frame":"particle.random_start_frame","Opacity Start":"particle.opacity_start","Opacity End":"particle.opacity_end","Seed":"particle.seed"}
        for title,group,form,records in self._group_records:
            group.setTitle(t(group_keys[title]))
            for name,widget in records:form.labelForField(widget).setText(t(field_keys[name]))
        self.random_start_frame.setText(t("particle.random_start_frame"))
        self.randomize.setToolTip(t("particle.randomize_seed"));self.refresh.setToolTip(t("effects.refresh_preview"));self.bake.setToolTip(t("effects.bake"));self.export.setToolTip(t("effects.export_preview"));self.revert.setToolTip(t("effects.revert"))
        if hasattr(self,"_heading_indexes"):
            for index,key in zip(self._heading_indexes,("particle.resource_compositions","resource.static","resource.animated")):self.clip.setItemText(index,t(key))
