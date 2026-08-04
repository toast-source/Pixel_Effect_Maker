import numpy as np
from PIL import Image
from PySide6.QtCore import QSettings
from app.models.project import Project,FORMAT_VERSION
from app.models.particle_emitter import ParticleEmitter,ParticleEmitterSettings
from app.models.property_registry import search_properties
from app.services.resource_import_service import import_resource
from app.services.particle_render_service import render_particle_frames
from app.services.aseprite_locator_service import parse_libraryfolders
def test_png_and_gif_import_and_v4_roundtrip(tmp_path):
    png=tmp_path/"x.PNG"; Image.new("RGBA",(2,2),(1,2,3,4)).save(png); source=import_resource(png); assert source.pixels.shape==(2,2,4)
    gif=tmp_path/"x.GIF"; frames=[Image.new("RGBA",(2,2),(255,0,0,255)),Image.new("RGBA",(2,2),(0,255,0,128))]; frames[0].save(gif,save_all=True,append_images=frames[1:],duration=[40,120],loop=0)
    clip=import_resource(gif); assert clip.frame_durations_ms==[40,120] and len(clip.frames)==2
    project=Project.create_default(width=8,height=8); project.source_assets.append(source); project.animation_clips.append(clip)
    loaded=Project.from_dict(project.to_dict()); assert loaded.format_version==FORMAT_VERSION==5 and loaded.animation_clips[0].frame_durations_ms==[40,120]
def test_static_resource_particle_and_visibility():
    project=Project.create_default(width=8,height=8); from app.models.source_asset import SourceAsset
    pixels=np.zeros((1,1,4),dtype=np.uint8);pixels[0,0]=255; source=SourceAsset("s",pixels);project.source_assets.append(source)
    emitter=ParticleEmitter("p",ParticleEmitterSettings(source.id,resource_type="source_asset",particle_count_min=1,particle_count_max=1,speed_min=0,speed_max=0,lifetime_min=2,lifetime_max=2,origin_x=4,origin_y=4,output_frame_count=2)); project.particle_emitters.append(emitter)
    assert render_particle_frames(project,emitter)[0][...,3].any(); project.layers[0].visible=False; assert project.compose_frame(0)[...,3].sum()==0
def test_property_search_is_bilingual_filtered_and_stable():
    assert search_properties("rotate","clip")[0][0].id=="clip.rotation"; assert search_properties("회전","clip")[0][0].id=="clip.rotation"; assert search_properties("speed","resource")==[]
def test_safe_steam_library_parser():
    assert parse_libraryfolders('"path" "D:\\\\SteamLibrary"')
