"""
The assets downloaded from the GitHub releases: one entry per release archive.

A new or renamed model only needs its file name added to ``required`` here,
so that installations without it download the archive again.
"""

from dataclasses import dataclass
from pathlib import Path

PACKAGE_PATH = Path(__file__).parent.parent.absolute()

# Stores the GitHub id of the release asset a directory was last filled from
ASSET_ID_FILE = ".asset_id"


@dataclass(frozen=True)
class Asset:
    """
    A release archive and where its content is installed.

    Args:
        label: Shown to the user, e.g. in the download dialog.
        archive: File name of the archive in the GitHub release.
        directory: Where the archive's content is installed.
        required: Paths (relative to ``directory``) that must be present.
    """

    label: str
    archive: str
    directory: Path
    required: tuple[str, ...]

    def missing(self) -> list[str]:
        """The required files that are not present."""
        return [
            name
            for name in self.required
            if not (self.directory / name).exists()
        ]

    def is_available(self) -> bool:
        return not self.missing()

    def installed_id(self) -> str | None:
        """Id of the release asset the directory was last filled from."""
        try:
            return (self.directory / ASSET_ID_FILE).read_text().strip() or None
        except OSError:
            return None


SEGMENTATION_MODELS_PATH = PACKAGE_PATH / "_segmentation" / "_models"

CELLS_MODELS = Asset(
    label="Cell models",
    archive="cells_models.zip",
    directory=SEGMENTATION_MODELS_PATH / "_cells",
    required=("linear_cells_model.pth",),
)

RINGS_MODELS = Asset(
    label="Ring models",
    archive="rings_models.zip",
    directory=SEGMENTATION_MODELS_PATH / "_rings",
    # The segmentation model and the rings editor's rerun model
    required=("linear_rings_model.pth", "LinearRingModel_v3_iterative.pt"),
)

SAMPLE_DATA = Asset(
    label="Sample data",
    archive="sample_data.zip",
    directory=PACKAGE_PATH / "_sample_data" / "sample_data",
    required=tuple(
        f"conifer_sample/conifer_sample.{suffix}"
        for suffix in (
            "scan.jpg",
            "cells.png",
            "cells_table.txt",
            "rings.tif",
            "rings_table.txt",
            "metadata.json",
        )
    ),
)

ALL_ASSETS = (CELLS_MODELS, RINGS_MODELS, SAMPLE_DATA)
