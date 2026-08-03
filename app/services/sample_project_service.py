"""Factories for built-in diagnostic projects."""

from __future__ import annotations

from app.models.project import Project


def create_playback_test_project() -> Project:
    """Create an ordinary project with an eight-frame moving pixel square."""
    project = Project.create_default("Playback Test", 64, 64, 12, True)
    project.layers[0].name = "Playback Test"
    for _ in range(7):
        project.add_frame()
    layer_id = project.layers[0].id
    color = [255, 96, 32, 255]
    square_size = 8
    y = 28
    for index, frame in enumerate(project.frames):
        x = 4 + index * 7
        frame.layer_pixels[layer_id][
            y : y + square_size, x : x + square_size
        ] = color
    return project
