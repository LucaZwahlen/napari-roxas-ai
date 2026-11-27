"""
Dropdowns of the files of an asset (e.g. the models), downloading it if needed.
"""

from unittest.mock import patch

import pytest

from napari_roxas_ai._assets_files import (
    Asset,
    AssetComboBox,
    _combo_box,
    assets_updated,
)


@pytest.fixture
def models(tmp_path):
    return Asset(
        label="Ring models",
        archive="rings_models.zip",
        directory=tmp_path / "_rings",
        required=("standard.pth", "rerun.pt"),
    )


def _install(asset, *names):
    asset.directory.mkdir(exist_ok=True)
    for name in names:
        (asset.directory / name).write_bytes(b"weights")


def test_lists_the_files_and_selects_the_default(models):
    _install(models, "rerun.pt", "standard.pth", ".asset_id")

    combo = AssetComboBox(models, default="standard.pth")

    assert combo.choices == ("rerun.pt", "standard.pth")
    assert combo.value == "standard.pth"


def test_only_lists_the_given_suffixes(models):
    _install(models, "standard.pth", "manifest.json")

    combo = AssetComboBox(models, suffixes=(".pt", ".pth"))

    assert combo.choices == ("standard.pth",)


def test_lists_the_files_once_downloaded(models):
    combo = AssetComboBox(models, default="standard.pth")
    assert combo.choices == ()

    _install(models, "rerun.pt", "standard.pth")
    assets_updated.emit()

    assert combo.choices == ("rerun.pt", "standard.pth")
    assert combo.value == "standard.pth"


def test_keeps_the_selection_after_a_download(models):
    _install(models, "rerun.pt", "standard.pth")
    combo = AssetComboBox(models, default="standard.pth")
    combo.value = "rerun.pt"

    assets_updated.emit()

    assert combo.value == "rerun.pt"


def test_downloads_the_asset_when_first_shown(models, qtbot):
    with patch.object(_combo_box, "ensure_assets") as ensure_assets:
        combo = AssetComboBox(models)
        qtbot.addWidget(combo.native)
        # E.g. the hidden rings editor created by the loading widget
        ensure_assets.assert_not_called()

        combo.show()
        combo.hide()
        combo.show()

    ensure_assets.assert_called_once_with([models])
