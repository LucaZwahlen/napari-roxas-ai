"""
LassoSelectTool: a stroke tool drawing a closed lasso (``StrokeSelectTool``).
Selects the shapes with a vertex inside (or on) the lasso.
"""

from pathlib import Path

import cv2
import numpy as np

from ._stroke import StrokeSelectTool
from .._toolbar import ToolSpec

LASSO = "lasso_select"

LASSO_TOOL = ToolSpec(
    LASSO,
    str(Path(__file__).parent.parent / "icons" / "lasso_select.svg"),
    "Lasso select",
)


class LassoSelectTool(StrokeSelectTool):
    spec = LASSO_TOOL
    closed = True
    min_points = 3

    @staticmethod
    def hits(shapes, points) -> set[int]:
        """
        The shapes (Nx2 vertex arrays) with at least one vertex inside or on
        the boundary of the lasso ``points`` (a polygon, at least 3 points).
        """
        lasso = np.asarray(points, dtype=float)
        if len(lasso) < 3 or not len(shapes):
            return set()

        # Bounding box of the lasso (coordinates in (row, col) / (y, x))
        min_r = int(np.floor(np.min(lasso[:, 0]))) - 1
        max_r = int(np.ceil(np.max(lasso[:, 0]))) + 1
        min_c = int(np.floor(np.min(lasso[:, 1]))) - 1
        max_c = int(np.ceil(np.max(lasso[:, 1]))) + 1
        height = max_r - min_r + 1
        width = max_c - min_c + 1

        # Rasterize the lasso, its boundary included. cv2 expects (x, y) =
        # (col, row).
        mask = np.zeros((height, width), dtype=np.uint8)
        contour = np.round(
            np.column_stack((lasso[:, 1] - min_c, lasso[:, 0] - min_r))
        ).astype(np.int32)
        cv2.fillPoly(mask, [contour], 1)
        cv2.drawContours(mask, [contour], -1, 1, 1)

        inside = set()
        for index, shape in enumerate(shapes):
            v_rows = np.round(shape[:, 0]).astype(int) - min_r
            v_cols = np.round(shape[:, 1]).astype(int) - min_c
            in_bounds = (
                (v_rows >= 0)
                & (v_rows < height)
                & (v_cols >= 0)
                & (v_cols < width)
            )
            if np.any(in_bounds) and np.any(
                mask[v_rows[in_bounds], v_cols[in_bounds]] > 0
            ):
                inside.add(index)
        return inside
