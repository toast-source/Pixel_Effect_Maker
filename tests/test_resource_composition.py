import numpy as np
import pytest
from app.models.project import Project,FORMAT_VERSION,ProjectError
from app.models.source_asset import SourceAsset
from app.models.animation_clip import AnimationClipAsset
from app.models.resource_composition import ResourceComposition,CompositionLayer,AnimationTrack,Keyframe
from app.models.particle_emitter import ParticleEmitter,ParticleEmitterSettings,ParticleInstance
from app.services.resource_composition_render_service import render_composition_frame,render_composition_frames,composition_as_clip,invalidate_composition_cache
from app.services.particle_render_service import render_particle_frames,particle_clip_frame
def pattern():
    p=np.zeros((3,3,4),dtype=np.uint8);p[0,1]=[255,0,0,255];p[1,1]=[0,255,0,255];return p
def setup():
    project=Project.create_default(width=8,height=8);asset=SourceAsset("a",pattern());project.source_assets.append(asset);comp=ResourceComposition("A",8,8,12,12,True);layer=CompositionLayer("a", "source_asset",asset.id,0,11,pivot_x=asset.pivot_x,pivot_y=asset.pivot_y);comp.layers.append(layer);project.resource_compositions.append(comp);return project,asset,comp,layer
def test_track_keyframes_replace_sort_delete_and_evaluate():
    track=AnimationTrack("rotation",0);track.set_keyframe(11,360);track.set_keyframe(0,0);track.set_keyframe(11,180)
    assert [k.frame for k in track.keyframes]==[0,11] and track.evaluate(11)==180 and 80<track.evaluate(6)<110
    track.delete_keyframe(11);assert track.evaluate(5)==0
@pytest.mark.parametrize("easing",["Linear","Ease In","Ease Out","Ease In/Out"])
def test_all_easings(easing):
    track=AnimationTrack("opacity",0);track.set_keyframe(0,0,easing);track.set_keyframe(10,1);assert 0<=track.evaluate(5)<=1
def test_composition_v5_roundtrip_and_v4_migration():
    project,asset,comp,layer=setup();layer.add_property("rotation").set_keyframe(0,0);data=project.to_dict();loaded=Project.from_dict(data);assert loaded.format_version==FORMAT_VERSION==5 and loaded.resource_compositions[0].layers[0].tracks["rotation"].keyframes[0].value==0
    data["format_version"]=4;data.pop("resource_compositions");migrated=Project.from_dict(data);assert migrated.resource_compositions==[]
def test_renderer_position_rotation_scale_opacity_visibility_and_source_immutable():
    project,asset,comp,layer=setup();before=asset.pixels.copy();base=render_composition_frame(project,comp,0);assert base[...,3].any()
    layer.add_property("position").set_keyframe(0,[2,0]);layer.add_property("rotation").set_keyframe(0,90);layer.add_property("scale").set_keyframe(0,[2,2]);layer.add_property("opacity").set_keyframe(0,.5);comp.touch();changed=render_composition_frame(project,comp,0);assert changed[...,3].max()<=128 and not np.array_equal(base,changed) and np.array_equal(asset.pixels,before)
    layer.visible=False;assert not render_composition_frame(project,comp,0)[...,3].any()
def test_animated_layer_duration_and_range():
    project,asset,comp,layer=setup();red=np.zeros((1,1,4),dtype=np.uint8);red[0,0]=[255,0,0,255];blue=red.copy();blue[0,0]=[0,0,255,255];clip=AnimationClipAsset("c",[red,blue],fps=10,frame_durations_ms=[50,150],playback_mode="loop");project.animation_clips.append(clip);comp.layers=[CompositionLayer("c","animation_clip",clip.id,1,11,pivot_x=.5,pivot_y=.5)]
    assert not render_composition_frame(project,comp,0)[...,3].any();assert render_composition_frame(project,comp,1)[...,0].max()==255;assert render_composition_frame(project,comp,2)[...,2].max()==255
def test_composition_particle_frame_source_preview_path():
    project,asset,comp,layer=setup();layer.add_property("rotation").set_keyframe(0,0);layer.tracks["rotation"].set_keyframe(11,360);comp.touch();clip=composition_as_clip(project,comp);assert len(clip.frames)==12
    emitter=ParticleEmitter("p",ParticleEmitterSettings(comp.id,resource_type="resource_composition",output_frame_count=4,particle_count_min=1,particle_count_max=1,speed_min=0,speed_max=0,lifetime_min=4,lifetime_max=4,origin_x=4,origin_y=4));project.particle_emitters.append(emitter);frames=render_particle_frames(project,emitter);assert len(frames)==4 and any(f[...,3].any() for f in frames)
def test_missing_composition_layer_source_rejected():
    project,asset,comp,layer=setup();layer.source_id="missing"
    with pytest.raises(ProjectError):Project.from_dict(project.to_dict())

def test_particle_time_uses_effect_fps_before_composition_fps_and_speed():
    def clip(fps,mode="loop"):
        frames=[]
        for value in range(4):
            frame=np.zeros((1,1,4),dtype=np.uint8);frame[0,0]=[value,0,0,255];frames.append(frame)
        return AnimationClipAsset("timed",frames,fps=fps,playback_mode=mode,source_format="composition",frame_durations_ms=[round(1000/fps)]*4)
    def instance(speed=1,start=0):return ParticleInstance(0,20,0,0,0,0,1,0,0,start,speed,1)
    assert particle_clip_frame(clip(12),instance(),1,effect_fps=12)[0,0,0]==1
    assert particle_clip_frame(clip(24),instance(),1,effect_fps=12)[0,0,0]==2
    assert particle_clip_frame(clip(12),instance(),1,effect_fps=24)[0,0,0]==0
    assert particle_clip_frame(clip(24),instance(.5),1,effect_fps=12)[0,0,0]==1
    assert particle_clip_frame(clip(12),instance(2),1,effect_fps=12)[0,0,0]==2
    assert particle_clip_frame(clip(12),instance(start=2),0,effect_fps=12)[0,0,0]==2
    assert particle_clip_frame(clip(12),instance(),4,effect_fps=12)[0,0,0]==0
    assert particle_clip_frame(clip(12,"hold"),instance(),20,effect_fps=12)[0,0,0]==3
