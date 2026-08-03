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

    def load(self) -> dict[str, str]:
        values = {
            command.key: self.settings.value(
                f"{self.PREFIX}/{command.key}", command.default, type=str
            )
            for command in SHORTCUT_COMMANDS
        }
        try:
            return validate_shortcuts(values)
        except ShortcutConfigurationError:
            defaults = dict(DEFAULT_SHORTCUTS)
            self.save(defaults)
            return defaults

    def save(self, values: dict[str, str]) -> dict[str, str]:
        normalized = validate_shortcuts(values)
        for key, shortcut in normalized.items():
            self.settings.setValue(f"{self.PREFIX}/{key}", shortcut)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise SettingsError("Could not save keyboard shortcut settings.")
        return normalized

    def restore_defaults(self) -> dict[str, str]:
        return self.save(dict(DEFAULT_SHORTCUTS))
