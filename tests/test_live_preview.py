"""Non-destructive Draft and asynchronous Preview regressions."""

from __future__ import annotations

from copy import deepcopy
import os
import time

import numpy as np
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.models.effect_generator import TransformEmitter, TransformEmitterSettings
from app.models.project import Project
from app.models.source_asset import SourceAsset
from app.services.preview_service import PreviewManager
from app.services.project_io import load_project, save_project
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow


APPLICATION = QApplication.instance() or QApplication([])


def service_for(tmp_path) -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", "en")
    return ShortcutSettingsService(settings)


def prepared_window(tmp_path) -> tuple[MainWindow, TransformEmitter]:
    path = tmp_path / "preview-source.png"
    pixels = np.zeros((4, 4, 4), dtype=np.uint8)
    pixels[1:3, 1:3] = [255, 80, 20, 255]
    Image.fromarray(pixels, "RGBA").save(path)
    window = MainWindow(service_for(tmp_path))
    window.import_source_asset_path(path)
    emitter = window.add_transform_emitter()
    assert emitter is not None
    initial = window.effect_properties.current_settings()
    initial.output_frames = 4
    initial.lifetime = 4
    assert window.generate_effect(emitter.id, initial)
    window.dirty = False
    return window, emitter


def wait_for_preview(window: MainWindow, emitter_id: str, timeout_ms: int = 1500) -> None:
    elapsed = 0
    while window.preview_manager.current_session(emitter_id) is None and elapsed < timeout_ms:
        QTest.qWait(25)
        elapsed += 25
    assert window.preview_manager.current_session(emitter_id) is not None


def test_property_change_only_mutates_draft_and_preview(tmp_path) -> None:
    window, emitter = prepared_window(tmp_path)
    committed = deepcopy(emitter.settings)
    layer_id = emitter.generated_layer_id
    assert layer_id is not None
    applied_pixels = [frame.layer_pixels[layer_id].copy() for frame in window.project.frames]
    source_pixels = window.project.source_assets[0].pixels.copy()

    window.effect_properties.rotation_end.setValue(90)
    window.effect_properties.output_frames.setValue(7)
    assert emitter.settings == committed
    assert not window.dirty
    wait_for_preview(window, emitter.id)
    assert window.canvas.preview_frames is not None
    assert len(window.canvas.preview_frames) == 7
    assert window.active_preview_generator_id == emitter.id
    assert emitter.settings == committed
    assert not window.dirty
    assert np.array_equal(window.project.source_assets[0].pixels, source_pixels)
    assert all(
        np.array_equal(frame.layer_pixels[layer_id], before)
        for frame, before in zip(window.project.frames, applied_pixels, strict=True)
    )
    assert "Preview ready" in window.effect_properties.settings_status.text()
    window.show()
    window.canvas.setFocus()
    APPLICATION.processEvents()
    QTest.keyClick(window.canvas, Qt.Key.Key_Return)
    APPLICATION.processEvents()
    assert window.play_timer.isActive()
    assert "Preview Playing" in window.timeline.playback_status_label.text()
    before_index = window.frame_index
    QTest.keyClick(window.canvas, Qt.Key.Key_Right)
    APPLICATION.processEvents()
    assert not window.play_timer.isActive()
    assert window.frame_index == min(before_index + 1, 6)
    window.preview_manager.discard(emitter.id)
    window.dirty = False
    window.close()


def test_preview_can_be_shorter_than_applied_project(tmp_path) -> None:
    window, emitter = prepared_window(tmp_path)
    assert len(window.project.frames) == 4
    window.effect_properties.output_frames.setValue(2)
    wait_for_preview(window, emitter.id)
    assert window._display_frame_count() == 2
    window.frame_index = 1
    window.next_frame()
    assert window.frame_index == 1
    window.effect_properties.generate_button.click()
    assert len(window.project.frames) == 4
    assert emitter.generated_layer_id is not None
    assert not window.project.frames[2].layer_pixels[emitter.generated_layer_id].any()
    window.dirty = False
    window.close()


