"""
Editing tools: the tools panel of the edit sessions.

- ``napari_tools/``: napari's own Labels and Shapes tools we offer;
- ``custom_tools/``: our own tools (lasso, line select);
- ``options/``: tool and layer options;
- ``_controller``: binds a toolbar to a layer (``LayerTools``), ``CustomTool``;
- ``_companion``: layers belonging to another layer (``CompanionLayer``);
- ``_toolbar``, ``_panel``: the widgets.
"""

from ._controller import UNDO, UNDO_ACTION, CustomTool, LayerTools
from ._panel import PIXEL, VECTOR, EditToolsPanel
from ._toolbar import ToolBar, ToolSpec
from .custom_tools import (
    LASSO,
    LASSO_TOOL,
    LINE_SELECT,
    LINE_SELECT_TOOL,
    LassoSelectTool,
    LineSelectTool,
    SelectionOutline,
    StrokeSelectTool,
)
from .napari_tools import (
    DELETE,
    LABELS_TOOLS,
    SHAPES_ACTIONS,
    SHAPES_TOOLS,
    labels_rows,
    shapes_action_states,
    shapes_actions,
    shapes_rows,
)

__all__ = [
    "DELETE",
    "LABELS_TOOLS",
    "LASSO",
    "LASSO_TOOL",
    "LINE_SELECT",
    "LINE_SELECT_TOOL",
    "PIXEL",
    "SHAPES_ACTIONS",
    "SHAPES_TOOLS",
    "UNDO",
    "UNDO_ACTION",
    "VECTOR",
    "CustomTool",
    "EditToolsPanel",
    "LassoSelectTool",
    "LineSelectTool",
    "LayerTools",
    "SelectionOutline",
    "StrokeSelectTool",
    "ToolBar",
    "ToolSpec",
    "labels_rows",
    "shapes_action_states",
    "shapes_actions",
    "shapes_rows",
]
