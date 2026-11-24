from magicgui.widgets import Slider

from ._base import ToolOption


class BrushSize(ToolOption):
    """Brush diameter of the Labels paint and erase tools."""

    name = "brush_size"
    label = "Brush size"
    tools = frozenset({"paint", "erase"})

    def make_widget(self):
        return Slider(min=1, max=100)

    def read(self, layer):
        return int(round(layer.brush_size))

    def write(self, layer, value) -> None:
        layer.brush_size = value

    def layer_event(self, layer):
        return layer.events.brush_size
