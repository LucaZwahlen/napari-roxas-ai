from pathlib import Path

import cv2
import numpy as np

from ._stroke import StrokeSelectTool
from .._toolbar import ToolSpec

LINE_SELECT = "line_select"

LINE_SELECT_TOOL = ToolSpec(
    LINE_SELECT,
    str(Path(__file__).parent.parent / "icons" / "line_select.svg"),
    "Line select: selects what the line crosses",
)


def _cross(o, a, b):
    return (a[..., 0] - o[..., 0]) * (b[..., 1] - o[..., 1]) - (
        a[..., 1] - o[..., 1]
    ) * (b[..., 0] - o[..., 0])


class LineSelectTool(StrokeSelectTool):
    spec = LINE_SELECT_TOOL
    closed = False
    min_points = 2

    @staticmethod
    def hits(shapes, points) -> set[int]:
        """
        The shapes (Nx2 vertex arrays) crossed or touched by the line
        ``points`` (a polyline, at least 2 points), or containing it entirely.
        """
        line = np.asarray(points, dtype=float)
        if len(line) < 2 or not len(shapes):
            return set()
        low, high = line.min(axis=0), line.max(axis=0)
        # Line segments, (M, 1, 2) to compare with the K edges of a shape
        p1, p2 = line[:-1, None, :], line[1:, None, :]

        hit = set()
        for index, shape in enumerate(shapes):
            shape = np.asarray(shape, dtype=float)
            if np.any(shape.max(axis=0) < low) or np.any(
                shape.min(axis=0) > high
            ):
                continue
            q1 = shape[None, :, :]
            q2 = np.roll(shape, -1, axis=0)[None, :, :]
            # Segments and edges with overlapping bounding boxes, whose end
            # points lie on both sides of (or on) each other
            boxes_overlap = np.all(
                (np.minimum(p1, p2) <= np.maximum(q1, q2))
                & (np.minimum(q1, q2) <= np.maximum(p1, p2)),
                axis=-1,
            )
            crossing = (_cross(q1, q2, p1) * _cross(q1, q2, p2) <= 0) & (
                _cross(p1, p2, q1) * _cross(p1, p2, q2) <= 0
            )
            # ... or the line lies inside the shape (same axis order for both)
            inside = (
                cv2.pointPolygonTest(
                    shape.astype(np.float32).reshape(-1, 1, 2),
                    (float(line[0, 0]), float(line[0, 1])),
                    False,
                )
                >= 0
            )
            if np.any(boxes_overlap & crossing) or inside:
                hit.add(index)
        return hit
