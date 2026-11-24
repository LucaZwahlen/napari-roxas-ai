"""
Tool options: one file per option (a ``ToolOption`` subclass).

``default_options(page)`` is what each page of the tools dock shows.
"""

from ._base import OptionsBox, ToolOption
from .brush_size import BrushSize
from .contiguous import Contiguous
from .opacity import Opacity


def default_options(page: str) -> list[ToolOption]:
    """The options of the ``pixel`` or ``vector`` page."""
    if page == "pixel":
        return [BrushSize(), Contiguous(), Opacity()]
    return [Opacity()]


__all__ = [
    "BrushSize",
    "Contiguous",
    "Opacity",
    "OptionsBox",
    "ToolOption",
    "default_options",
]
