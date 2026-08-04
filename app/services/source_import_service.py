"""PNG source asset loading and validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.models.source_asset import SourceAsset

MAX_SOURCE_DIMENSION = 2048
MAX_SOURCE_PIXELS = 4_194_304


class SourceImportError(ValueError):
    """Raised when an image cannot be safely imported as a source asset."""


def import_source_asset(path: str | Path) -> SourceAsset:
    """Load a PNG as an embedded, independent RGBA source asset."""
    source = Path(path)
    if source.suffix.lower() != ".png":
        raise SourceImportError("only PNG source assets are supported")
    try:
        with Image.open(source) as image:
            if image.format != "PNG":
                raise SourceImportError("the selected file is not a valid PNG")
            width, height = image.size
            if (
                width < 1
                or height < 1
                or width > MAX_SOURCE_DIMENSION
                or height > MAX_SOURCE_DIMENSION
                or width * height > MAX_SOURCE_PIXELS
            ):
                raise SourceImportError(
                    f"PNG dimensions exceed the safe limit ({MAX_SOURCE_DIMENSION}px "
                    f"per side, {MAX_SOURCE_PIXELS:,} pixels total)"
                )
            pixels = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    except SourceImportError:
        raise
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise SourceImportError(f"could not import PNG: {exc}") from exc
    return SourceAsset(
        name=source.stem,
        pixels=pixels,
        source_path=str(source.resolve()),
    )
