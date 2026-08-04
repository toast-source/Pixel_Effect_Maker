"""PNG/GIF embedded resource import with per-frame timing."""
from pathlib import Path
from PIL import Image, ImageSequence
import numpy as np
from app.models.source_asset import SourceAsset
from app.models.animation_clip import AnimationClipAsset

class ResourceImportError(ValueError): pass
def import_resource(path):
    path=Path(path); ext=path.suffix.lower()
    if ext==".png":
        try: pixels=np.asarray(Image.open(path).convert("RGBA"),dtype=np.uint8)
        except Exception as exc: raise ResourceImportError(f"invalid PNG: {exc}") from exc
        return SourceAsset(path.name,pixels,source_path=str(path),source_format="png")
    if ext==".gif":
        try:
            image=Image.open(path); frames=[]; durations=[]
            for frame in ImageSequence.Iterator(image):
                frames.append(np.asarray(frame.convert("RGBA"),dtype=np.uint8)); durations.append(max(1,int(frame.info.get("duration",image.info.get("duration",100)) or 100)))
            return AnimationClipAsset(path.name,frames,fps=max(1,round(1000/(sum(durations)/len(durations)))),frame_durations_ms=durations,
                playback_mode="loop" if image.info.get("loop",0)==0 else "hold",loop=image.info.get("loop",0)==0,source_format="gif",source_path=str(path))
        except Exception as exc: raise ResourceImportError(f"invalid GIF: {exc}") from exc
    raise ResourceImportError(f"unsupported resource type: {ext}")
