"""
The models and sample data downloaded from the GitHub releases.

ex:
self._cells_model = AssetComboBox(CELLS_MODELS, label="Model:")
ensure_assets([SAMPLE_DATA], on_done=self._on_sample_data_ready)
"""

from ._combo_box import DOWNLOAD_MENU_HINT, AssetComboBox
from ._manager import assets_updated, download_missing_assets, ensure_assets
from ._registry import (
    ALL_ASSETS,
    CELLS_MODELS,
    RINGS_MODELS,
    SAMPLE_DATA,
    Asset,
)

__all__ = [
    "ALL_ASSETS",
    "Asset",
    "AssetComboBox",
    "CELLS_MODELS",
    "DOWNLOAD_MENU_HINT",
    "RINGS_MODELS",
    "SAMPLE_DATA",
    "assets_updated",
    "download_missing_assets",
    "ensure_assets",
]
