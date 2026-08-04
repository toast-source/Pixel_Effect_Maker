"""Debounced asynchronous live preview orchestration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from queue import Empty, SimpleQueue
from typing import Callable

import numpy as np
from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, QTimer, Signal

from app.models.effect_generator import TransformEmitter, TransformEmitterSettings
from app.models.preview import GeneratorDraft, PreviewSession
from app.models.project import Project
from app.models.source_asset import SourceAsset
from app.services.effect_render_service import render_generator_frames


@dataclass(frozen=True)
class PreviewRenderSnapshot:
    generator_id: str
    revision: int
    width: int
    height: int
    fps: int
    existing_frame_count: int
    asset: SourceAsset
    settings: TransformEmitterSettings
    context_revision: int = 0

    @classmethod
    def from_project(
        cls,
        project: Project,
        generator_id: str,
        revision: int,
        settings: TransformEmitterSettings,
        context_revision: int = 0,
    ) -> "PreviewRenderSnapshot":
        asset = next(
            item
            for item in project.source_assets
            if item.id == settings.source_asset_id
        )
        return cls(
            generator_id=generator_id,
            revision=revision,
            width=project.width,
            height=project.height,
            fps=project.fps,
            existing_frame_count=len(project.frames),
            asset=SourceAsset(
                id=asset.id,
                name=asset.name,
                pixels=asset.pixels.copy(),
                pivot_x=asset.pivot_x,
                pivot_y=asset.pivot_y,
                source_path=asset.source_path,
            ),
            settings=deepcopy(settings),
            context_revision=context_revision,
        )


def render_preview_snapshot(snapshot: PreviewRenderSnapshot) -> list[np.ndarray]:
    """Render a snapshot without reading or mutating the live project."""
    project = Project.create_default(
        "Preview", snapshot.width, snapshot.height, snapshot.fps, True
    )
    while len(project.frames) < snapshot.existing_frame_count:
        project.add_frame()
    project.source_assets.append(snapshot.asset)
    generator = TransformEmitter(
        id=snapshot.generator_id,
        name="Preview",
        settings=deepcopy(snapshot.settings),
    )
    project.generators.append(generator)
    return render_generator_frames(project, generator)[: snapshot.settings.output_frames]


class _PreviewWorker(QRunnable):
    def __init__(
        self,
        snapshot: PreviewRenderSnapshot,
        renderer: Callable[[PreviewRenderSnapshot], list[np.ndarray]],
        results: SimpleQueue,
    ) -> None:
        super().__init__()
        self.snapshot = snapshot
        self.renderer = renderer
        self.results = results

    def run(self) -> None:
        try:
            frames = self.renderer(self.snapshot)
            self.results.put(
                (
                    self.snapshot.context_revision,
                    self.snapshot.generator_id,
                    self.snapshot.revision,
                    frames,
                    "",
                )
            )
        except Exception as exc:  # worker boundary: report a safe message to the UI
            self.results.put(
                (
                    self.snapshot.context_revision,
                    self.snapshot.generator_id,
                    self.snapshot.revision,
                    None,
                    str(exc),
                )
            )


class PreviewManager(QObject):
    """Own generator drafts, debounce, worker revisions, and preview sessions."""

    state_changed = Signal(str, str)
    preview_ready = Signal(str, int, object)
    preview_failed = Signal(str, int, str)

    SETTINGS_KEY = "effects/auto_preview"

    def __init__(
        self,
        settings: QSettings,
        renderer: Callable[[PreviewRenderSnapshot], list[np.ndarray]] = render_preview_snapshot,
        thread_pool: QThreadPool | None = None,
        debounce_ms: int = 250,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.renderer = renderer
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self.debounce_ms = debounce_ms
        self.auto_preview = self.settings.value(
            self.SETTINGS_KEY, True, type=bool
        )
        self.drafts: dict[str, GeneratorDraft] = {}
        self.committed: dict[str, TransformEmitterSettings] = {}
        self.sessions: dict[str, PreviewSession] = {}
        self._pending: PreviewRenderSnapshot | None = None
        self._running = False
        self._closed = False
        self._context_revision = 0
        self._workers: dict[tuple[str, int], _PreviewWorker] = {}
        self._results: SimpleQueue = SimpleQueue()
        self.render_start_count = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_pending)
        self._result_timer = QTimer(self)
        self._result_timer.setInterval(10)
        self._result_timer.timeout.connect(self._poll_results)
        self._result_timer.start()

    def ensure_draft(self, generator: TransformEmitter) -> GeneratorDraft:
        if generator.id not in self.drafts:
            committed = deepcopy(generator.settings)
            self.committed[generator.id] = committed
            self.drafts[generator.id] = GeneratorDraft(
                generator.id, deepcopy(committed)
            )
        return self.drafts[generator.id]

    def update_draft(
        self, project: Project, generator: TransformEmitter, settings: TransformEmitterSettings
    ) -> GeneratorDraft:
        draft = self.ensure_draft(generator)
        if settings == draft.settings:
            return draft
        draft.settings = deepcopy(settings)
        draft.revision += 1
        draft.is_dirty = draft.settings != self.committed[generator.id]
        self.sessions.pop(generator.id, None)
        self.state_changed.emit(
            generator.id, "settings_changed" if draft.is_dirty else "applied"
        )
        if self.auto_preview and draft.is_dirty:
            self.schedule(project, generator.id)
        return draft

    def schedule(self, project: Project, generator_id: str, immediate: bool = False) -> None:
        draft = self.drafts[generator_id]
        try:
            self._pending = PreviewRenderSnapshot.from_project(
                project,
                generator_id,
                draft.revision,
                draft.settings,
                self._context_revision,
            )
        except (StopIteration, ValueError) as exc:
            self.preview_failed.emit(generator_id, draft.revision, str(exc))
            return
        self.state_changed.emit(generator_id, "updating")
        if immediate:
            self._timer.stop()
            self._start_pending()
        else:
            self._timer.start(self.debounce_ms)

    def set_auto_preview(self, enabled: bool) -> None:
        self.auto_preview = bool(enabled)
        self.settings.setValue(self.SETTINGS_KEY, self.auto_preview)
        self.settings.sync()
        if not enabled:
            self._timer.stop()
            self._pending = None

    def _start_pending(self) -> None:
        if self._closed or self._running or self._pending is None:
            return
        snapshot = self._pending
        self._pending = None
        self._running = True
        self.render_start_count += 1
        worker = _PreviewWorker(snapshot, self.renderer, self._results)
        self._workers[(snapshot.generator_id, snapshot.revision)] = worker
        self.thread_pool.start(worker)

    def _poll_results(self) -> None:
        while True:
            try:
                result = self._results.get_nowait()
            except Empty:
                return
            self._worker_completed(*result)

    def _worker_completed(
        self,
        context_revision: int,
        generator_id: str,
        revision: int,
        frames: object,
        error: str,
    ) -> None:
        self._workers.pop((generator_id, revision), None)
        self._running = False
        if self._closed or context_revision != self._context_revision:
            if self._pending is not None:
                self._start_pending()
            return
        draft = self.drafts.get(generator_id)
        if draft is None or revision != draft.revision:
            if self._pending is not None:
                self._start_pending()
            return
        if error or frames is None:
            previous = self.sessions.get(generator_id)
            if previous is not None:
                previous.render_state = "failed"
                previous.error_message = error
            self.state_changed.emit(generator_id, "failed")
            self.preview_failed.emit(generator_id, revision, error)
        else:
            session = PreviewSession(
                generator_id=generator_id,
                revision=revision,
                frames=frames,
                render_state="ready",
            )
            self.sessions[generator_id] = session
            self.state_changed.emit(generator_id, "ready")
            self.preview_ready.emit(generator_id, revision, frames)
        if self._pending is not None:
            self._start_pending()

    def current_session(self, generator_id: str) -> PreviewSession | None:
        session = self.sessions.get(generator_id)
        draft = self.drafts.get(generator_id)
        if session is None or draft is None or session.revision != draft.revision:
            return None
        return session

    def mark_applied(
        self, generator_id: str, committed_settings: TransformEmitterSettings
    ) -> None:
        committed = deepcopy(committed_settings)
        self.committed[generator_id] = committed
        draft = self.drafts[generator_id]
        draft.revision += 1
        draft.settings = deepcopy(committed)
        draft.is_dirty = False
        self.sessions.pop(generator_id, None)
        if self._pending and self._pending.generator_id == generator_id:
            self._pending = None
            self._timer.stop()
        self.state_changed.emit(generator_id, "applied")

    def revert(self, generator_id: str) -> GeneratorDraft:
        draft = self.drafts[generator_id]
        draft.settings = deepcopy(self.committed[generator_id])
        draft.revision += 1
        draft.is_dirty = False
        self.sessions.pop(generator_id, None)
        if self._pending and self._pending.generator_id == generator_id:
            self._pending = None
            self._timer.stop()
        self.state_changed.emit(generator_id, "applied")
        return draft

    def discard(self, generator_id: str) -> None:
        self.revert(generator_id)

    def dirty_generator_ids(self) -> list[str]:
        return [key for key, draft in self.drafts.items() if draft.is_dirty]

    def reset_context(self) -> None:
        self._context_revision += 1
        self._timer.stop()
        self._pending = None
        self.drafts.clear()
        self.committed.clear()
        self.sessions.clear()
        self._workers.clear()

    def close(self) -> None:
        self._closed = True
        self._timer.stop()
        self._pending = None
        self.drafts.clear()
        self.sessions.clear()
