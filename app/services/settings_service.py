"""Application-level settings persistence."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from app.shortcuts import (
    DEFAULT_SHORTCUTS,
    SHORTCUT_COMMANDS,
    ShortcutConfigurationError,
    validate_shortcuts,
)


class SettingsError(RuntimeError):
    """Raised when user settings cannot be persisted."""


class ShortcutSettingsService:
    """Load and save project-independent keyboard shortcuts via QSettings."""

    PREFIX = "keyboard_shortcuts"

    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings or QSettings("SOUTHPAW GAMES", "Pixel Effect Maker")

    def load(self) -> dict[str, list[str]]:
        missing_keys = [
            command.key
            for command in SHORTCUT_COMMANDS
            if not self.settings.contains(f"{self.PREFIX}/{command.key}")
        ]
        values = {
            command.key: self.settings.value(
                f"{self.PREFIX}/{command.key}", list(command.default_sequences)
            )
            for command in SHORTCUT_COMMANDS
        }
        try:
            normalized = validate_shortcuts(values)
        except ShortcutConfigurationError:
            defaults = dict(DEFAULT_SHORTCUTS)
            self.save(defaults)
            return defaults
        if missing_keys:
            return self.save(normalized)
        return normalized

    def save(
        self, values: dict[str, str | list[str] | tuple[str, ...]]
    ) -> dict[str, list[str]]:
        normalized = validate_shortcuts(values)
        for key, shortcut in normalized.items():
            self.settings.setValue(f"{self.PREFIX}/{key}", shortcut)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise SettingsError("Could not save keyboard shortcut settings.")
        return normalized

    def restore_defaults(self) -> dict[str, list[str]]:
        return self.save({key: list(value) for key, value in DEFAULT_SHORTCUTS.items()})
