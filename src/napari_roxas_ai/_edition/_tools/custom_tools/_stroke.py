import numpy as np

from .._controller import CustomTool
from ._outline import SelectionOutline


class StrokeSelectTool(CustomTool):
    """
    Napari's Shapes select mode where a drag draws a stroke (a lasso, a line, ...)
    whose hit shapes become napari's selection.

    Interactions with the selection are left to napari (move, resize).
    Any other drag, also on an unselected shape, draws a stroke; on release, the shapes
    it ``hits`` become napari's selection. While a stroke is drawn the
    layer is in pan_zoom mode, which takes napari's select drag out of the
    layer's drag callbacks.
    """

    closed: bool = False
    min_points: int = 2

    def __init__(self, viewer):
        self._viewer = viewer
        self._tools = None
        self._outline: SelectionOutline | None = None
        self._stroke: list | None = None
        self._select_cursor = "standard"

    def hits(self, shapes, points: np.ndarray) -> set[int]:
        """The indices of the ``shapes`` (Nx2 arrays) the stroke selects."""
        raise NotImplementedError

    @property
    def is_drawing(self) -> bool:
        return self._stroke is not None

    def activate(self, tools, layer) -> None:
        self._tools = tools
        tools.set_mode(layer, "select")
        # Added by the editor for the edit session; without one, the stroke
        # is not drawn
        self._outline = SelectionOutline.of(layer)
        # First, to run before (and instead of) napari's select drag
        layer.mouse_drag_callbacks.insert(0, self._on_drag)
        layer.bind_key("Escape", self._cancel_stroke, overwrite=True)
        self._select_cursor = layer.cursor
        layer.cursor = "cross"

    def deactivate(self, tools, layer) -> None:
        self._tools = None
        self._stroke = None
        if self._on_drag in layer.mouse_drag_callbacks:
            layer.mouse_drag_callbacks.remove(self._on_drag)
        layer.bind_key("Escape", None)
        if layer.mode == "select":
            layer.cursor = self._select_cursor
        if self._outline is not None:
            self._outline.clear()
            self._outline = None

    def _cancel_stroke(self, _layer=None) -> None:
        self._stroke = None
        if self._outline is not None:
            self._outline.clear()

    def _on_drag(self, layer, event):
        tools = self._tools
        if tools is None or event.button != 1:
            return
        shape, vertex = layer.get_value(event.position, world=True)
        if vertex is not None or shape in layer.selected_data:
            # On the selection (a selected shape or a handle of its box):
            # napari moves or resizes it
            return

        tools.set_mode(layer, "pan_zoom")
        layer.mouse_pan = False
        layer.cursor = "cross"
        stroke = [self._data_position(layer, event)]
        self._stroke = stroke
        yield
        while event.type == "mouse_move":
            if self._stroke is stroke:
                point = self._data_position(layer, event)
                if not np.array_equal(point, stroke[-1]):
                    stroke.append(point)
                    if self._outline is not None:
                        self._outline.show(np.array(stroke), self.closed)
            yield

        if self._tools is not tools:
            return  # turned off while drawing
        tools.set_mode(layer, "select")
        layer.cursor = "cross"
        if self._stroke is not stroke:
            return  # cancelled (Escape)
        self._cancel_stroke()
        selected = (
            set(layer.selected_data) if "Shift" in event.modifiers else set()
        )
        if len(stroke) >= self.min_points:
            selected |= self.hits(layer.data, np.array(stroke))
        layer.selected_data = selected
        tools.update_actions()

    @staticmethod
    def _data_position(layer, event) -> np.ndarray:
        return np.asarray(layer.world_to_data(event.position), float)[-2:]