def test_apply_reuses_latest_preview_and_revert_is_non_destructive(tmp_path) -> None:
    window, emitter = prepared_window(tmp_path)
    window.effect_properties.offset_x_end.setValue(8)
    wait_for_preview(window, emitter.id)
    starts = window.preview_manager.render_start_count
    preview = [frame.copy() for frame in window.canvas.preview_frames or []]
    window.effect_properties.generate_button.click()
    assert window.preview_manager.render_start_count == starts
    assert emitter.settings.offset_x_end == 8
    assert window.dirty
    assert emitter.generated_layer_id is not None
    assert all(
        np.array_equal(frame.layer_pixels[emitter.generated_layer_id], expected)
        for frame, expected in zip(window.project.frames, preview, strict=True)
    )
    window.dirty = False
    committed = deepcopy(emitter.settings)
    pixels = [
        frame.layer_pixels[emitter.generated_layer_id].copy()
        for frame in window.project.frames
    ]
    window.effect_properties.rotation_end.setValue(45)
    window.revert_generator_draft(emitter.id)
    assert window.preview_manager.drafts[emitter.id].settings == committed
    assert emitter.settings == committed
    assert not window.dirty
    assert window.canvas.preview_frames is None
    assert all(
        np.array_equal(frame.layer_pixels[emitter.generated_layer_id], expected)
        for frame, expected in zip(window.project.frames, pixels, strict=True)
    )
    window.close()


def test_unapplied_preview_is_not_saved(tmp_path) -> None:
    window, emitter = prepared_window(tmp_path)
    committed = deepcopy(emitter.settings)
    window.effect_properties.scale_x_end.setValue(2.5)
    wait_for_preview(window, emitter.id)
    saved = save_project(window.project, tmp_path / "committed-only.peffect.json")
    loaded = load_project(saved)
    assert loaded.generators[0].settings == committed
    window.preview_manager.discard(emitter.id)
    window.close()


def test_debounce_coalesces_changes_and_uses_last_value(tmp_path) -> None:
    calls: list[float] = []

    def renderer(snapshot):
        calls.append(snapshot.settings.rotation_end)
        return [np.zeros((snapshot.height, snapshot.width, 4), dtype=np.uint8)]

    settings = QSettings(str(tmp_path / "preview.ini"), QSettings.Format.IniFormat)
    manager = PreviewManager(settings, renderer=renderer, debounce_ms=60)
    project = Project.create_default(width=8, height=8)
    asset = SourceAsset("Source", np.zeros((2, 2, 4), dtype=np.uint8))
    project.source_assets.append(asset)
    emitter = TransformEmitter("Emitter", TransformEmitterSettings(asset.id))
    project.generators.append(emitter)
    manager.ensure_draft(emitter)
    for value in range(10):
        draft = deepcopy(emitter.settings)
        draft.rotation_end = value
        manager.update_draft(project, emitter, draft)
    assert calls == []
    QTest.qWait(200)
    assert calls == [9]
    assert manager.render_start_count == 1
    manager.close()


def test_auto_preview_off_requires_manual_refresh_and_persists(tmp_path) -> None:
    calls = []

    def renderer(snapshot):
        calls.append(snapshot.revision)
        return [np.zeros((snapshot.height, snapshot.width, 4), dtype=np.uint8)]

    settings = QSettings(str(tmp_path / "manual.ini"), QSettings.Format.IniFormat)
    manager = PreviewManager(settings, renderer=renderer, debounce_ms=20)
    project = Project.create_default(width=4, height=4)
    asset = SourceAsset("Source", np.zeros((2, 2, 4), dtype=np.uint8))
    project.source_assets.append(asset)
    emitter = TransformEmitter("Emitter", TransformEmitterSettings(asset.id))
    project.generators.append(emitter)
    manager.ensure_draft(emitter)
    manager.set_auto_preview(False)
    changed = deepcopy(emitter.settings)
    changed.rotation_end = 20
    manager.update_draft(project, emitter, changed)
    QTest.qWait(100)
    assert calls == []
    manager.schedule(project, emitter.id, immediate=True)
    QTest.qWait(100)
    assert len(calls) == 1
    assert settings.value(PreviewManager.SETTINGS_KEY, type=bool) is False
    manager.close()


