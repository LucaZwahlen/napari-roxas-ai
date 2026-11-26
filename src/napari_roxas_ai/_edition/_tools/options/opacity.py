from magicgui.widgets import FloatSlider

from ._base import ToolOption


class Opacity(ToolOption):
    """Opacity of the layer, whatever the tool."""

    name = "opacity"
    label = "Layer opacity"
    tools = None

    def make_widget(self):
        return FloatSlider(min=0, max=1, step=0.01)

    def read(self, layer):
        return float(layer.opacity)

    def write(self, layer, value) -> None:
        layer.opacity = value

    def layer_event(self, layer):
        return layer.events.opacity
