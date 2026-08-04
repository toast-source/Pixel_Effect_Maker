"""Shortcut command definitions and validation."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QKeySequence


@dataclass(frozen=True, slots=True)
class ShortcutCommand:
    """A configurable application command and its default shortcut."""

    key: str
    label: str
    default_sequences: tuple[str, ...]


SHORTCUT_COMMANDS = (
    ShortcutCommand("undo", "Undo", ("Ctrl+Z",)),
    ShortcutCommand("redo", "Redo", ("Ctrl+Shift+Z", "Ctrl+Y")),
    ShortcutCommand("new_layer", "New Layer", ("Shift+N",)),
    ShortcutCommand("new_frame", "New Frame", ("Alt+N",)),
    ShortcutCommand("new_empty_frame", "New Empty Frame", ("Alt+B",)),
    ShortcutCommand("play_stop_animation", "Play / Stop Animation", ("Enter",)),
    ShortcutCommand("previous_frame", "Previous Frame", ("Left", "<")),
    ShortcutCommand("next_frame", "Next Frame", ("Right", ">")),
)

DEFAULT_SHORTCUTS = {
    command.key: list(command.default_sequences) for command in SHORTCUT_COMMANDS
}
COMMAND_LABELS = {command.key: command.label for command in SHORTCUT_COMMANDS}


class ShortcutConfigurationError(ValueError):
    """Raised when shortcut settings are invalid or conflict."""


def validate_shortcuts(
    values: dict[str, str | list[str] | tuple[str, ...]]
) -> dict[str, list[str]]:
    """Normalize shortcuts and reject duplicate non-empty key sequences."""
    normalized: dict[str, list[str]] = {}
    assigned: dict[str, str] = {}
    for command in SHORTCUT_COMMANDS:
        raw_value = values.get(command.key, list(command.default_sequences))
        if isinstance(raw_value, str):
            raw_sequences = [raw_value]
        elif isinstance(raw_value, (list, tuple)) and all(
            isinstance(item, str) for item in raw_value
        ):
            raw_sequences = list(raw_value[:2])
        else:
            raise ShortcutConfigurationError(
                f"{command.label} has an invalid shortcut value."
            )
        command_sequences: list[str] = []
        for raw_sequence in raw_sequences:
            raw_sequence = raw_sequence.strip()
            if not raw_sequence:
                continue
            sequence = QKeySequence.fromString(
                raw_sequence, QKeySequence.SequenceFormat.PortableText
            )
            canonical = sequence.toString(QKeySequence.SequenceFormat.PortableText)
            if sequence.isEmpty() or not canonical:
                raise ShortcutConfigurationError(
                    f"{command.label} has an invalid shortcut: {raw_sequence}"
                )
            conflict_key = {
                "<": "Shift+,",
                "Shift+,": "Shift+,",
                ">": "Shift+.",
                "Shift+.": "Shift+.",
                "Enter": "Enter/Return",
                "Return": "Enter/Return",
            }.get(canonical, canonical)
            if conflict_key in assigned:
                other = COMMAND_LABELS[assigned[conflict_key]]
                raise ShortcutConfigurationError(
                    f"Shortcut {canonical} is assigned to both {other} and {command.label}."
                )
            assigned[conflict_key] = command.key
            command_sequences.append(canonical)
        normalized[command.key] = command_sequences
    return normalized
