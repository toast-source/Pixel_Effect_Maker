"""Stable searchable property definitions independent of display language."""
from dataclasses import dataclass
import re
@dataclass(frozen=True)
class PropertyDefinition:
    id:str; name_en:str; name_ko:str; description_en:str; description_ko:str; category:str; tags:tuple[str,...]; editor_types:tuple[str,...]; default_value:object; unit:str|None=None
REGISTRY=(
 PropertyDefinition("position","Position","위치","Moves the layer on the composition canvas","컴포지션 캔버스에서 레이어를 이동합니다","Transform",("move","translation","x","y","이동","좌표"),("composition_layer",),[0.0,0.0],"px"),
 PropertyDefinition("rotation","Rotation","회전","Rotates the layer around its pivot","레이어를 피벗 기준으로 회전합니다","Transform",("rotate","angle","spin","turn","회전","각도","돌리기","스핀"),("composition_layer",),0.0,"degree"),
 PropertyDefinition("scale","Scale","크기","Scales the layer around its pivot","레이어를 피벗 기준으로 확대하거나 축소합니다","Transform",("size","zoom","resize","크기","확대","축소"),("composition_layer",),[1.0,1.0],"percent"),
 PropertyDefinition("opacity","Opacity","불투명도","Changes layer visibility without changing source pixels","원본 픽셀을 바꾸지 않고 레이어 불투명도를 조절합니다","Appearance",("alpha","transparent","fade","투명","페이드"),("composition_layer",),1.0,"percent"),
 PropertyDefinition("particle.speed","Speed","속도","Particle movement speed","파티클 이동 속도","Motion",("velocity","fast","slow","이동","빠르기"),("particle",),1.0,"px/frame"),
 PropertyDefinition("particle.direction","Direction","방향","Movement angle","이동 각도","Motion",("angle","rotate","각도","회전"),("particle",),-90.0,"degree"),
 PropertyDefinition("particle.lifetime","Lifetime","수명","Visible particle lifetime","파티클 표시 수명","Particle",("life","duration","시간"),("particle",),12,"frames"),
 PropertyDefinition("clip.rotation","Rotation","회전","Clip rotation over time","클립 시간별 회전","Transform",("rotate","angle","spin","돌리기","각도"),("clip",),0.0,"degree"),
 PropertyDefinition("resource.pivot_x","Pivot X","피벗 X","Horizontal pivot","수평 피벗","Resource",("origin","center","중심"),("resource",),0.0,"px"),
 PropertyDefinition("resource.pivot_y","Pivot Y","피벗 Y","Vertical pivot","수직 피벗","Resource",("origin","center","중심"),("resource",),0.0,"px"),)
def search_properties(query,editor_type,enabled=()):
    needle=re.sub(r"\s+","",query).casefold(); result=[]
    for item in REGISTRY:
        if editor_type not in item.editor_types:continue
        hay=" ".join((item.id,item.name_en,item.name_ko,item.description_en,item.description_ko,item.category,*item.tags)); normalized=re.sub(r"\s+","",hay).casefold()
        if not needle or needle in normalized:result.append((item,item.id in enabled))
    return result
