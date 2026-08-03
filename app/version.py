"""Central application version information."""

APP_NAME = "Pixel Effect Maker"
__version__ = "0.0.01"
VERSION_LABEL = f"v{__version__}"


def get_display_name() -> str:
    """Return the application name with its user-facing version label."""
    return f"{APP_NAME} {VERSION_LABEL}"
