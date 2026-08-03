"""Shortcut command definitions and validation."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QKeySequence


@dataclass(frozen=True, slots=True)
class ShortcutCommand:
    """A configurable application command and its default shortcut."""

    key: str
    label: str
    default: str


SHORTCUT_COMMANDS = (
    ShortcutCommand("new_layer", "New Layer", "Shift+N"),
    ShortcutCommand("new_frame", "New Frame", "Alt+N"),
    ShortcutCommand("new_empty_frame", "New Empty Frame", "Alt+B"),
    ShortcutCommand("play_stop_animation", "Play / Stop Animation", "Enter"),
)

DEFAULT_SHORTCUTS = {
    command.key: command.default for command in SHORTCUT_COMMANDS
}
COMMAND_LABELS = {command.key: command.label for command in SHORTCUT_COMMANDS}


class ShortcutConfigurationError(ValueError):
    """Raised when shortcut settings are invalid or conflict."""


def validate_shortcuts(values: dict[str, str]) -> dict[str, str]:
    """Normalize shortcuts and reject duplicate non-empty key sequences."""
    normalized: dict[str, str] = {}
    assigned: dict[str, str] = {}
    for command in SHORTCUT_COMMANDS:
        raw_value = values.get(command.key, command.default)
        if not isinstance(raw_value, str):
            raise ShortcutConfigurationError(
                f"{command.label} has an invalid shortcut value."
            )
        raw_value = raw_value.strip()
        if not raw_value:
            normalized[command.key] = ""
            continue
        sequence = QKeySequence.fromString(
            raw_value, QKeySequence.SequenceFormat.PortableText
        )
        canonical = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        if sequence.isEmpty() or not canonical:
            raise ShortcutConfigurationError(
                f"{command.label} has an invalid shortcut: {raw_value}"
            )
        if canonical in assigned:
            other = COMMAND_LABELS[assigned[canonical]]
            raise ShortcutConfigurationError(
                f"Shortcut {canonical} is assigned to both {other} and {command.label}."
            )
        assigned[canonical] = command.key
        normalized[command.key] = canonical
    return normalized
