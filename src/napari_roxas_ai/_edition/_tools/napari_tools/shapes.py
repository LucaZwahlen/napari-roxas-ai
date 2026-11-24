from collections.abc import Callable, Sequence

from .._controller import UNDO_ACTION, CustomTool
from .._toolbar import ToolRows, ToolSpec

DELETE = "delete"

# napari's Shapes modes offered for polygon editing (no layer transform, ellipses, lines, paths)
SHAPES_TOOLS = {
    "pan_zoom": ToolSpec("pan_zoom", "pan_arrows", "Pan/zoom"),
    "select": ToolSpec("select", "select", "Select shapes"),
    "direct": ToolSpec("direct", "direct", "Select vertices"),
    "vertex_insert": ToolSpec(
        "vertex_insert", "vertex_insert", "Insert vertex"
    ),
    "vertex_remove": ToolSpec(
        "vertex_remove", "vertex_remove", "Remove vertex"
    ),
    "add_rectangle": ToolSpec("add_rectangle", "rectangle", "Add rectangles"),
    "add_polygon": ToolSpec("add_polygon", "polygon", "Add polygons"),
    "add_polygon_lasso": ToolSpec(
        "add_polygon_lasso", "polygon_lasso", "Add polygons with a lasso"
    ),
}

SHAPES_ACTIONS = {
    DELETE: ToolSpec(
        DELETE, "delete_shape", "Delete selected (Delete)", checkable=False
    ),
}


def shapes_rows(custom: Sequence[CustomTool] = ()) -> ToolRows:
    """napari's Shapes tools with custom tools following the selection tools."""
    t = SHAPES_TOOLS
    return [
        [
            t["pan_zoom"],
            t["select"],
            *(tool.spec for tool in custom),
            t["direct"],
            t["vertex_insert"],
            t["vertex_remove"],
            None,
            SHAPES_ACTIONS[DELETE],
            UNDO_ACTION,
        ],
        [
            t["add_rectangle"],
            t["add_polygon"],
            t["add_polygon_lasso"],
        ],
    ]


def shapes_actions() -> dict[str, Callable]:
    """Handlers of the Shapes action buttons."""
    return {DELETE: lambda layer: layer.remove_selected()}


def shapes_action_states(layer) -> dict[str, bool]:
    selected = len(layer.selected_data) > 0
    return {DELETE: selected}
