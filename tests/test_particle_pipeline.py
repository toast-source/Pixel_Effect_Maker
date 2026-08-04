from __future__ import annotations
from copy import deepcopy
import json
import numpy as np
import pytest
from PIL import Image

from app.models.animation_clip import AnimationClipAsset
from app.models.effect_generator import TransformEmitter, TransformEmitterSettings
from app.models.particle_emitter import ParticleEmitter, ParticleEmitterSettings
from app.models.project import FORMAT_VERSION, Project, ProjectError
from app.models.source_asset import SourceAsset
from app.services.clip_service import create_clip_from_generator, update_clip_from_generator
from app.services.effect_render_service import apply_rendered_frames
from app.services.particle_render_service import apply_particle_frames, build_particle_instances, particle_clip_frame, render_particle_frames
from app.services.preview_export_service import export_preview_sequence

def clip_asset(mode="loop"):
    frames=[]
    for color in ((255,0,0,255),(0,255,0,128),(0,0,255,255)):
        frame=np.zeros((3,3,4),dtype=np.uint8); frame[1,1]=color; frames.append(frame)
    return AnimationClipAsset("Spark",frames,fps=12,playback_mode=mode)

def settings(clip_id, **changes):
    value=ParticleEmitterSettings(clip_asset_id=clip_id,output_frame_count=8,particle_count_min=4,particle_count_max=7,
        origin_x=8,origin_y=8,speed_min=1,speed_max=3,lifetime_min=3,lifetime_max=7,seed=42)
    for key,item in changes.items():setattr(value,key,item)
    return value

def test_animation_clip_copies_frames_and_round_trips():
    original=clip_asset(); source=original.frames[0].copy(); data=original.to_dict(); loaded=AnimationClipAsset.from_dict(data)
    original.frames[0][1,1]=0
    assert np.array_equal(loaded.frames[0],source); assert loaded.playback_mode=="loop"

def test_create_and_explicit_update_clip_are_independent():
    project=Project.create_default(width=4,height=4); asset=SourceAsset("s",np.zeros((1,1,4),dtype=np.uint8)); project.source_assets.append(asset)
    generator=TransformEmitter("g",TransformEmitterSettings(asset.id)); project.generators.append(generator)
    output=[np.full((4,4,4),10,dtype=np.uint8)]; apply_rendered_frames(project,generator,output)
    clip=create_clip_from_generator(project,generator); frozen=clip.frames[0].copy()
    project.frames[0].layer_pixels[generator.generated_layer_id][:]=77
    assert np.array_equal(clip.frames[0],frozen)
    update_clip_from_generator(project,clip,generator); assert np.all(clip.frames[0]==77)

def test_particle_instances_are_deterministic_and_ranges_hold():
    s=settings("c",spawn_shape="box",box_width=10,box_height=6,start_delay_min=1,start_delay_max=3,scale_min=.5,scale_max=2,rotation_min=-10,rotation_max=20,angular_velocity_min=-2,angular_velocity_max=4,clip_speed_min=.5,clip_speed_max=2,random_start_frame=True)
    first=build_particle_instances(s,3); second=build_particle_instances(deepcopy(s),3)
    assert first==second; assert 4<=len(first)<=7
    assert all(3<=p.start_x<=13 and 5<=p.start_y<=11 and .5<=p.scale<=2 and 0<=p.clip_start_frame<3 for p in first)
    s.seed=43; assert build_particle_instances(s,3)!=first

@pytest.mark.parametrize("shape",["point","line","circle","box"])
def test_all_spawn_shapes_are_supported(shape):
    s=settings("c",spawn_shape=shape,particle_count_min=20,particle_count_max=20,line_end_x=18,line_end_y=8,radius=5,box_width=8,box_height=6)
    particles=build_particle_instances(s,3)
    if shape=="point": assert {(p.start_x,p.start_y) for p in particles}=={(8,8)}
    elif shape=="line": assert all(8<=p.start_x<=18 and p.start_y==8 for p in particles)
    elif shape=="circle": assert all(abs(np.hypot(p.start_x-8,p.start_y-8)-5)<1e-6 for p in particles)
    else: assert all(4<=p.start_x<=12 and 5<=p.start_y<=11 for p in particles)