def test_project_context_reset_discards_late_worker_result(tmp_path) -> None:
    def renderer(snapshot):
        time.sleep(0.08)
        return [np.zeros((snapshot.height, snapshot.width, 4), dtype=np.uint8)]

    settings = QSettings(str(tmp_path / "context.ini"), QSettings.Format.IniFormat)
    manager = PreviewManager(settings, renderer=renderer, debounce_ms=10)
    project = Project.create_default(width=4, height=4)
    asset = SourceAsset("Source", np.zeros((2, 2, 4), dtype=np.uint8))
    project.source_assets.append(asset)
    emitter = TransformEmitter("Emitter", TransformEmitterSettings(asset.id))
    project.generators.append(emitter)
    manager.ensure_draft(emitter)
    changed = deepcopy(emitter.settings)
    changed.rotation_end = 30
    manager.update_draft(project, emitter, changed)
    manager.schedule(project, emitter.id, immediate=True)
    manager.reset_context()
    QTest.qWait(200)
    assert manager.sessions == {}
    assert manager.drafts == {}
    manager.close()


def test_stale_revision_is_discarded_and_latest_wins(tmp_path) -> None:
    def renderer(snapshot):
        if snapshot.settings.rotation_end == 1:
            time.sleep(0.12)
        marker = int(snapshot.settings.rotation_end)
        return [np.full((snapshot.height, snapshot.width, 4), marker, dtype=np.uint8)]

    settings = QSettings(str(tmp_path / "revision.ini"), QSettings.Format.IniFormat)
    manager = PreviewManager(settings, renderer=renderer, debounce_ms=10)
    project = Project.create_default(width=4, height=4)
    asset = SourceAsset("Source", np.zeros((2, 2, 4), dtype=np.uint8))
    project.source_assets.append(asset)
    emitter = TransformEmitter("Emitter", TransformEmitterSettings(asset.id))
    project.generators.append(emitter)
    manager.ensure_draft(emitter)
    first = deepcopy(emitter.settings)
    first.rotation_end = 1
    manager.update_draft(project, emitter, first)
    manager.schedule(project, emitter.id, immediate=True)
    QTest.qWait(20)
    second = deepcopy(first)
    second.rotation_end = 2
    manager.update_draft(project, emitter, second)
    QTest.qWait(800)
    session = manager.current_session(emitter.id)
    assert session is not None, (
        manager._running,
        manager._pending,
        manager.render_start_count,
        manager.drafts[emitter.id].revision,
        manager.sessions,
    )
    assert session.revision == manager.drafts[emitter.id].revision
    assert session.frames[0][0, 0, 0] == 2
    assert manager.render_start_count == 2
    manager.close()


def test_preview_failure_keeps_project_unchanged(tmp_path) -> None:
    def renderer(snapshot):
        raise ValueError("test render failure")

    window, emitter = prepared_window(tmp_path)
    layer_id = emitter.generated_layer_id
    assert layer_id is not None
    before = [frame.layer_pixels[layer_id].copy() for frame in window.project.frames]
    window.preview_manager.renderer = renderer
    window.effect_properties.rotation_end.setValue(10)
    QTest.qWait(800)
    assert emitter.settings.rotation_end != 10
    assert not window.dirty
    assert all(
        np.array_equal(frame.layer_pixels[layer_id], expected)
        for frame, expected in zip(window.project.frames, before, strict=True)
    )
    assert "failed" in window.effect_properties.settings_status.text().lower()
    window.preview_manager.discard(emitter.id)
    window.close()
