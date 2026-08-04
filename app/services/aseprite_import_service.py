"""Aseprite CLI adapter; never modifies the input file."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json, subprocess
from .resource_import_service import import_resource, ResourceImportError
def import_aseprite(path,executable,timeout=20):
    source=Path(path)
    with TemporaryDirectory(prefix="pem_ase_") as folder:
        target=Path(folder)/"frames.gif"
        try: result=subprocess.run([str(executable),"-b",str(source),"--save-as",str(target)],capture_output=True,text=True,timeout=timeout,check=False)
        except subprocess.TimeoutExpired as exc: raise ResourceImportError("Aseprite CLI timed out") from exc
        if result.returncode or not target.exists(): raise ResourceImportError("Aseprite CLI did not produce frames")
        clip=import_resource(target); clip.name=source.name; clip.source_format=source.suffix.lower().lstrip("."); clip.source_path=str(source); return clip
