"""
This module provides sample data to experiment with the plugin
"""

from PIL import Image
from qtpy.QtCore import QEventLoop

from napari_roxas_ai._assets_files import SAMPLE_DATA, ensure_assets
from napari_roxas_ai._reader import read_directory

# Disable DecompressionBomb warnings for large images
Image.MAX_IMAGE_PIXELS = None


def _layer_order_key(layer_tuple):
    """Sort key to ensure layers are loaded from bottom to top: scan -> cells -> rings."""
    _, add_kwargs, layer_type = layer_tuple
    name = str(add_kwargs.get("name", "")).lower() if isinstance(add_kwargs, dict) else ""
    if layer_type == "image" or "scan" in name:
        return 0
    if "cells" in name:
        return 1
    if "rings" in name:
        return 2
    return 3


def load_sample_data():
    """
    Load the sample data for the conifer dataset.
    This function reads the sample data files from the specified directory
    and returns a list of layer data tuples ordered from bottom to top:
    input image (scan) -> cells -> rings.

    The sample data is downloaded first if missing; nothing is loaded if
    the download is cancelled or fails.
    """
    if not _download_sample_data():
        return []
    layers = read_directory(str(SAMPLE_DATA.directory))
    return sorted(layers, key=_layer_order_key)


def _download_sample_data() -> bool:
    """
    Download the sample data if missing and wait for it: napari's sample data
    hook must return the layers. Returns whether the sample data is available.
    """
    waiting = QEventLoop()
    available = None

    def done(ok: bool) -> None:
        nonlocal available
        available = ok
        waiting.quit()

    ensure_assets([SAMPLE_DATA], done)
    if available is None:  # Still downloading, napari is drawn meanwhile
        waiting.exec()
    return available
