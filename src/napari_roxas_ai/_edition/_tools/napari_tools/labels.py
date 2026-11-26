from collections.abc import Sequence

from .._controller import UNDO_ACTION, CustomTool
from .._toolbar import ToolRows, ToolSpec

# napari's Labels modes, ToolSpec name MUST match the napari operation name,
# with the napari actions whose shortcuts they show
LABELS_TOOLS = {
    "pan_zoom": ToolSpec(
        "pan_zoom",
        "pan_arrows",
        "Pan/zoom",
        action="napari:activate_labels_pan_zoom_mode",
    ),
    "paint": ToolSpec(
        "paint", "paint", "Paint", action="napari:activate_labels_paint_mode"
    ),
    "polygon": ToolSpec(
        "polygon",
        "polygon",
        "Draw a polygon label",
        action="napari:activate_labels_polygon_mode",
    ),
    "erase": ToolSpec(
        "erase", "erase", "Erase", action="napari:activate_labels_erase_mode"
    ),
}


def labels_rows(custom: Sequence[CustomTool] = ()) -> ToolRows:
    """napari's Labels tools, then the custom tools."""
    t = LABELS_TOOLS
    row = [
        t["pan_zoom"],
        None,
        t["erase"],
        t["paint"],
        t["polygon"],
        None,
        UNDO_ACTION,
    ]
    if custom:
        row += [None, *(tool.spec for tool in custom)]
    return [row]
