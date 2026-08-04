"""Timeline-driven reusable resource compositions."""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Any
from uuid import uuid4

EASINGS={"Linear","Ease In","Ease Out","Ease In/Out"}
PROPERTY_DEFAULTS={"position":[0.0,0.0],"rotation":0.0,"scale":[1.0,1.0],"opacity":1.0}

@dataclass
class Keyframe:
    frame:int;value:Any;easing:str="Linear"
    def __post_init__(self):
        self.frame=int(self.frame)
        if self.frame<0:raise ValueError("keyframe frame must be non-negative")
        if self.easing not in EASINGS:raise ValueError("unsupported keyframe easing")
    def to_dict(self):return {"frame":self.frame,"value":self.value,"easing":self.easing}
    @classmethod
    def from_dict(cls,data):return cls(int(data["frame"]),data["value"],str(data.get("easing","Linear")))

@dataclass
class AnimationTrack:
    property_id:str;default_value:Any;keyframes:list[Keyframe]=field(default_factory=list)
    def __post_init__(self):
        if self.property_id not in PROPERTY_DEFAULTS:raise ValueError("unsupported composition property")
        self._normalize()
    def _normalize(self):
        by_frame={k.frame:k for k in self.keyframes};self.keyframes=sorted(by_frame.values(),key=lambda k:k.frame)
    def set_keyframe(self,frame,value,easing="Linear"):
        self.keyframes.append(Keyframe(frame,value,easing));self._normalize();return next(k for k in self.keyframes if k.frame==frame)
    def delete_keyframe(self,frame):self.keyframes=[k for k in self.keyframes if k.frame!=frame]
    def evaluate(self,frame):
        if not self.keyframes:return self.default_value
        if frame<=self.keyframes[0].frame:return self.keyframes[0].value
        if frame>=self.keyframes[-1].frame:return self.keyframes[-1].value
        left=self.keyframes[0];right=self.keyframes[-1]
        for a,b in zip(self.keyframes,self.keyframes[1:]):
            if a.frame<=frame<=b.frame:left,right=a,b;break
        amount=(frame-left.frame)/(right.frame-left.frame)
        if left.easing=="Ease In":amount=amount*amount
        elif left.easing=="Ease Out":amount=1-(1-amount)*(1-amount)
        elif left.easing=="Ease In/Out":amount=2*amount*amount if amount<.5 else 1-((-2*amount+2)**2)/2
        def mix(a,b):return float(a)+(float(b)-float(a))*amount
        if isinstance(left.value,(list,tuple)):return [mix(a,b) for a,b in zip(left.value,right.value)]
        return mix(left.value,right.value)
    def to_dict(self):return {"property_id":self.property_id,"default_value":self.default_value,"keyframes":[k.to_dict() for k in self.keyframes]}
    @classmethod
    def from_dict(cls,data):return cls(str(data["property_id"]),data.get("default_value",PROPERTY_DEFAULTS[str(data["property_id"])]),[Keyframe.from_dict(k) for k in data.get("keyframes",[])])

@dataclass
class CompositionLayer:
    name:str;source_type:str;source_id:str;start_frame:int;end_frame:int;source_start_frame:int=0;visible:bool=True;pivot_x:float=0.0;pivot_y:float=0.0;tracks:dict[str,AnimationTrack]=field(default_factory=dict);id:str=field(default_factory=lambda:uuid4().hex)
    def __post_init__(self):
        if self.source_type not in {"source_asset","animation_clip"}:raise ValueError("unsupported composition layer source")
        if self.start_frame<0 or self.end_frame<self.start_frame:raise ValueError("invalid composition layer range")
    def add_property(self,property_id):
        if property_id not in PROPERTY_DEFAULTS:raise ValueError("unsupported composition property")
        return self.tracks.setdefault(property_id,AnimationTrack(property_id,PROPERTY_DEFAULTS[property_id]))
    def remove_property(self,property_id):self.tracks.pop(property_id,None)
    def value(self,property_id,frame):return self.tracks[property_id].evaluate(frame) if property_id in self.tracks else PROPERTY_DEFAULTS[property_id]
    def to_dict(self):return {"id":self.id,"name":self.name,"visible":self.visible,"source_type":self.source_type,"source_id":self.source_id,"start_frame":self.start_frame,"end_frame":self.end_frame,"source_start_frame":self.source_start_frame,"pivot_x":self.pivot_x,"pivot_y":self.pivot_y,"tracks":{k:v.to_dict() for k,v in self.tracks.items()}}
    @classmethod
    def from_dict(cls,data):return cls(id=str(data["id"]),name=str(data["name"]),visible=bool(data.get("visible",True)),source_type=str(data["source_type"]),source_id=str(data["source_id"]),start_frame=int(data.get("start_frame",0)),end_frame=int(data["end_frame"]),source_start_frame=int(data.get("source_start_frame",0)),pivot_x=float(data.get("pivot_x",0)),pivot_y=float(data.get("pivot_y",0)),tracks={k:AnimationTrack.from_dict(v) for k,v in data.get("tracks",{}).items()})

@dataclass
class ResourceComposition:
    name:str;width:int=64;height:int=64;fps:int=12;frame_count:int=12;loop:bool=True;layers:list[CompositionLayer]=field(default_factory=list);background_mode:str="transparent";pivot_x:float|None=None;pivot_y:float|None=None;revision:int=0;id:str=field(default_factory=lambda:uuid4().hex)
    def __post_init__(self):
        if not 1<=self.width<=1024 or not 1<=self.height<=1024:raise ValueError("composition size must be 1..1024")
        if not 1<=self.fps<=120 or not 1<=self.frame_count<=512:raise ValueError("invalid composition timing")
        if self.background_mode!="transparent":raise ValueError("only transparent compositions are supported")
        if self.pivot_x is None:self.pivot_x=self.width/2
        if self.pivot_y is None:self.pivot_y=self.height/2
    def touch(self):self.revision+=1
    def to_dict(self):return {"id":self.id,"name":self.name,"width":self.width,"height":self.height,"fps":self.fps,"frame_count":self.frame_count,"loop":self.loop,"background_mode":self.background_mode,"pivot_x":self.pivot_x,"pivot_y":self.pivot_y,"revision":self.revision,"layers":[l.to_dict() for l in self.layers]}
    @classmethod
    def from_dict(cls,data):return cls(id=str(data["id"]),name=str(data["name"]),width=int(data["width"]),height=int(data["height"]),fps=int(data["fps"]),frame_count=int(data["frame_count"]),loop=bool(data.get("loop",True)),background_mode=str(data.get("background_mode","transparent")),pivot_x=float(data.get("pivot_x",int(data["width"])/2)),pivot_y=float(data.get("pivot_y",int(data["height"])/2)),revision=int(data.get("revision",0)),layers=[CompositionLayer.from_dict(v) for v in data.get("layers",[])])
