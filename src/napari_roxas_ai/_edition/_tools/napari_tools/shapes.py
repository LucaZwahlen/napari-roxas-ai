from collections.abc import Callable, Sequence

from .._controller import UNDO_ACTION, CustomTool
from .._toolbar import ToolRows, ToolSpec

DELETE = "delete"

# napari's Shapes modes offered for polygon editing (no shape selection,
# layer transform, rectangles, ellipses, lines, paths), with the napari
# actions whose shortcuts they show
SHAPES_TOOLS = {
    "pan_zoom": ToolSpec(
        "pan_zoom",
        "pan_arrows",
        "Pan/zoom",
        action="napari:activate_shapes_pan_zoom_mode",
    ),
    "direct": ToolSpec(
        "direct",
        "direct",
        "Select vertices",
        action="napari:activate_direct_mode",
    ),
    "vertex_insert": ToolSpec(
        "vertex_insert",
        "vertex_insert",
        "Insert vertex",
        action="napari:activate_vertex_insert_mode",
    ),
    "vertex_remove": ToolSpec(
        "vertex_remove",
        "vertex_remove",
        "Remove vertex",
        action="napari:activate_vertex_remove_mode",
    ),
    "add_polygon": ToolSpec(
        "add_polygon",
        "polygon",
        "Add polygons",
        action="napari:activate_add_polygon_mode",
    ),
    "add_polygon_lasso": ToolSpec(
        "add_polygon_lasso",
        "polygon_lasso",
        "Add polygons with a lasso",
        action="napari:activate_add_polygon_lasso_mode",
    ),
}

SHAPES_ACTIONS = {
    DELETE: ToolSpec(
        DELETE,
        "delete_shape",
        "Delete selected",
        checkable=False,
        action="napari:delete_selected_shapes",
    ),
}


def shapes_rows(custom: Sequence[CustomTool] = ()) -> ToolRows:
    """napari's Shapes tools with custom tools following pan/zoom."""
    t = SHAPES_TOOLS
    return [
        [
            t["pan_zoom"],
            None,
            *(tool.spec for tool in custom),
            t["direct"],
            t["vertex_insert"],
            t["vertex_remove"],
            None,
            t["add_polygon"],
            t["add_polygon_lasso"],
            None,
            SHAPES_ACTIONS[DELETE],
            UNDO_ACTION,
        ],
    ]


def shapes_actions() -> dict[str, Callable]:
    """Handlers of the Shapes action buttons."""
    return {DELETE: lambda layer: layer.remove_selected()}


def shapes_action_states(layer) -> dict[str, bool]:
    selected = len(layer.selected_data) > 0
    return {DELETE: selected}
