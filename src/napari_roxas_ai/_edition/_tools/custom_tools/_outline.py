import numpy as np
from napari.layers import Shapes
from napari.settings import get_settings

from .._companion import CompanionLayer

# Edited layer -> its outline (until removed)
_OUTLINES: dict = {}


class SelectionOutline:
    """
    The outline of a selection being drawn as a solid line in naparis
    preferenced highlight color. Drawn as a non-filled polygon in a ``shapes``
    layer right above the edited layer, belonging to it (``CompanionLayer``:
    the user can't hide, delete or select it).

    Added by the editor for an edit session (``add``; adding a layer is slow,
    switching tools must not be) and removed when it ends (``remove``). The
    tools get it with ``of(layer)``: without one, nothing is drawn.
    """

    @classmethod
    def add(cls, viewer, reference_layer) -> "SelectionOutline":
        """Add the outline of ``reference_layer`` to the viewer."""
        outline = cls(viewer, reference_layer)
        _OUTLINES[reference_layer] = outline
        return outline

    @staticmethod
    def of(reference_layer) -> "SelectionOutline | None":
        """The outline of ``reference_layer`` (None: it has none)."""
        return _OUTLINES.get(reference_layer)

    def __init__(self, viewer, reference_layer):
        self._viewer = viewer
        self._reference = reference_layer
        self._scale = np.asarray(reference_layer.scale[-2:], dtype=float)
        self._highlight = get_settings().appearance.highlight
        # The outline shown (redrawn when its style changes)
        self._points: np.ndarray | None = None
        self._closed = False

        self._layer = Shapes(
            ndim=2,
            scale=self._scale,
            translate=reference_layer.translate[-2:],
            opacity=1,
            blending="translucent_no_depth",
        )
        self._companion = CompanionLayer(viewer, self._layer, reference_layer)
        viewer.camera.events.zoom.connect(self._update_style)
        self._highlight.events.highlight_color.connect(self._update_style)
        self._highlight.events.highlight_thickness.connect(self._update_style)

    @property
    def layer(self) -> Shapes:
        return self._layer

    @property
    def width(self) -> float:
        """The highlight thickness (screen pixels) in data units."""
        scale = float(np.mean(np.abs(self._scale))) or 1.0
        zoom = float(self._viewer.camera.zoom) or 1.0
        return float(self._highlight.highlight_thickness) / (zoom * scale)

    def _color(self):
        return np.asarray(self._highlight.highlight_color, dtype=float)

    def show(self, points: np.ndarray, closed: bool = True) -> None:
        """Outline ``points`` (data coordinates of the reference layer)."""
        self._points = np.asarray(points, dtype=float)
        self._closed = closed
        self._draw()

    def clear(self) -> None:
        if self._points is None:
            return
        self._points = None
        self._draw()

    def _draw(self) -> None:
        if self._layer not in self._viewer.layers:
            return
        self._layer.data = []
        points = self._points
        if points is None or len(points) < 2:
            return
        style = {"edge_width": self.width, "edge_color": self._color()}
        if self._closed and len(points) >= 3:
            self._layer.add_polygons(
                [points], face_color="transparent", **style
            )
        else:
            self._layer.add_paths([points], **style)

    def _update_style(self, _event=None) -> None:
        if self._points is not None:
            self._draw()

    def remove(self) -> None:
        if _OUTLINES.get(self._reference) is self:
            del _OUTLINES[self._reference]
        self._viewer.camera.events.zoom.disconnect(self._update_style)
        self._highlight.events.highlight_color.disconnect(self._update_style)
        self._highlight.events.highlight_thickness.disconnect(
            self._update_style
        )
        self._companion.release()
