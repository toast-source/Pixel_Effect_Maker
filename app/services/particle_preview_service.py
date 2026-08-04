"""Debounced asynchronous non-destructive particle previews."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from queue import Empty, SimpleQueue
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from app.models.animation_clip import AnimationClipAsset
from app.models.source_asset import SourceAsset
from app.models.particle_emitter import ParticleEmitter, ParticleEmitterSettings
from app.models.project import Project
from app.services.particle_render_service import render_particle_frames

@dataclass
class ParticleDraft:
    emitter_id: str; settings: ParticleEmitterSettings; revision: int=0; is_dirty: bool=False
@dataclass
class ParticlePreviewSession:
    emitter_id: str; revision: int; frames: list
@dataclass(frozen=True)
class ParticlePreviewSnapshot:
    emitter_id: str; revision: int; width: int; height: int; fps: int; resource: object; settings: ParticleEmitterSettings; context_revision: int=0
    @classmethod
    def from_project(cls, project, emitter_id, revision, settings, context_revision=0):
        if settings.resource_type=="resource_composition":resource=deepcopy(project)
        else:
            items=project.source_assets if settings.resource_type=="source_asset" else project.animation_clips
            resource=next(c for c in items if c.id==settings.clip_asset_id)
        return cls(emitter_id,revision,project.width,project.height,project.fps,resource,deepcopy(settings),context_revision)
def render_particle_snapshot(snapshot):
    if snapshot.settings.resource_type=="resource_composition":project=snapshot.resource
    else:
        project=Project.create_default("Particle Preview",snapshot.width,snapshot.height,snapshot.fps,True)
        (project.source_assets if snapshot.settings.resource_type=="source_asset" else project.animation_clips).append(snapshot.resource)
    emitter=ParticleEmitter(id=snapshot.emitter_id,name="Preview",settings=deepcopy(snapshot.settings)); return render_particle_frames(project,emitter)
class _Worker(QRunnable):
    def __init__(self,snapshot,queue): super().__init__(); self.snapshot=snapshot; self.queue=queue
    def run(self):
        try: self.queue.put((self.snapshot.context_revision,self.snapshot.emitter_id,self.snapshot.revision,render_particle_snapshot(self.snapshot),""))
        except Exception as exc: self.queue.put((self.snapshot.context_revision,self.snapshot.emitter_id,self.snapshot.revision,None,str(exc)))
class ParticlePreviewManager(QObject):
    state_changed=Signal(str,str); preview_ready=Signal(str,int,object); preview_failed=Signal(str,int,str)
    def __init__(self,parent=None):
        super().__init__(parent); self.drafts={}; self.sessions={}; self._project=None; self._pending=None; self._context_revision=0; self._queue=SimpleQueue(); self._pool=QThreadPool.globalInstance(); self._timer=QTimer(self); self._timer.setSingleShot(True); self._timer.timeout.connect(self._start); self._poll=QTimer(self); self._poll.timeout.connect(self._drain); self._poll.start(20)
    def ensure_draft(self,emitter):
        return self.drafts.setdefault(emitter.id,ParticleDraft(emitter.id,deepcopy(emitter.settings)))
    def update(self,project,emitter,settings,immediate=False):
        draft=self.ensure_draft(emitter); draft.settings=deepcopy(settings); draft.revision+=1; draft.is_dirty=(draft.settings!=emitter.settings); self.sessions.pop(emitter.id,None); self._project=project; self._pending=(emitter.id,draft.revision); self.state_changed.emit(emitter.id,"settings_changed"); self._timer.start(0 if immediate else 250); return draft
    def schedule(self,project,emitter_id): self._project=project; draft=self.drafts[emitter_id]; self._pending=(emitter_id,draft.revision); self._timer.start(0)
    def _start(self):
        if not self._pending or self._project is None:return
        emitter_id,revision=self._pending; self._pending=None; draft=self.drafts.get(emitter_id)
        if draft is None or draft.revision!=revision:return
        try: snapshot=ParticlePreviewSnapshot.from_project(self._project,emitter_id,revision,draft.settings,self._context_revision)
        except Exception as exc: self.preview_failed.emit(emitter_id,revision,str(exc)); return
        self.state_changed.emit(emitter_id,"updating"); self._pool.start(_Worker(snapshot,self._queue))
    def _drain(self):
        while True:
            try: context_revision,emitter_id,revision,frames,error=self._queue.get_nowait()
            except Empty:return
            if context_revision!=self._context_revision:continue
            draft=self.drafts.get(emitter_id)
            if draft is None or draft.revision!=revision:continue
            if error: self.state_changed.emit(emitter_id,"failed"); self.preview_failed.emit(emitter_id,revision,error)
            else: self.sessions[emitter_id]=ParticlePreviewSession(emitter_id,revision,frames); self.state_changed.emit(emitter_id,"ready"); self.preview_ready.emit(emitter_id,revision,frames)
    def revert(self,emitter): self.drafts[emitter.id]=ParticleDraft(emitter.id,deepcopy(emitter.settings)); self.sessions.pop(emitter.id,None); return self.drafts[emitter.id]
    def mark_applied(self,emitter): self.drafts[emitter.id]=ParticleDraft(emitter.id,deepcopy(emitter.settings)); self.sessions.pop(emitter.id,None)
    def reset_context(self): self._context_revision+=1; self._timer.stop(); self._pending=None; self.drafts.clear(); self.sessions.clear(); self._project=None
