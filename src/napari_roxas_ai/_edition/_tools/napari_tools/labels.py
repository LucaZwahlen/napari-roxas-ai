from collections.abc import Sequence

from .._controller import UNDO_ACTION, CustomTool
from .._toolbar import ToolRows, ToolSpec

# napari's Labels modes, ToolSpec name MUST match the napari operation name
LABELS_TOOLS = {
    "pan_zoom": ToolSpec("pan_zoom", "pan_arrows", "Pan/zoom"),
    "pick": ToolSpec("pick", "picker", "Pick a label"),
    "paint": ToolSpec("paint", "paint", "Paint"),
    "polygon": ToolSpec("polygon", "polygon", "Draw a polygon label"),
    "fill": ToolSpec("fill", "fill", "Fill"),
    "erase": ToolSpec("erase", "erase", "Erase"),
}


def labels_rows(custom: Sequence[CustomTool] = ()) -> ToolRows:
    """napari's Labels tools, then the custom tools."""
    t = LABELS_TOOLS
    row = [
        t["pan_zoom"],
        t["pick"],
        t["paint"],
        t["polygon"],
        t["fill"],
        t["erase"],
        None,
        UNDO_ACTION,
    ]
    if custom:
        row += [None, *(tool.spec for tool in custom)]
    return [row]
