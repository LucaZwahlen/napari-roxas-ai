from magicgui.widgets import CheckBox

from ._base import ToolOption


class Contiguous(ToolOption):
    """Fill only the connected region."""

    name = "contiguous"
    label = "Contiguous"
    tools = frozenset({"fill"})

    def make_widget(self):
        return CheckBox()

    def read(self, layer):
        return bool(layer.contiguous)

    def write(self, layer, value) -> None:
        layer.contiguous = value

    def layer_event(self, layer):
        return layer.events.contiguous