def test_burst_over_time_and_radial_velocity():
    burst=build_particle_instances(settings("c",particle_count_min=4,particle_count_max=4,start_delay_min=0,start_delay_max=0),3)
    assert {p.birth_frame for p in burst}=={0}
    over=build_particle_instances(settings("c",emission_mode="over_time",emission_duration=7,particle_count_min=4,particle_count_max=4,start_delay_min=0,start_delay_max=0),3)
    assert [p.birth_frame for p in over]==[0,2,4,6]
    radial=build_particle_instances(settings("c",spawn_shape="circle",direction_mode="radial_outward",direction_spread_degrees=0,particle_count_min=8,particle_count_max=8),3)
    assert all((p.start_x-8)*p.velocity_x+(p.start_y-8)*p.velocity_y>0 for p in radial)

def test_once_loop_hold_clip_playback():
    from app.models.particle_emitter import ParticleInstance
    p=ParticleInstance(0,10,0,0,0,0,1,0,0,0,1,1)
    assert particle_clip_frame(clip_asset("once"),p,3) is None
    assert np.array_equal(particle_clip_frame(clip_asset("loop"),p,3),clip_asset().frames[0])
    assert np.array_equal(particle_clip_frame(clip_asset("hold"),p,9),clip_asset().frames[-1])

def test_particle_render_is_deterministic_transparent_and_clipped():
    project=Project.create_default(width=16,height=16); clip=clip_asset(); project.animation_clips.append(clip)
    emitter=ParticleEmitter("P",settings(clip.id,origin_x=15,origin_y=15)); project.particle_emitters.append(emitter)
    first=render_particle_frames(project,emitter); second=render_particle_frames(project,emitter)
    assert len(first)==8 and all(f.shape==(16,16,4) for f in first); assert all(np.array_equal(a,b) for a,b in zip(first,second))
    assert project.frames[0].layer_pixels[project.layers[0].id].sum()==0

def test_particle_bake_preserves_layers_and_is_atomic_on_validation():
    project=Project.create_default(width=8,height=8); clip=clip_asset(); project.animation_clips.append(clip); emitter=ParticleEmitter("P",settings(clip.id)); project.particle_emitters.append(emitter)
    ordinary=project.layers[0].id; ordinary_before=project.frames[0].layer_pixels[ordinary].copy(); outputs=render_particle_frames(project,emitter); layer=apply_particle_frames(project,emitter,outputs)
    assert layer.name=="Particle: P" and np.array_equal(project.frames[0].layer_pixels[ordinary],ordinary_before)
    before=project.frames[0].layer_pixels[layer.id].copy()
    with pytest.raises(ValueError):apply_particle_frames(project,emitter,[np.zeros((1,1,4),dtype=np.uint8)])
    assert np.array_equal(project.frames[0].layer_pixels[layer.id],before)

def test_preview_sequence_export_is_numbered_rgba_and_non_overwriting(tmp_path):
    frames=clip_asset().frames; paths=export_preview_sequence(frames,tmp_path,"Fire Burst")
    assert [p.name for p in paths]==["Fire_Burst_0001.png","Fire_Burst_0002.png","Fire_Burst_0003.png"]
    assert Image.open(paths[1]).mode=="RGBA"
    with pytest.raises(FileExistsError):export_preview_sequence(frames,tmp_path,"Fire Burst")

def test_v2_migrates_empty_collections_and_v3_round_trip_rejects_future():
    project=Project.create_default(width=8,height=8); legacy=project.to_dict(); legacy["format_version"]=2; legacy.pop("animation_clips"); legacy.pop("particle_emitters")
    migrated=Project.from_dict(legacy); assert migrated.animation_clips==[] and migrated.particle_emitters==[] and migrated.format_version==5
    clip=clip_asset(); migrated.animation_clips.append(clip); emitter=ParticleEmitter("P",settings(clip.id)); migrated.particle_emitters.append(emitter)
    loaded=Project.from_dict(migrated.to_dict()); assert loaded.animation_clips[0].id==clip.id and loaded.particle_emitters[0].settings.seed==42
    future=migrated.to_dict(); future["format_version"]=FORMAT_VERSION+1
    with pytest.raises(ProjectError):Project.from_dict(future)
