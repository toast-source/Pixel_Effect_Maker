"""Deterministic nearest-neighbor Resource Composition renderer."""
from __future__ import annotations
import numpy as np
from app.models.animation_clip import AnimationClipAsset
from app.models.frame import empty_pixels
from app.models.project import Project
from app.models.resource_composition import ResourceComposition,CompositionLayer
from app.models.source_asset import SourceAsset
from app.services.effect_render_service import render_transformed_source

_CACHE:dict[tuple,list[np.ndarray]]={}
def invalidate_composition_cache(composition_id=None):
    if composition_id is None:_CACHE.clear()
    else:
        for key in list(_CACHE):
            if key[0]==composition_id:_CACHE.pop(key,None)

def _source(project,layer):
    items=project.source_assets if layer.source_type=="source_asset" else project.animation_clips
    return next((item for item in items if item.id==layer.source_id),None)
def _clip_index(clip,elapsed_ms):
    durations=clip.frame_durations_ms or [max(1,round(1000/clip.fps))]*len(clip.frames);total=sum(durations)
    if clip.loop or clip.playback_mode=="loop":elapsed_ms%=total
    elif elapsed_ms>=total:
        if clip.playback_mode=="once":return None
        return len(clip.frames)-1
    cumulative=0
    for index,duration in enumerate(durations):
        cumulative+=duration
        if elapsed_ms<cumulative:return index
    return len(clip.frames)-1
def _pixels_at(project,composition,layer,frame):
    source=_source(project,layer)
    if source is None:return None
    if isinstance(source,SourceAsset):return source.pixels
    local=max(0,frame-layer.start_frame+layer.source_start_frame);elapsed=local*1000/composition.fps;index=_clip_index(source,elapsed)
    return None if index is None else source.frames[index]
def render_composition_frame(project:Project,composition:ResourceComposition,frame:int)->np.ndarray:
    if not 0<=frame<composition.frame_count:raise ValueError("composition frame out of range")
    output=empty_pixels(composition.width,composition.height)
    for layer in composition.layers:
        if not layer.visible or frame<layer.start_frame or frame>layer.end_frame:continue
        pixels=_pixels_at(project,composition,layer,frame)
        if pixels is None:continue
        position=layer.value("position",frame);rotation=float(layer.value("rotation",frame));scale=layer.value("scale",frame);opacity=float(layer.value("opacity",frame))
        asset=SourceAsset(layer.name,pixels,pivot_x=layer.pivot_x,pivot_y=layer.pivot_y)
        render_transformed_source(output,asset,position_x=composition.width/2+float(position[0]),position_y=composition.height/2+float(position[1]),rotation=rotation,scale_x=float(scale[0]),scale_y=float(scale[1]),horizontal_tilt=0,vertical_tilt=0,perspective=0,opacity=max(0,min(1,opacity)))
    return output
def render_composition_frames(project,composition,use_cache=True):
    key=(composition.id,composition.revision,composition.width,composition.height,composition.fps,composition.frame_count)
    if use_cache and key in _CACHE:return [frame.copy() for frame in _CACHE[key]]
    frames=[render_composition_frame(project,composition,index) for index in range(composition.frame_count)]
    _CACHE[key]=[frame.copy() for frame in frames];return frames
def composition_as_clip(project,composition):
    return AnimationClipAsset(composition.name,render_composition_frames(project,composition),fps=composition.fps,pivot_x=composition.pivot_x,pivot_y=composition.pivot_y,playback_mode="loop" if composition.loop else "hold",loop=composition.loop,source_format="composition",frame_durations_ms=[max(1,round(1000/composition.fps))]*composition.frame_count)
