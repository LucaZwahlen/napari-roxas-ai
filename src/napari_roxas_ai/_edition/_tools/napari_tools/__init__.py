"""
napari's own Labels and Shapes tools as offered in the tools panel: which
modes, their toolbar rows and the action buttons.
Selecting one is just ``layer.mode = name``.
"""

from .labels import LABELS_TOOLS, labels_rows
from .shapes import (
    DELETE,
    SHAPES_ACTIONS,
    SHAPES_TOOLS,
    shapes_action_states,
    shapes_actions,
    shapes_rows,
)

__all__ = [
    "DELETE",
    "LABELS_TOOLS",
    "SHAPES_ACTIONS",
    "SHAPES_TOOLS",
    "labels_rows",
    "shapes_action_states",
    "shapes_actions",
    "shapes_rows",
]
