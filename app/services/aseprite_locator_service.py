"""Safe Windows Aseprite discovery and validation."""
from pathlib import Path
import os, shutil, subprocess
def parse_libraryfolders(text):
    import re
    return [Path(value.replace("\\\\","\\")) for value in re.findall(r'"path"\s+"([^"]+)"',text)]
def validate_aseprite(path,timeout=3):
    candidate=Path(path)
    if not candidate.is_file() or candidate.suffix.lower()!=".exe": return False,""
    try:
        result=subprocess.run([str(candidate),"--version"],capture_output=True,text=True,timeout=timeout,check=False)
        return result.returncode==0,(result.stdout or result.stderr).strip()
    except (OSError,subprocess.TimeoutExpired): return False,""
def locate_aseprite(settings=None):
    candidates=[]
    if settings:
        configured=settings.value("external_tools/aseprite_path","")
        if configured:candidates.append(Path(str(configured)))
    for root in filter(None,[os.environ.get("ProgramFiles(x86)"),os.environ.get("ProgramFiles")]): candidates.append(Path(root)/"Steam/steamapps/common/Aseprite/Aseprite.exe")
    found=shutil.which("aseprite")
    if found:candidates.append(Path(found))
    for candidate in candidates:
        if validate_aseprite(candidate)[0]:return candidate
    return None
